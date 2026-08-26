# Devrimo

ODTÜ öğrencisi için asistan: Next.js + shadcn/ui web arayüzü, arkada Python
(FastAPI) agent core — elle yazılmış tool-calling loop'u ile. Faz 1 demo:
auth yok, tek kullanıcı, stub connector'lar.

## Yapı

```
devrimo/
├── apps/
│   ├── web/      # Next.js 15 (App Router, TS, shadcn/ui, tailwind v4)
│   └── agent/    # FastAPI + tool-calling loop + SQLite sohbet geçmişi
├── packages/
│   └── connectors/  # saf Python connector'lar (odtuclass)
├── docs/         # mimari karar kaydı
└── .hermes/      # brief'ler
```

- **web** `/` chat · `/duyurular` · `/takvim` · `/mail`. `/api/chat` route
  handler'ı istekleri agent'e proxy'ler (`AGENT_URL`, varsayılan
  `http://localhost:8300`).
- **agent** `POST /api/chat` (`{message}` → `{reply}`), `GET /healthz`.
  OpenAI-uyumlu API'ye env ile bağlanır. Sohbet geçmişi ve connector
  önbelleği `data/devrimo.db` (SQLite).
- **packages/connectors** saf Python connector'lar (`odtuclass.py`: Moodle
  login — `login/token.php`, olmazsa form-login scraping — üzerinden
  `get_courses / get_announcements / get_assignments / get_grades /
  get_today_schedule`).

## Kurulum

Gerekenler: Node 20+, pnpm 10+, Python 3.11+, [uv](https://docs.astral.sh/uv/).

```sh
pnpm install          # root'ta
uv sync               # apps/agent içinde
cp .env.example .env  # OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL doldur
```

## Çalıştırma

```sh
# 1) agent (8300)
cd apps/agent && uv run uvicorn main:app --port 8300

# 2) web (3000)
pnpm dev              # geliştirme
# veya
pnpm build && pnpm start   # production
```

## Doğrulama

```sh
curl -s localhost:8300/healthz                       # {"status":"ok","odtuclass":false}
curl -s localhost:3000/api/chat -H 'content-type: application/json' \
     -d '{"message":"bugün derslerim ne?"}'           # schedule aracı devrede
```

## ODTÜClass bağlama (gerçek veri)

`.env` içine credential gir; agent yeniden başlatınca araçlar gerçek
ODTÜClass (Moodle) verisiyle cevap verir:

```sh
ODTUCLASS_URL=https://odtuclass2026f.metu.edu.tr   # dönem başına güncellenir
ODTU_USERNAME=eXXXXXXX
ODTU_PASSWORD=...
```

- `healthz` çıktısındaki `"odtuclass":true` ayarın okunduğunu gösterir.
- Giriş: önce mobil servis token'ı (`login/token.php`), o kapalıysa web
  form-login scraping denenir. Yanlış şifre → Türkçe hata mesajı, crash yok;
  site erişilemezse ayrıca "ulaşılamıyor" mesajı verilir.
- Connector çıktıları SQLite `cache` tablosuna timestamp'le yazılır; canlı
  çekim başarısız olursa agent son bilinen veriyi "son güncelleme" notuyla
  gösterir.
- Credential boşken her şey demo stub'ıyla çalışır — demo kırılmaz.
- Şifre hiçbir yere loglanmaz, SQLite'a yazılmaz.

## Sayfa izleyici + deadline uyarısı (Faz 4)

Agent ile birlikte bir arka plan thread'i başlar (`apps/agent/watcher.py`):
varsayılan izleme listesindeki metu.edu.tr sayfalarını (OIDB duyurular,
CENG bölüm duyuruları, registrar) her döngüde hash-diff ile tarar ve
ODTÜClass assignment'larından yaklaşan deadline'ları süzer. Yeni bulgu
SQLite `notifications` tablosuna yazılır (dedupe'lu, tekrar bildirilmez).

- `GET /healthz` çıktısındaki `"watcher"` alanı thread durumunu gösterir
  (`canli`, `dongu`, `son_tarama`, `son_hata`, `aralik_dk`).
- Agent uçları: `check_updates` / `get_deadlines` / `get_notifications`
  tool'ları ve `GET /api/updates`, `GET /api/deadlines?days=7`,
  `GET /api/notifications` route'ları.
- Web: `/duyurular` "İzlenen Sayfa Değişiklikleri", `/takvim`
  "Yaklaşan Deadline'lar" bölümü agent API'sinden okur.
- Ayar (env): `WATCHER_INTERVAL_SECS` (varsayılan 900), 
  `DEADLINE_WINDOW_DAYS` (varsayılan 7). Polite crawling: sayfa başına
  tek istek/döngü, timeout var, retry yok.

## Webmail bağlama (Faz 5)

`packages/connectors/webmail.py`, METU webmail'e (Roundcube, IMAP SSL)
**salt-okunur** bağlanır: okunmamış mailler, Gönderen/Konu/Gövde araması,
tam gövde. Mail gönderme/yanıtlama bu fazda yok; bağlantılar EXAMINE
(readonly) ile açılır, mesaj bayrağı değişmez.

```sh
IMAP_HOST=mail.metu.edu.tr   # varsayılan
IMAP_PORT=993                # varsayılan
MAIL_USERNAME=eXXXXXXX
MAIL_PASSWORD=...
```

- Credential boşken connector demo stub verisine düşer — `/mail` sayfası
  ve chat kırılmaz.
- Canlı moda geçiş: `.env` içine `MAIL_USERNAME` / `MAIL_PASSWORD` gir,
  agent'ı yeniden başlat (`healthz` çıktısında `"webmail":true`).
- Agent uçları: `get_unread_mails` / `search_emails` tool'ları ve
  `GET /api/mails?limit=20` route'u. Sonuçlar SQLite `cache` tablosuna
  yazılır; canlı çekim başarısız olursa son bilinen mailler gösterilir.
- Web: `/mail` agent `/api/mails`'ten okur; agent kapalıysa yerel stub'a
  düşer (kaynak rozetinden görünür).
- Chat örnekleri: "okunmamış maillerim var mı?", "maillerde ödev ara".
- Hatalar Türkçe ve ayrıktır: yanlış şifre → "Webmail girişi başarısız",
  host/ağ sorunu → "Webmail sunucusuna ulaşılamıyor". Şifre hiçbir yere
  loglanmaz, SQLite'a yazılmaz.
- Türkçe karakterli arama için sunucu UTF-8 (RFC6855) desteklemiyorsa
  connector açıklayıcı hata döner; ASCII sorgularda sunucu tarafında
  CHARSET denenir, reddedilirse düz SEARCH ile devam edilir.

## Günlük özet + ders çakışması uyarısı (Faz 6)

r/ODTU'daki iki yaygın şikâyetin ürünleşmesi:

**Günlük duyuru özeti.** Agent, ODTÜClass duyuruları + izlenen sayfa
değişiklikleri + okunmamış mailleri tek ham akışta birleştirir
(`get_daily_digest` tool'u) ve LLM kısa Türkçe özete çevirir.

- Web: `/duyurular` sayfasındaki **"Günlük Özet"** kartı agent'in
  `GET /api/digest` (LLM özetli) ucundan okur; agent kapalıysa kart
  hiç gösterilmez.
- Chat örnekleri: "bugün ne kaçırabilirim?", "günün özeti".

**Ders çakışma tespiti.** `packages/connectors/conflicts.py`,
`detect_conflicts(schedule)` ile aynı gün/saat diliminde kesişen dersleri
bulur: farklı iki ders kesişiyorsa `cakisma`, aynı ders kodunun lab saati
kesişiyorsa uyarı değil bilgi olarak `lab_bilgi` işaretlenir (portalda lab
saatlerinin görünmemesi sorununa karşı).

- Agent: `check_schedule_conflicts` tool'u ve `GET /api/conflicts` route'u.
- Web: `/takvim` sayfasında çakışma varsa sarı, düz stil uyarı bandı.
- Chat örneği: "programımda çakışma var mı?"

## Onboarding / Ayarlar (Faz 7)

Üç kaynak için bağlantı: **Email (IMAP)** · **ODTÜClass** · **METU SAIS** (`https://student.metu.edu.tr/portal/#/`).

- **SAIS connector** `packages/connectors/sais.py` — `httpx` + form-login, `SAIS_USERNAME` / `SAIS_PASSWORD` (boşsa stub fallback, demo kırılmaz). Fonksiyonlar: `get_student_info`, `get_schedule`, `get_transcript`, `get_announcements`.
- **Credential saklama:** onboarding'den girilenler SQLite `credentials` tablosuna yazılır, env'yi override eder (kalıcı, restart sonrası da kalır). `GET /api/connections` sadece `username_masked` döner, şifre asla dönülmez.
- **Agent API:** `GET /api/connections` (masked), `POST /api/connections` (kaydet + test), `POST /api/connections/test` (sadece test), `DELETE /api/connections/{service}`, `GET /healthz` → `{sais: bool}`.
- **Chat:** SAIS tool'ları `get_sais_info`, `get_sais_schedule`, `get_sais_transcript` (stub modunda da çalışır). `get_today_schedule` önceliği SAIS → ODTÜClass → stub.
- **Web:** `/onboarding` 3 adımlı wizard (Test + Kaydet + Atla her adımda, neutral shadcn + lucide), `/ayarlar` üç kartlı yönetim sayfası (Test / Kaydet / Bağlantıyı Kes). Nav'da `Onboarding` ve `Ayarlar` linkleri.

```sh
SAIS_USERNAME=eXXXXXXX
SAIS_PASSWORD=...
```

## Yol haritası

Supabase auth, takvim connector'ı, webmail gönderme (güvenlik onayı
sonrası). Karar kaydı: `docs/ARCHITECTURE.md`.
