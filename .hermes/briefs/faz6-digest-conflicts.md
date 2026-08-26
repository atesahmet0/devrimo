# Devrimo — Faz 6 Brief: Duyuru Özeti + Ders Çakışma Uyarısı (Reddit'ten türetilen ekstralar)

## Hedef
r/ODTU'da en sık görülen iki pain point'in ürünleşmesi:
1. **Duyuru karmaşası** → tüm duyuların (ODTUClass + izlenen sayfalar + mail) tek akışta LLM özetiyle birleştirilmesi ("günlük özet").
2. **Ders çakışmaları** → programdaki saat çakışmalarının otomatik tespiti (lab saatleri portalda görünmüyor şikâyeti çok yaygın).

## Gereksinimler
1. **`packages/connectors/conflicts.py`:**
   - `detect_conflicts(schedule)`: aynı gün/saat diliminde çakışan dersleri bulur; lab+ders aynı kodun parçasıysa uyarı değil bilgi olarak işaretler
   - Çıktı: liste of {ders1, ders2, gun, aralık, tip: "cakisma"|"lab_bilgi"}
2. **Agent tool'ları:**
   - `get_daily_digest()`: announcements + page_changes + unread mails'i birleştirip LLM'e verilecek ham metni döndürür; agent bunu Türkçe kısa özete çevirir (sistem prompt'a kural ekle)
   - `check_schedule_conflicts()`: mevcut schedule'da detect_conflicts çalıştırır
3. **Web UI:**
   - `/duyurular` sayfasına "Günlük Özet" kartı: agent `/api/digest` route'u (LLM özetli), agent kapalıysa gizle
   - `/takvim` sayfasına çakışma uyarı bandı (varsa sarı renk, düz stil)
4. README'ye iki özelliğin kısa açıklaması.

## Kabul kriterleri (canlı doğrulama)
- Mock schedule ile çakışma tespiti doğru: aynı saat 2 ders = "cakisma"; ders+aynı kodun lab'ı = "lab_bilgi"
- `/api/digest` stub veriyle özet döner; chat "bugün ne kaçırabilirim" sorusuna digest tool'unu kullanıp cevap verir
- Chat "programımda çakışma var mı" sorusu conflict tool'unu çağırır
- UI bölümleri render olur; pnpm build temiz

## Notlar
- Test yazma YOK; canlı doğrulama yeterli
