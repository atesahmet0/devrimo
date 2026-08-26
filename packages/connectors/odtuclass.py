"""ODTÜClass (Moodle) connector — saf Python, agent'ten bağımsız.

Giriş sırası:
  1. ``login/token.php`` (moodle_mobile_app servisi) → REST webservice çağrıları.
  2. Olmazsa web form-login (session cookie ile) + sayfa kazıma (best-effort).

Credential'lar env'den gelir: ODTUCLASS_URL, ODTU_USERNAME, ODTU_PASSWORD.
Şifre hiçbir yere loglanmaz / yazılmaz; sadece istek gövdesinde kullanılır.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime
from html.parser import HTMLParser

import httpx

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) devrimo-agent/0.2"

ANNOUNCEMENT_HINTS = re.compile(r"duyur|announc|news|haber", re.IGNORECASE)


class ODTUClassError(Exception):
    """Connector temel hatası."""


class ODTUAuthError(ODTUClassError):
    """Kullanıcı adı veya şifre hatalı."""

    def __init__(self) -> None:
        super().__init__("ODTÜClass girişi başarısız: kullanıcı adı veya şifre hatalı.")


class ODTUUnavailableError(ODTUClassError):
    """Siteye erişilemedi / zaman aşımı."""


class ODTUDataError(ODTUClassError):
    """Veri alındı ama ayrıştırılamadı / beklenmeyen yanıt."""


def load_config() -> tuple[str | None, str | None, str | None]:
    return (
        os.environ.get("ODTUCLASS_URL"),
        os.environ.get("ODTU_USERNAME"),
        os.environ.get("ODTU_PASSWORD"),
    )


def is_configured() -> bool:
    return all(load_config())


def from_env(**kwargs) -> "ODTUClassClient | None":
    url, user, password = load_config()
    if not (url and user and password):
        return None
    return ODTUClassClient(url, user, password, **kwargs)


_default_client: ODTUClassClient | None = None


def default_client() -> "ODTUClassClient | None":
    global _default_client
    if _default_client is None and is_configured():
        _default_client = from_env()
    return _default_client


def get_courses(client: "ODTUClassClient | None" = None) -> list[dict]:
    cli = client or default_client()
    if cli is None:
        raise ODTUClassError(
            "ODTÜClass ayarlı değil: ODTUCLASS_URL, ODTU_USERNAME ve ODTU_PASSWORD gerekli."
        )
    return cli.get_courses()


def get_announcements(course_id=None, client: "ODTUClassClient | None" = None) -> list[dict]:
    cli = client or default_client()
    if cli is None:
        raise ODTUClassError(
            "ODTÜClass ayarlı değil: ODTUCLASS_URL, ODTU_USERNAME ve ODTU_PASSWORD gerekli."
        )
    return cli.get_announcements(course_id)


def get_assignments(course_id=None, client: "ODTUClassClient | None" = None) -> list[dict]:
    cli = client or default_client()
    if cli is None:
        raise ODTUClassError(
            "ODTÜClass ayarlı değil: ODTUCLASS_URL, ODTU_USERNAME ve ODTU_PASSWORD gerekli."
        )
    return cli.get_assignments(course_id)


def get_grades(course_id=None, client: "ODTUClassClient | None" = None) -> list[dict]:
    cli = client or default_client()
    if cli is None:
        raise ODTUClassError(
            "ODTÜClass ayarlı değil: ODTUCLASS_URL, ODTU_USERNAME ve ODTU_PASSWORD gerekli."
        )
    return cli.get_grades(course_id)


def _iso(ts) -> str | None:
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def strip_html(text: str, limit: int = 400) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


class _HiddenInputs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        d = dict(attrs)
        if d.get("type", "text").lower() == "hidden" and d.get("name"):
            self.fields[d["name"]] = d.get("value") or ""


def parse_hidden_inputs(page: str) -> dict[str, str]:
    p = _HiddenInputs()
    p.feed(page)
    return p.fields


class _LinkTexts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href = None
        self.buf: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.buf = []

    def handle_data(self, data):
        if self.href is not None:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            text = re.sub(r"\s+", " ", " ".join(self.buf)).strip()
            self.links.append((self.href or "", text))
            self.href = None
            self.buf = []


def extract_links(page: str) -> list[tuple[str, str]]:
    p = _LinkTexts()
    p.feed(page)
    return p.links


_COURSE_RE = re.compile(r"course/view\.php\?id=(\d+)")
_FORUM_RE = re.compile(r"mod/forum/view\.php\?f=(\d+)")
_DISCUSS_RE = re.compile(r"mod/discuss/discuss\.php\?d=(\d+)")
_ASSIGN_RE = re.compile(r"mod/assign/view\.php\?id=(\d+)")

_DATE_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2})?\b"),
    re.compile(r"\b\d{1,2} \w+[çgilu]? ?\w* \d{4}\b"),
]


class ODTUClassClient:
    """Tek kullanıcılı ODTÜClass istemcisi. Login tembel (ilk çağrıda) yapılır."""

    def __init__(self, base_url: str, username: str, password: str,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._token: str | None = None
        self._userid: int | None = None
        self._mode: str | None = None
        self._courses: list[dict] | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ODTUClassClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def mode(self) -> str | None:
        return self._mode

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            resp = self._http.request(method, path, **kw)
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as e:
            raise ODTUUnavailableError(
                f"ODTÜClass zaman aşımına uğradı ({self.timeout}s): {type(e).__name__}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise ODTUUnavailableError(
                f"ODTÜClass beklenmedik durum kodu döndürdü: HTTP {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ODTUUnavailableError(
                f"ODTÜClass'a ulaşılamıyor ({type(e).__name__}). Site adresini veya ağı kontrol et."
            ) from e

    def ensure_login(self) -> None:
        if self._mode:
            return
        if self._try_ws_login():
            self._mode = "ws"
            return
        if self._try_form_login():
            self._mode = "web"
            return
        raise ODTUAuthError()

    def _try_ws_login(self) -> bool:
        resp = self._request(
            "POST",
            "/login/token.php",
            data={"username": self.username, "password": self.password,
                  "service": "moodle_mobile_app"},
        )
        try:
            data = resp.json()
        except ValueError:
            data = {}
        token = data.get("token")
        if token and isinstance(token, str):
            self._token = token
            info = self._call_ws("core_webservice_get_site_info")
            userid = info.get("userid")
            if not userid:
                return False
            self._userid = int(userid)
            return True
        return False

    def _call_ws(self, function: str, params: dict | list | None = None):
        if not self._token:
            raise ODTUClassError("Oturum açık değil.")
        flat = {"wstoken": self._token, "wsfunction": function,
                "moodlewsrestformat": "json"}
        if isinstance(params, dict):
            items = params.items()
        elif params:
            items = params
        else:
            items = []
        for k, v in items:
            if v is not None:
                flat[k] = v
        resp = self._request("POST", "/webservice/rest/server.php", data=flat)
        try:
            payload = resp.json()
        except ValueError as e:
            raise ODTUDataError(f"{function}: yanıtı JSON değil.") from e
        if isinstance(payload, dict) and payload.get("exception"):
            raise ODTUDataError(
                f"{function} başarısız: {payload.get('message') or payload.get('exception')}"
            )
        return payload

    def _try_form_login(self) -> bool:
        page = self._request("GET", "/login/index.php").text
        fields = parse_hidden_inputs(page)
        fields["username"] = self.username
        fields["password"] = self.password
        result = self._request("POST", "/login/index.php", data=fields)
        body = result.text
        if 'class="loginerrors"' in body or "invalidlogin" in result.url.path.lower():
            return False
        dash = self._request("GET", "/my/")
        if "/login/" in str(dash.url.path):
            return False
        return True

    def _ensure_courses(self) -> list[dict]:
        if self._courses is None:
            raw = self._call_ws("core_enrol_get_users_courses", {"userid": self._userid})
            courses = []
            for c in sorted(raw, key=lambda x: str(x.get("shortname", ""))):
                cid = int(c["id"])
                short = c.get("shortname") or c.get("displayname") or str(cid)
                courses.append({
                    "id": cid,
                    "kod": short,
                    "ad": c.get("fullname") or c.get("displayname") or short,
                    "url": f"{self.base_url}/course/view.php?id={cid}",
                })
            self._courses = courses
        return self._courses

    def get_today_schedule(self):
        """Bugünkü takvim olaylarını döndürür; veri yoksa None.

        ODTÜClass'ta haftalık ders çizelgesi standart olarak API'de yoktur;
        bu yüzden ajans haftalık programa kendi stub verisiyle devam eder.
        """
        self.ensure_login()
        events = self._call_ws("core_calendar_get_calendar_events", {}) or {}
        now = datetime.now()
        out = []
        for ev in events.get("events", []):
            try:
                start = datetime.fromtimestamp(int(ev["timestart"]))
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            dur = max(int(ev.get("timeduration") or 0), 0)
            start_ts = int(ev["timestart"])
            start = datetime.fromtimestamp(start_ts)
            end = datetime.fromtimestamp(start_ts + dur)
            if start.date() == now.date():
                out.append({
                    "ders": ev.get("name") or "",
                    "saat": start.strftime("%H:%M"),
                    "bitis": end.strftime("%H:%M"),
                    "yer": (ev.get("location") or ev.get("description") or "") and strip_html(
                        ev.get("location") or "", 80),
                    "tur": ev.get("eventtype") or "",
                })
        return {"gun": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma",
                        "Cumartesi", "Pazar"][now.weekday()],
                "dersler": out} if out else None

    def get_courses(self) -> list[dict]:
        self.ensure_login()
        if self._mode == "ws":
            return self._ensure_courses()
        return self._scrape_courses()

    def _scrape_courses(self) -> list[dict]:
        page = self._request("GET", "/my/").text
        seen: dict[int, str] = {}
        order: list[int] = []
        for href, text in extract_links(page):
            m = _COURSE_RE.search(href)
            if not m:
                continue
            cid = int(m.group(1))
            title = text or f"Ders {cid}"
            if cid not in seen:
                seen[cid] = title
                order.append(cid)
        return [{"id": cid, "kod": seen[cid], "ad": seen[cid],
                 "url": f"{self.base_url}/course/view.php?id={cid}"}
                for cid in order]

    def get_announcements(self, course_id=None) -> list[dict]:
        self.ensure_login()
        if course_id is not None:
            targets = [int(course_id)]
        else:
            targets = [c["id"] for c in self.get_courses()]
        names = {c["id"]: c["kod"] for c in self.get_courses()}
        out: list[dict] = []
        if self._mode == "ws":
            tuples = [(f"courseids[{i}]", cid) for i, cid in enumerate(targets)]
            forums = self._call_ws("mod_forum_get_forums_by_courses",
                                   tuples if tuples else {"courseids[]": []}) or []
            news = [f for f in forums
                    if f.get("type") == "news" or ANNOUNCEMENT_HINTS.search(f.get("name", ""))]
            if not news:
                news = forums[:1]
            for forum in news:
                fid = int(forum["id"])
                discussions = self._call_ws("mod_forum_get_forum_discussions",
                                            {"forumid": fid}) or {}
                for d in discussions.get("discussions", []) if isinstance(discussions, dict) else []:
                    did = int(d["id"])
                    out.append({
                        "id": did,
                        "course_id": forum.get("course"),
                        "course": names.get(forum.get("course"), ""),
                        "baslik": d.get("name") or d.get("subject") or "",
                        "yazar": d.get("userfullname") or "",
                        "tarih": _iso(d.get("created") or d.get("modified")
                                      or d.get("timemodified")),
                        "ozet": strip_html(d.get("message") or ""),
                        "url": f"{self.base_url}/mod/discuss/discuss.php?d={did}",
                    })
        else:
            for cid in targets:
                page = self._request("GET", f"/course/view.php?id={cid}").text
                links = extract_links(page)
                forums = [(m.group(1), t) for h, t in links
                          if (m := _FORUM_RE.search(h))]
                chosen = [(f, t) for f, t in forums if ANNOUNCEMENT_HINTS.search(t)] or forums[:1]
                for fid, _t in chosen:
                    fpage = self._request("GET", f"/mod/forum/view.php?f={fid}").text
                    seen: set[int] = set()
                    for href, text in extract_links(fpage):
                        m = _DISCUSS_RE.search(href)
                        if not m or int(m.group(1)) in seen:
                            continue
                        seen.add(int(m.group(1)))
                        dates = next((r.findall(text) for r in _DATE_RES if r.search(text)), [])
                        out.append({
                            "id": int(m.group(1)),
                            "course_id": cid,
                            "course": names.get(cid, str(cid)),
                            "baslik": text or f"Tartışma {m.group(1)}",
                            "tarih": dates[0] if dates else None,
                            "ozet": "",
                            "url": f"{self.base_url}/mod/discuss/discuss.php?d={m.group(1)}",
                        })
        out.sort(key=lambda a: a.get("tarih") or "", reverse=True)
        return out

    def get_assignments(self, course_id=None) -> list[dict]:
        self.ensure_login()
        targets = [int(course_id)] if course_id is not None \
            else [c["id"] for c in self.get_courses()]
        names = {c["id"]: c["kod"] for c in self.get_courses()}
        out: list[dict] = []
        if self._mode == "ws":
            tuples = [(f"courseids[{i}]", cid) for i, cid in enumerate(targets)]
            res = self._call_ws("mod_assign_get_assignments",
                                tuples if tuples else {"courseids[]": []}) or {}
            for c in res.get("courses", []):
                for a in c.get("assignments", []):
                    cmid = a.get("cmid") or a.get("id")
                    due = _iso(a.get("duedate"))
                    out.append({
                        "id": a.get("id"),
                        "course_id": c.get("id"),
                        "course": names.get(c.get("id"), ""),
                        "ad": a.get("name") or "",
                        "teslim": due,
                        "aciklama": strip_html(a.get("introhtml") or ""),
                        "url": f"{self.base_url}/mod/assign/view.php?id={cmid}",
                    })
        else:
            for cid in targets:
                page = self._request("GET", f"/course/view.php?id={cid}").text
                count = 0
                for href, text in extract_links(page):
                    m = _ASSIGN_RE.search(href)
                    if not m:
                        continue
                    aid = m.group(1)
                    apage = self._request("GET", f"/mod/assign/view.php?id={aid}").text
                    plain = strip_html(apage, 100000)
                    due = next((mm.group(0) for r in _DATE_RES
                                if (mm := r.search(plain))), None)
                    out.append({
                        "id": int(aid), "course_id": cid,
                        "course": names.get(cid, str(cid)),
                        "ad": text or f"Ödev {aid}", "teslim": due,
                        "aciklama": "", "url": f"{self.base_url}/mod/assign/view.php?id={aid}",
                    })
                    count += 1
                    if count >= 12:
                        break
        out.sort(key=lambda a: a.get("teslim") or "9999")
        return out

    def get_grades(self, course_id=None) -> list[dict]:
        self.ensure_login()
        targets = [int(course_id)] if course_id is not None \
            else [c["id"] for c in self.get_courses()]
        names = {c["id"]: c["kod"] for c in self.get_courses()}
        out: list[dict] = []
        for cid in targets:
            res = self._call_ws("gradereport_user_get_grade_items", {"courseid": cid})
            for ug in (res or {}).get("usergrades", []):
                for gi in ug.get("gradeitems", []):
                    grade = gi.get("gradeformatted")
                    if grade is None and gi.get("graderaw") is not None:
                        grade = str(gi["graderaw"])
                    out.append({
                        "course_id": cid,
                        "course": names.get(cid, str(cid)),
                        "kalem": gi.get("itemname") or "",
                        "not": grade if grade is not None else "-",
                    })
        return out
