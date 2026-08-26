"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { mails as stubMails } from "@/lib/stub-data";

type Row = {
  id: string;
  from: string;
  subject: string;
  date: string;
  preview: string;
  unread: boolean;
};

type ApiMail = {
  id?: string;
  kimden?: string;
  konu?: string;
  tarih?: string | null;
  ozet?: string;
  okunmadi?: boolean;
};

function toRows(items: ApiMail[]): Row[] {
  return items.map((m, i) => ({
    id: m.id ?? `api-${i}`,
    from: m.kimden ?? "",
    subject: m.konu ?? "",
    date: m.tarih ?? "",
    preview: m.ozet ?? "",
    unread: Boolean(m.okunmadi),
  }));
}

const stubRows: Row[] = [...stubMails]
  .sort((a, b) => Number(b.unread) - Number(a.unread))
  .map((m) => ({
    id: m.id,
    from: m.from,
    subject: m.subject,
    date: m.date,
    preview: m.preview,
    unread: m.unread,
  }));

export function MailList() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [kaynak, setKaynak] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/mails")
      .then(async (res) => {
        if (!res.ok) throw new Error("agent yok");
        const data = await res.json();
        const items = toRows(data.veriler ?? []);
        if (!alive) return;
        setRows(items);
        setKaynak(data.kaynak ?? "agent");
      })
      .catch(() => {
        // Agent kapalıysa mevcut stub veriye düş.
        if (alive) {
          setRows(stubRows);
          setKaynak("stub");
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Kaynak:</span>
        {kaynak === "webmail" ? (
          <Badge variant="outline">webmail (IMAP)</Badge>
        ) : kaynak === "demo-stub" ? (
          <Badge variant="outline">agent · demo-stub</Badge>
        ) : kaynak === "stub" ? (
          <Badge variant="outline">yerel stub (agent kapalı)</Badge>
        ) : (
          <span>kontrol ediliyor…</span>
        )}
      </div>
      <ul className="divide-y rounded-lg border">
        {rows?.map((m) => (
          <li key={m.id} className="px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="max-w-[60%] truncate text-sm font-medium">
                {m.from}
              </span>
              {m.unread ? <Badge>okunmadı</Badge> : null}
              <span className="ml-auto text-xs text-muted-foreground">
                {m.date}
              </span>
            </div>
            <p className="mt-1 text-sm">{m.subject}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {m.preview}
            </p>
          </li>
        ))}
      </ul>
      {rows !== null && rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Okunmamış mail yok.</p>
      ) : null}
    </div>
  );
}
