"""Webmail (IMAP) connector — METU Roundcube okuma/arama, sadece stdlib.

``imaplib`` ile ``mail.metu.edu.tr:993`` (SSL) üzerinden salt-okunur erişim:
okunmamış listesi, Gönderen/Konu/Gövde araması, tam gövde. Mail GÖNDERME
bu fazda yok; bağlantılar readonly (EXAMINE) açılır, mesaj bayrağı
değişmez.

Credential'lar env'den gelir: IMAP_HOST (varsayılan mail.metu.edu.tr),
IMAP_PORT (varsayılan 993), MAIL_USERNAME, MAIL_PASSWORD. Kullanıcı adı
veya şifre boşsa connector stub veriye düşer — demo kırılmaz.

Şifre hiçbir yere loglanmaz / yazılmaz; hata mesajları Türkçe ve ayrıktır:
kimlik doğrulama hatası (WebmailAuthError) ile bağlantı hatası
(WebmailConnectionError) birbirine karışmaz.
"""

from __future__ import annotations

import email
import email.policy
import html
import imaplib
import os
import re
import ssl
from contextlib import contextmanager
from email.utils import parsedate_to_datetime

DEFAULT_HOST = "mail.metu.edu.tr"
DEFAULT_PORT = 993
DEFAULT_TIMEOUT = 15.0
PREVIEW_CHARS = 180


class WebmailError(Exception):
    """Connector temel hatası."""


class WebmailAuthError(WebmailError):
    """Kullanıcı adı veya şifre hatalı."""

    def __init__(self) -> None:
        super().__init__("Webmail girişi başarısız: kullanıcı adı veya şifre hatalı.")


class WebmailConnectionError(WebmailError):
    """Sunucuya ulaşılamadı / SSL veya zaman aşımı sorunu."""


class WebmailDataError(WebmailError):
    """Sunucuya ulaşıldı ama beklenmeyen / bozuk yanıt döndü."""


def load_config() -> tuple[str, int, str | None, str | None]:
    host = os.environ.get("IMAP_HOST") or DEFAULT_HOST
    port = int(os.environ.get("IMAP_PORT") or DEFAULT_PORT)
    return host, port, os.environ.get("MAIL_USERNAME"), os.environ.get("MAIL_PASSWORD")


def is_configured() -> bool:
    _host, _port, user, password = load_config()
    return bool(user and password)


def from_env(**kwargs) -> "WebmailClient | None":
    host, port, user, password = load_config()
    if not (user and password):
        return None
    return WebmailClient(host, port, user, password, **kwargs)


# Demo stub — apps/web/src/lib/stub-data.ts içindeki mails dizisinin aynası.
STUB_MAILS = [
    {
        "id": "m1",
        "kimden": "ODTUClass Duyuru <noreply@metu.edu.tr>",
        "konu": "[CENG 242] Yeni duyuru: Ödev 3",
        "tarih": "2026-08-25 14:12",
        "ozet": "Ödev 3 yayınlandı, son teslim tarihi için duyuruya bakın...",
        "okunmadi": True,
        "govde": "Merhaba,\n\nÖdev 3 yayınlandı, son teslim tarihi için duyuruya "
                 "bakın. Late policy: her gün %10.\n\nİyi çalışmalar.",
    },
    {
        "id": "m2",
        "kimden": "OIDB <oidb@metu.edu.tr>",
        "konu": "Kayıt yenileme hatırlatması",
        "tarih": "2026-08-24 09:03",
        "ozet": "Sayın İlgili Öğrenci, kayıt yenilemeniz 31 Ağustos'ta...",
        "okunmadi": True,
        "govde": "Sayın İlgili Öğrenci,\n\nKayıt yenilemeniz 31 Ağustos'ta "
                 "sona ermektedir. İşlemlerinizi tamamlayınız.",
    },
    {
        "id": "m3",
        "kimden": "Kütüphane <kutuphane@metu.edu.tr>",
        "konu": "İade hatırlatması: 2 kaynak",
        "tarih": "2026-08-21 16:45",
        "ozet": "Elinizdeki 2 kaynağın iade tarihi yaklaşmaktadır...",
        "okunmadi": False,
        "govde": "Elinizdeki 2 kaynağın iade tarihi yaklaşmaktadır. "
                 "Süre uzatma için kütüphane hesabınızı kullanabilirsiniz.",
    },
]


def stub_list_unread(limit: int = 20) -> list[dict]:
    unread_first = [m for m in STUB_MAILS if m["okunmadi"]] + \
        [m for m in STUB_MAILS if not m["okunmadi"]]
    return [dict(m) for m in unread_first[: max(1, limit)]]


_TR_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ş": "s", "ş": "s",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})


def _fold(text: str) -> str:
    """Türkçe karakter duyarsız küçük harf: 'KAYIT' == 'kayıt', 'ODEV' == 'ödev'."""
    return (text or "").translate(_TR_FOLD).lower()


def stub_search_mail(query: str, limit: int = 10) -> list[dict]:
    q = _fold(str(query or ""))
    if not q:
        raise WebmailDataError("Arama için bir anahtar kelime gerekli.")
    hits = [dict(m) for m in STUB_MAILS
            if q in _fold(m["konu"])
            or q in _fold(m["kimden"])
            or q in _fold(m["ozet"])
            or q in _fold(m["govde"])]
    return hits[: max(1, limit)]


def stub_get_mail(mail_id) -> dict:
    mid = str(mail_id).strip()
    for m in STUB_MAILS:
        if m["id"] == mid:
            return dict(m)
    raise WebmailDataError(f"'{mid}' numaralı mail bulunamadı (stub modda id'ler m1..m3).")


def _quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _fmt_date(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return value[:16]
    return dt.strftime("%Y-%m-%d %H:%M")


def strip_html(text: str, limit: int | None = PREVIEW_CHARS) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def _part_text(part) -> str:
    try:
        payload = part.get_content()
    except (LookupError, UnicodeDecodeError, AssertionError):
        raw = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            payload = raw.decode(charset, errors="replace")
        except LookupError:
            payload = raw.decode("utf-8", errors="replace")
    return payload if isinstance(payload, str) else ""


def _body_text(msg) -> str:
    plain: list[str] = []
    rich: list[str] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        if "attachment" in str(part.get("Content-Disposition") or ""):
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain":
            plain.append(_part_text(part))
        elif ctype == "text/html":
            rich.append(strip_html(_part_text(part), limit=None))
    return ("\n".join(plain) or "\n".join(rich)).strip()


class WebmailClient:
    """Tek kullanıcılı IMAP istemcisi. Her işlem kısa ömürlü bağlantı açar."""

    def __init__(self, host: str, port: int, username: str, password: str,
                 timeout: float = DEFAULT_TIMEOUT, mailbox: str = "INBOX",
                 ssl_context: ssl.SSLContext | None = None) -> None:
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.timeout = float(timeout)
        self.mailbox = mailbox
        self.ssl_context = ssl_context

    def _open(self) -> imaplib.IMAP4_SSL:
        try:
            imap = imaplib.IMAP4_SSL(self.host, self.port, timeout=self.timeout,
                                     ssl_context=self.ssl_context)
        except (OSError, TimeoutError) as e:
            raise WebmailConnectionError(
                f"Webmail sunucusuna ulaşılamıyor ({self.host}:{self.port}): "
                f"{type(e).__name__}. Ağ/VPN bağlantısını ve host/port ayarını kontrol et."
            ) from e
        except imaplib.IMAP4.abort as e:
            # Bağlantı kurulum sırasında koptu / sunucu protokol dışı kapandı.
            raise WebmailConnectionError(
                f"Webmail bağlantısı kurulamadı ({self.host}:{self.port}): "
                "sunucu bağlantıyı kapattı.") from e
        try:
            typ, _data = imap.login(self.username, self.password)
        except imaplib.IMAP4.abort as e:
            raise WebmailConnectionError(
                f"Webmail bağlantısı sunucu tarafından koptu ({self.host}:{self.port})."
            ) from e
        except imaplib.IMAP4.error as e:
            raise WebmailAuthError() from e
        if typ != "OK":
            raise WebmailAuthError()
        try:
            # RFC6855: sunucu desteklerse UTF-8 arama kelimeleri gönderilebilir.
            imap.enable("UTF8=ACCEPT")
        except imaplib.IMAP4.error:
            pass
        return imap

    @contextmanager
    def _session(self):
        imap = self._open()
        try:
            yield imap
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _select_readonly(self, imap) -> None:
        try:
            typ, _data = imap.select(self.mailbox, readonly=True)
        except imaplib.IMAP4.abort as e:
            raise WebmailConnectionError(
                f"Webmail bağlantısı koptu ({self.host}:{self.port}).") from e
        if typ != "OK":
            raise WebmailDataError(f"{self.mailbox} klasörü açılamadı.")

    def _uid_search(self, imap, *criteria: str) -> list[str]:
        """UID SEARCH; UTF-8 karakter seti reddedilirse ASCII ile tekrar dener."""
        try:
            typ, data = imap.uid("SEARCH", "CHARSET", "UTF-8", *criteria)
        except imaplib.IMAP4.error:
            typ, data = imap.uid("SEARCH", *criteria)
        if typ != "OK" or not data:
            return []
        raw = b" ".join(p for p in data if isinstance(p, bytes))
        uids = [u.decode("ascii", errors="ignore") for u in raw.split()]
        return [u for u in reversed(uids) if u.isdigit()]

    def _fetch_summary(self, imap, uid: str) -> dict:
        # Tek literal: mesajın ilk 16 KB'ı (başlık + gövde başı) → önizleme için yeterli.
        try:
            typ, data = imap.uid("FETCH", uid, "(FLAGS BODY.PEEK[]<0.16384>)")
        except imaplib.IMAP4.error as e:
            raise WebmailDataError(f"Mail {uid} alınamadı: {e}") from e
        if typ != "OK":
            raise WebmailDataError(f"Mail {uid} alınamadı.")
        parts = next((p for p in data if isinstance(p, tuple)), None)
        if parts is None:
            raise WebmailDataError(f"Mail {uid} bulunamadı.")
        flags = parts[0].decode("utf-8", errors="replace") if isinstance(parts[0], bytes) else ""
        msg = email.message_from_bytes(parts[1], policy=email.policy.default)
        text = _body_text(msg)
        return {
            "kimden": str(msg.get("From") or ""),
            "konu": str(msg.get("Subject") or ""),
            "tarih": _fmt_date(str(msg.get("Date") or "")),
            "ozet": strip_html(text),
            "okunmadi": "\\Seen" not in flags,
        }

    def list_unread(self, limit: int = 20) -> list[dict]:
        with self._session() as imap:
            self._select_readonly(imap)
            out: list[dict] = []
            for uid in self._uid_search(imap, "UNSEEN")[: max(1, int(limit))]:
                item = self._fetch_summary(imap, uid)
                item["id"] = uid
                out.append(item)
            return out

    def search_mail(self, query: str, limit: int = 10) -> list[dict]:
        query = str(query or "").strip()
        if not query:
            raise WebmailDataError("Arama için bir anahtar kelime gerekli.")
        with self._session() as imap:
            if not query.isascii() and not imap.utf8_enabled:
                raise WebmailDataError(
                    "Sunucu UTF-8 aramayı desteklemiyor; anahtar kelimeyi Türkçe "
                    "karakter (ç, ğ, ı, ö, ş, ü) olmadan deneyin.")
            self._select_readonly(imap)
            quoted = _quote(query)
            uids: set[str] = set()
            for crit in ("FROM", "SUBJECT", "BODY"):
                uids.update(self._uid_search(imap, crit, quoted))
            out: list[dict] = []
            for uid in sorted(uids, key=int, reverse=True)[: max(1, int(limit))]:
                item = self._fetch_summary(imap, uid)
                item["id"] = uid
                out.append(item)
            return out

    def get_mail(self, mail_id) -> dict:
        uid = str(mail_id).strip()
        if not uid.isdigit():
            raise WebmailDataError(
                f"Geçersiz mail kimliği: '{uid}' (canlı modda UID numarası gerekli).")
        with self._session() as imap:
            self._select_readonly(imap)
            try:
                typ, data = imap.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
            except imaplib.IMAP4.error as e:
                raise WebmailDataError(f"Mail {uid} alınamadı: {e}") from e
            if typ != "OK":
                raise WebmailDataError(f"Mail {uid} alınamadı.")
            parts = next((p for p in data if isinstance(p, tuple)), None)
            if parts is None:
                raise WebmailDataError(f"'{uid}' numaralı mail bulunamadı.")
            flags = parts[0].decode("utf-8", errors="replace") if isinstance(parts[0], bytes) else ""
            msg = email.message_from_bytes(parts[1], policy=email.policy.default)
            return {
                "id": uid,
                "kimden": str(msg.get("From") or ""),
                "konu": str(msg.get("Subject") or ""),
                "tarih": _fmt_date(str(msg.get("Date") or "")),
                "okunmadi": "\\Seen" not in flags,
                "govde": _body_text(msg),
            }


def list_unread(limit: int = 20) -> list[dict]:
    cli = from_env()
    if cli is None:
        return stub_list_unread(limit)
    return cli.list_unread(limit)


def search_mail(query: str, limit: int = 10) -> list[dict]:
    if not str(query or "").strip():
        raise WebmailDataError("Arama için bir anahtar kelime gerekli.")
    cli = from_env()
    if cli is None:
        return stub_search_mail(query, limit)
    return cli.search_mail(query, limit)


def get_mail(mail_id) -> dict:
    cli = from_env()
    if cli is None:
        return stub_get_mail(mail_id)
    return cli.get_mail(mail_id)
