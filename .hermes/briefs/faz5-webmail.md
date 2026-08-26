# Devrimo — Faz 5 Brief: Webmail (IMAP) Connector

## Hedef
METU webmail (Roundcube, IMAP `mail.metu.edu.tr:993` SSL) okuma/arama connector'ı + `/mail` sayfasını gerçek veriye bağla. Reddit pain point: öğrenci mailini kaçırıyor (duyurular mail ile de geliyor).

## Gereksinimler
1. **`packages/connectors/webmail.py`:**
   - Python stdlib `imaplib` (bağımlılık ekleme), SSL
   - Env: `IMAP_HOST` (default mail.metu.edu.tr), `IMAP_PORT` (993), `MAIL_USERNAME`, `MAIL_PASSWORD` — boşsa stub fallback (mevcut /mail stub data)
   - Fonksiyonlar: `list_unread(limit=20)`, `search_mail(query, limit=10)` (FROM/SUBJECT/BODY), `get_mail(mail_id)` (tam gövde)
   - Şifre asla log/db'ye yazılmaz; hatalar Türkçe ve ayrık (auth hatası vs bağlantı hatası)
2. **Agent tool'ları:** `get_unread_mails()`, `search_emails(query)` wired; cache tablosuna özet yazımı.
3. **Web UI:** `/mail` sayfası agent `/api/mails` route'undan okur; agent kapalıysa mevcut stub'a düşer.
4. README: env değişkenleri + canlı moda geçiş.

## Kabul kriterleri
- Mock IMAP gerekmiyor: credential boşken stub fallback e2e çalışır; kod incelemesinde IMAP akışı doğru (python -c ile import + fonksiyon imzaları doğrulanır)
- Yanlış host/şifre senaryosu mock socket ile test edilir → temiz hata
- Chat "okunmamış maillerim" sorusuna cevap verir (stub modunda)
- pnpm build temiz

## Notlar
- Gönderme/yanıtlama bu fazda YOK (sadece okuma) — güvenlik onayı sonra
- Test yazma YOK
