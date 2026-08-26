# Devrimo — Faz 4 Brief: Okul Sayfası İzleyici + Deadline Uyarısı

## Hedef
metu.edu.tr sayfalarını periyodik izleyen diff-crawler + yaklaşan ödev deadline'larını proaktif bildiren arka plan servisi. Reddit'ten doğrulanan pain point: duyuruları/duyuru kanallarını kaçırmak, ödev son gününü unutmak.

## Gereksinimler
1. **`packages/connectors/page_watcher.py`:**
   - URL listesi config/DB'de (`watched_pages` tablosu: url, selector(optional), last_hash, last_change)
   - Her kontrolde içerik hash'i (normalize edilmiş metin) karşılaştırılır; değişim varsa `page_changes` tablosuna yazılır
2. **`packages/connectors/deadlines.py`:**
   - ODTÜClass assignments verisinden yaklaşan deadline'ları süzer (7 gün penceresi)
3. **`apps/agent/watcher.py` (arka plan thread):**
   - 15 dakikada bir watched_pages kontrolü + deadlines kontrolü
   - Yeni değişiklik/deadline varsa SQLite `notifications` tablosuna yazar
4. **Agent tool'ları:** `check_updates()` → yeni sayfa değişiklikleri; `get_deadlines(days=7)` → yaklaşan teslimler; `get_notifications()` → okunmamış bildirimler. Chat bunlara erişebilmeli.
5. **Web UI:** `/duyurular` sayfasına "İzlenen Sayfa Değişiklikleri" bölümü + `/takvim` sayfasına yaklaşan deadline listesi (agent API'sinden okuyan basit route'lar).
6. **Varsayılan izleme listesi** (seed): oidb.metu.edu.tr/tr/duyurular, CENG bölüm duyuruları, registrar sayfası — kolayca genişletilebilir.

## Kabul kriterleri (canlı doğrulama)
- Watcher thread ajanla birlikte başlar, healthz'de görünür
- Bir izlenen sayfa test amaçlı değiştirildiğinde (mock server) `check_updates` değişikliği raporlar
- Mock assignment ile `get_deadlines` doğru süzme yapar
- Web UI bölümleri render eder; e2e chat "yaklaşan ödevler" sorusuna cevap verir
- pnpm build temiz

## Notlar
- Polite crawling: timeout, retry yok, tek istek/sayfa/döngü
- Test yazma YOK
