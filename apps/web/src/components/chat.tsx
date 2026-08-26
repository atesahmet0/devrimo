"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Msg = { role: "user" | "assistant"; content: string };

export function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;

    setMessages((m) => [...m, { role: "user", content }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            data.reply ??
            data.detail ??
            data.error ??
            "Bir hata oluştu.",
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Bağlantı hatası." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col rounded-lg border">
      <div className="flex h-[26rem] flex-col gap-4 overflow-y-auto p-5">
        {messages.length === 0 && !busy ? (
          <div className="my-auto space-y-1 text-center">
            <p className="text-sm font-medium">Devrimo</p>
            <p className="text-xs text-muted-foreground">
              Ders programını, duyuruları sor. Örn: &ldquo;bugün derslerim
              ne?&rdquo;
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "self-end max-w-[75%] whitespace-pre-wrap rounded-md bg-secondary px-3 py-2 text-sm"
                  : "max-w-[85%] whitespace-pre-wrap rounded-md border px-3 py-2 text-sm"
              }
            >
              {m.content}
            </div>
          ))
        )}
        {busy && (
          <div className="text-xs text-muted-foreground" aria-live="polite">
            yazıyor…
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form
        className="flex gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Mesaj yaz…"
          disabled={busy}
        />
        <Button type="submit" disabled={busy || !input.trim()}>
          Gönder
        </Button>
      </form>
    </div>
  );
}
