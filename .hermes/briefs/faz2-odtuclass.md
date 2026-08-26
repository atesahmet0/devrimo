# Devrimo — Faz 2-3 Brief: ODTÜClass Connector + Gerçek Takvim

## Hedef
Stub tool'ları gerçek ODTÜClass (Moodle) verisiyle değiştir. Demo tek kullanıcı: credential'lar `.env`'den gelir (`ODTU_USERNAME`, `ODTU_PASSWORD`, `ODTUCLASS_URL` — örnek: https://odtuclass2026f.metu.edu.tr, dönem başına güncellenir).

## Gereksinimler
1. **Yeni paket `packages/connectors/odtuclass.py`** (saf Python, agent'ten bağımsız):
   - httpx ile Moodle web login: `login/token.php` dener; olmazsa form-login scraping (session cookie ile)
   - Fonksiyonlar: `get_courses()`, `get_announcements(course_id=None)`, `get_assignments(course_id=None)`, `get_grades(course_id=None)`
   - Timeout'lu, hata durumlarında açıklayıcı exception (şifre yanlış / site erişilemez ayrımı)
2. **Agent entegrasyonu:** stub `get_announcements`/`get_today_schedule` yerine:
   - `get_courses()` — kullanıcının bu dönemki dersleri
   - `get_announcements(course)` — duyurular (tümü veya ders bazlı)
   - `get_assignments()` — ödevler + teslim tarihleri
   - `get_today_schedule()` — ODTÜClass takviminden türet; mümkün değilse courses metadata'sından haftalık program çıkar
   - Credential yoksa mevcut stub'a fallback (demo kırılmasın)
3. **SQLite:** connector çıktıları `cache` tablosuna yazılsın (timestamp'li), agent "son çekilen" veriyi gösterebilsin.
4. README'ye yeni env değişkenleri ve çalıştırma farkları eklensin.

## Kabul kriterleri (canlı doğrulama)
- `ODTU_USERNAME/PASSWORD` verildiğinde: chat'ten "derslerim neler", "yeni duyurular", "ödevlerim ve tarihleri" sorularına GERÇEK ODTÜClass verisiyle cevap
- Yanlış şifre → temiz Türkçe hata mesajı, crash yok
- Credential boşken stub fallback çalışır
- pnpm build + uvicorn healthz + e2e chat doğrulanır

## Notlar
- ODTÜClass her dönem farklı subdomain — URL config'den
- Şifre ASLA log'a yazılmaz, SQLite'a yazılmaz
- Test yazma YOK; canlı doğrulama yeterli
