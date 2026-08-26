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

## Yol haritası

Faz 3: takvim + webmail connector'ları, sayfa izleyici, Supabase auth.
Karar kaydı: `docs/ARCHITECTURE.md`.
