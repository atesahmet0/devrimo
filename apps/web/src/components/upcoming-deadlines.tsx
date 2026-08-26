"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Deadline = {
  course: string;
  ad: string;
  teslim: string;
  kalan_gun?: number;
};

export function UpcomingDeadlines() {
  const [items, setItems] = useState<Deadline[] | null>(null);
  const [kaynak, setKaynak] = useState<string | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/deadlines")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "hata");
        setItems(data.veriler ?? []);
        setKaynak(data.kaynak ?? null);
      })
      .catch((e) => setHata(e.message));
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base font-medium">
            Yaklaşan Deadline&apos;lar
          </CardTitle>
          {kaynak && <Badge variant="outline">{kaynak}</Badge>}
        </div>
        <CardDescription>Önümüzdeki 7 günün teslimleri.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {hata ? (
          <p className="text-muted-foreground">Agent&apos;a ulaşılamıyor.</p>
        ) : items === null ? (
          <p className="text-muted-foreground">Yükleniyor…</p>
        ) : items.length === 0 ? (
          <p className="text-muted-foreground">
            7 gün içinde teslim yok.
          </p>
        ) : (
          items.map((d, i) => (
            <div key={i}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{d.ad}</span>
                <Badge variant="secondary">{d.course}</Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Son: {d.teslim}
                {typeof d.kalan_gun === "number"
                  ? ` · ~${d.kalan_gun} gün kaldı`
                  : ""}
              </p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
