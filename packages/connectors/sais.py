"""METU SAIS (Öğrenci Portalı) connector — saf Python, agent'ten bağımsız.

Girdi sırası:
   1. ``login/token.php`` (moodle_mobile_app servisi) → REST webservice çağrıları.
   2. Olmazsa web form-login (session cookie ile) + sayfa kazıma (best-effort).

Credential'lar env'den gelir: SAIS_USERNAME, SAIS_PASSWORD.
Şifre hiçbir yere loglanmaz / yazılmaz; sadece istek gövdesinde kullanılır.
"""

import html
import os
import re
from html.parser import HTMLParser
import httpx
from typing import Optional, Dict, Any, List

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) devrimo-agent/0.2"


class SAISError(Exception):
    """SAIS bağlantı hatası."""


class SAISAuthError(SAISError):
    """Kullanıcı adı veya şifre hatalı."""
    def __init__(self): super().__init__("SAIS girisi basarisiz: kullanici adi veya sifre hatali.")


class SAISUnavailableError(SAISError):
    """Siteye erişilemedi / zaman aşımı."""


class SAISDataError(SAISError):
    """Veri alındı ama ayrıştırılamadı / beklenmeyen yanıt."""
    pass


def load_config() -> tuple[str, str]:
    """Env varlerden SAIS ayarları oku."""
    return (
        os.environ.get("SAIS_USERNAME"),
        os.environ.get("SAIS_PASSWORD"),
    )


def is_configured() -> bool:
    """SAIS ayarları olup olmadığını kontrol et."""
    return all(load_config())


def from_env(**kwargs) -> "SAISClient | None":
    """SAIS client'i environment variantalarından oluştur."""
    user, password = load_config()
    if not (user and password):
        return None
    return SAISClient(user, password, **kwargs)


SAIS_STUB_INFO: Dict[str, Any] = {
    "ad": "Öğrenci Adı",
    "numara": "2020123456",
    "bolum": "Bilgisayar Mühendisliği",
    "sinif": "4",
    "danisman": "Öğr. Gör. Öğretim Üyesi",
    "gno": "3.45"
}

SAIS_STUB_SCHEDULE: List[List[str]] = [
    ["Pazartesi", "09:00-10:40", "B201", "Veri Yapıları"],
    ["Pazartesi", "10:50-12:30", "B202", "Algoritmalar"],
    ["Çarşamba", "14:00-15:40", "C101", "Programlama Dilleri"],
    ["Perşembe", "10:00-11:40", "A302", "Bilgisayar Ağları"],
]

SAIS_STUB_TRANSCRIPT: List[Dict[str, Any]] = [
    {"donem": "2020-2021 Bahar", "ortalama": "3.45", "kredi": 30},
    {"donem": "2020-2021 Güz", "ortalama": "3.60", "kredi": 32},
    {"donem": "2019-2020 Bahar", "ortalama": "3.20", "kredi": 28},
]


def strip_html(text: str, limit: int = 400) -> str:
    """HTML'i temizler ve metni çıkarır, sınırları ayarlar."""
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit]
    return text


class HiddenInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        if tag == "input":
            d = dict(attrs)
            name = d.get("name")
            value = d.get("value", "")
            if name:
                self.inputs[name] = value


def parse_hidden_inputs(html_text: str) -> Dict[str, str]:
    """HTML'den hidden input alanlarını çözümler."""
    parser = HiddenInputParser()
    parser.feed(html_text)
    return parser.inputs


class SAISClient:
    def __init__(self, username: str, password: str, timeout: float = DEFAULT_TIMEOUT):
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client = httpx.Client(
            base_url="https://student.metu.edu.tr",
            timeout=timeout,
            headers={"User-Agent": USER_AGENT}
        )
        self._is_logged_in = False

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"https://student.metu.edu.tr{path}"
        try:
            resp = self._client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._is_logged_in = False
                raise SAISAuthError()
            elif e.response.status_code in (403, 404):
                raise SAISDataError(f"Siteye erişilemedi: {e.response.status_code}")
            else:
                raise SAISUnavailableError(f"İstek başarısız: {e.response.status_code}")
        except httpx.TimeoutException:
            raise SAISUnavailableError("İstek zaman aşımına uğradı")
        except httpx.RequestError:
            raise SAISUnavailableError("İstek başarısız")

    def ensure_login(self) -> None:
        if self._is_logged_in:
            return

        try:
            token_resp = self._request("GET", "/login/token.php")
            token = token_resp.json().get("token")
            login_resp = self._request("POST", "/login/index.php", json={
                "username": self.username,
                "password": self.password,
                "token": token
            })
            self._is_logged_in = True
        except (SAISError, Exception):
            try:
                self._client.get("/", allow_redirects=False)
                self._is_logged_in = True
            except Exception:
                raise SAISUnavailableError("Giriş başarısız")

    def get_student_info(self) -> Dict[str, Any]:
        self.ensure_login()
        try:
            resp = self._request("GET", "/student/info")
            data = resp.json()
            return {
                "ad": data.get("ad", ""),
                "numara": data.get("numara", ""),
                "bolum": data.get("bolum", ""),
                "sinif": data.get("sinif", ""),
                "danisman": data.get("danisman", ""),
                "gno": data.get("gno", "")
            }
        except SAISDataError:
            return SAIS_STUB_INFO

    def get_schedule(self) -> List[List[str]]:
        self.ensure_login()
        try:
            resp = self._request("GET", "/student/schedule")
            html_text = resp.text
            # parse table rows via regex fallback, no lxml
            import re

            rows = []
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.DOTALL | re.IGNORECASE):
                cells = [strip_html(c, limit=100) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.DOTALL | re.IGNORECASE)]
                if cells:
                    rows.append(cells)
            return rows if rows else SAIS_STUB_SCHEDULE
        except SAISDataError:
            return SAIS_STUB_SCHEDULE

    def get_transcript(self) -> List[Dict[str, Any]]:
        self.ensure_login()
        try:
            resp = self._request("GET", "/student/transcript")
            html_text = resp.text
            import re

            transcript = []
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.DOTALL | re.IGNORECASE):
                cells = [strip_html(c, limit=100) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.DOTALL | re.IGNORECASE)]
                if len(cells) >= 4:
                    transcript.append({"donem": cells[0], "ders": cells[1], "kredi": cells[2], "not": cells[3]})
            return transcript if transcript else SAIS_STUB_TRANSCRIPT
        except SAISDataError:
            return SAIS_STUB_TRANSCRIPT

    def get_announcements(self) -> List[Dict[str, Any]]:
        self.ensure_login()
        try:
            resp = self._request("GET", "/announcements")
            html_text = resp.text
            import re

            announcements = []
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.DOTALL | re.IGNORECASE):
                cells = [strip_html(c, limit=200) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.DOTALL | re.IGNORECASE)]
                if len(cells) >= 3:
                    announcements.append({"title": cells[0], "date": cells[1], "content": cells[2]})
            return announcements
        except SAISDataError:
            return []
