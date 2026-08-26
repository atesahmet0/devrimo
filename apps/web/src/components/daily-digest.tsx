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

type DigestData = {
  ozet: string;
  kaynaklar?: string[];
  adet?: Record<string, number>;
  tarih?: string;
};

export function DailyDigest() {
  const [digest, setDigest] = useState<DigestData | null>(null);

  useEffect(() => {
    fetch("/api/digest")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok || !data.ozet) throw new Error(data.error ?? "hata");
        return data as DigestData;
      })
      .then(setDigest)
      .catch(() => setDigest(null));
  }, []);

  // Agent kapalıysa veya özet alınamadıysa kart hiç gösterilmez.
  if (!digest?.ozet) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base font-medium">Günlük Özet</CardTitle>
          <Badge variant="secondary">LLM</Badge>
          {digest.adet ? (
            <span className="ml-auto text-xs text-muted-foreground">
              {digest.adet.duyuru ?? 0} duyuru ·{" "}
              {digest.adet.sayfa_degisikligi ?? 0} değişiklik ·{" "}
              {digest.adet.okunmamis_mail ?? 0} okunmamış mail
            </span>
          ) : null}
        </div>
        <CardDescription>
          Duyurular, sayfa değişiklikleri ve maillerin agent özeti.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {digest.ozet}
        </p>
      </CardContent>
    </Card>
  );
}
