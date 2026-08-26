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

type Update = { url: string; etiket: string; ozet: string; tarih: string };

export function WatchedUpdates() {
  const [updates, setUpdates] = useState<Update[] | null>(null);
  const [izlenen, setIzlenen] = useState<number | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/updates")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "hata");
        setUpdates(data.veriler ?? []);
        setIzlenen(data.izlenen_sayfa ?? null);
      })
      .catch((e) => setHata(e.message));
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base font-medium">
            İzlenen Sayfa Değişiklikleri
          </CardTitle>
          {izlenen !== null && (
            <Badge variant="outline">{izlenen} sayfa izleniyor</Badge>
          )}
        </div>
        <CardDescription>
          Arka plan izleyicinin metu.edu.tr sayfalarında yakaladığı
          değişiklikler.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {hata ? (
          <p className="text-muted-foreground">İzleyiciye ulaşılamıyor.</p>
        ) : updates === null ? (
          <p className="text-muted-foreground">Kontrol ediliyor…</p>
        ) : updates.length === 0 ? (
          <p className="text-muted-foreground">
            Henüz değişiklik yakalanmadı.
          </p>
        ) : (
          updates.map((u, i) => (
            <div key={i}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{u.etiket || u.url}</span>
                <span className="text-xs text-muted-foreground">
                  {u.tarih}
                </span>
              </div>
              {u.ozet ? (
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {u.ozet}
                </p>
              ) : null}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
