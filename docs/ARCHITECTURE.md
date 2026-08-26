# Devrimo — Mimari Karar Kaydı

## Karar
Hermes yerine **Agno-olmayan, kendi servisimiz**: "profile-per-user Hermes" yolu seçildi (ates kararı). UI: **Next.js + shadcn/ui**, gradyan YOK. Auth: **local Supabase** (email + şifre). Tüm kod **OpenCode'a delege edilir** (OCX 'ws' profili), Hermes sadece PM.

## Neden bu mimari
- Her kullanıcı = izole Hermes profili: kendi config'i, session'ları, memory'si, skills'leri.
- Multi-profile gateway: her profil kendi bot token'ı ile çalışabilir; web UI'dan `hermes --profile <user> run/chat` ile konuşulur.
- Connector'lar bağımsız Python paketi (`devrimo-connectors`) olarak yazılır → ileride multi-tenant Agno/Pydantic AI servise taşınabilir.

## Bileşenler
1. **Web UI** (`apps/web`): Next.js 15, shadcn/ui (neutral tema, düz renkler), Supabase auth (email+password). Chat ekranı → backend API → Hermes CLI çağrısı.
2. **API köprüsü** (`apps/api`, FastAPI): auth token doğrular, kullanıcı→profil eşler, `hermes --profile devrimo-u{uid} -p "<msg>"` çalıştırır, yanıtı stream eder.
3. **Connector paketi** (`packages/connectors`, saf Python):
   - odtuclass: Moodle login scrape (kurs listesi, duyurular, ödev deadline'ları, notlar)
   - takvim: ders programı (OIBS/Sais'te yoksa ODTÜClass takviminden)
   - sayfa-izleyici: metu.edu.tr URL listesi diff crawler + bildirim
   - webmail: IMAP mail.metu.edu.tr:993 (okuma, arama); gönderim onaylı
4. **Supabase (local)**: auth + users/profili eşleme tablosu + credential'lar (AES şifreli).

## Reddit araştırmasından gelen özellikler (r/ODTU kanıtına dayalı)
1. **Deadline kurtarıcısı** — ODTÜClass ödev/sınav tarihlerini topla, yaklaşanları proaktif bildir ("deadline" ve "kaçırdım" temaları sürekli).
2. **Duyuru tek kanal** — ODTÜClass + bölüm sayfası + oidb duyurularını tek akışta özetle (duyurular parçalı, öğrenci kaçırıyor).
3. **Ders çakışma kontrolü** — program çakışması soruları çok sık ("Schedule ders çakışması", lab saatleri portalda görünmüyor).
4. **Sınav/ODTUClass görünürlük sorunları** — "sınav odtuclass'ta gözükmüyor" tarzı postlar → asistan "bu derste sınav var mı / nerede" sorusunu cevaplamalı.
5. **Yemekhane menüsü** — günlük menü sorgusu + puanlama ilgisi yüksek.
6. **IS100/kur sınavları gibi küçük duyuruların kaçırılması.**

## Kullanılacak ekstra özellikler (v1'e dahil)
- Yaklaşan deadline panosu (7 gün) + sabah özeti
- Duyuru akışı + LLM özet
- Haftalık ders programı görünümü + çakışma uyarısı
- Webmail okunmamış özeti

## Kısıtlar
- Bu makine 1.9GB RAM → aynı anda TEK OpenCode agent; supabase + next dev birlikte dikkatli.
- Rootless docker kuruluyor (sudo yok) → supabase start bunu kullanacak.
