"use client";

import { useEffect, useState } from "react";

type Conflict = {
  ders1: string;
  ders2: string;
  gun: string;
  aralik: string;
  tip: string;
};

export function ScheduleConflicts() {
  const [items, setItems] = useState<Conflict[] | null>(null);

  useEffect(() => {
    fetch("/api/conflicts")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "hata");
        setItems(data.veriler ?? []);
      })
      .catch(() => setItems([]));
  }, []);

  // Çakışma yoksa veya agent'a ulaşılamıyorsa bant gösterilmez.
  if (!items?.length) return null;

  return (
    <div
      role="alert"
      className="rounded-md border border-yellow-500 bg-yellow-50 p-4 text-sm text-yellow-900 dark:border-yellow-500/60 dark:bg-yellow-950/40 dark:text-yellow-100"
    >
      <p className="font-medium">Programda saat çakışması var</p>
      <ul className="mt-2 space-y-1">
        {items.map((c, i) => (
          <li key={i}>
            <span className="font-medium">
              {c.gun} {c.aralik}
            </span>{" "}
            — {c.ders1} ↔ {c.ders2}
            {c.tip === "lab_bilgi" ? (
              <span className="text-yellow-700 dark:text-yellow-300">
                {" "}
                (aynı dersin lab saati — bilgi)
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
