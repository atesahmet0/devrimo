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
├── docs/         # mimari karar kaydı
└── .hermes/      # brief'ler
```

- **web** `/` chat · `/duyurular` · `/takvim` · `/mail`. `/api/chat` route
  handler'ı istekleri agent'e proxy'ler (`AGENT_URL`, varsayılan
  `http://localhost:8300`).
- **agent** `POST /api/chat` (`{message}` → `{reply}`), `GET /healthz`.
  OpenAI-uyumlu API'ye env ile bağlanır; stub araçlar: `get_announcements`,
  `get_today_schedule`. Sohbet geçmişi `data/devrimo.db` (SQLite).

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
curl -s localhost:8300/healthz                       # {"status":"ok"}
curl -s localhost:3000/api/chat -H 'content-type: application/json' \
     -d '{"message":"bugün derslerim ne?"}'           # schedule aracı devrede
```

## Yol haritası

Faz 2: gerçek connector'lar (odtuclass, takvim, webmail), Supabase auth.
Karar kaydı: `docs/ARCHITECTURE.md`.
