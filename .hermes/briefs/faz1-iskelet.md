# Devrimo — Faz 1 Brief: Demo İskelet (auth'suz)

## Hedef
Çalışan bir demo web uygulaması: Next.js + shadcn/ui chat arayüzü, arka planda Python "agent core" (FastAPI) LLM tool-calling loop'u ile. Auth YOK — tek demo kullanıcısı. Basit, temiz, sırıtmayan UI.

## Zorunlu gereksinimler
1. **Monorepo yapı** (pnpm workspace):
   - `apps/web` — Next.js 15 (App Router, TypeScript)
   - `apps/agent` — Python 3.11 FastAPI servis
2. **UI kuralları (kesin):**
   - shadcn/ui kullan; **gradyan yok**, mor-mavi AI-estetiği yok, glow yok
   - Neutral tema (zinc/stone), düz renkler, bol whitespace
   - Sayfalar: `/` (chat), `/duyurular`, `/takvim`, `/mail` — hepsi basit liste/görünüm, şimdilik stub veriyle
3. **Agent core (`apps/agent`):**
   - FastAPI, `POST /api/chat` endpoint'i (JSON: {message} → {reply})
   - OpenAI-uyumlu API'ye bağlanır (base URL + key env'den: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`)
   - Tool-calling loop'u elle yaz (~150 satır, framework yok)
   - Şimdilik 2 stub tool: `get_announcements()` → sabit örnek duyurular, `get_today_schedule()` → sabit örnek program. Connector'lar sonraki fazda gerçek olacak.
   - SQLite (`data/devrimo.db`) sadece sohbet geçmişi için (`messages` tablosu).
4. **Web ↔ Agent:** Next.js route handler `/api/chat` proxy'si agent'e forward eder.
5. **README.md**: lean, OCX tarzı — kurulum, çalıştırma (`pnpm dev`, `uvicorn` komutu), yapı şeması.

## Kabul kriterleri (canlı doğrulama)
- `pnpm install && pnpm --filter web build` hatasız biter
- `cd apps/agent && uv run uvicorn main:app --port 8300` ayaklanır, `GET /healthz` 200 döner
- Web UI'dan mesaj yazınca agent'tan yanıt gelir (stub tool çağrısı çalışır: "bugün derslerim ne" sorusuna schedule tool'uyla cevap)
- `git log` temiz commit'ler içerir

## Kısıtlar
- Makine 1.9GB RAM — next dev yerine production build + start tercih edilir doğrulamada
- Test yazma YOK (ates istemedi); doğrulama canlı çalıştırma ile
