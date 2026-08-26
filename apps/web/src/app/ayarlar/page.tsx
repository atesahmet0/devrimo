"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function StatusBadge({ ok, source }: { ok: boolean | null; source?: string }) {
  if (ok === null) return <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground"><AlertCircle className="size-3.5" /> Bağlı değil</span>;
  if (ok) return <span className="inline-flex items-center gap-1.5 rounded-full border bg-zinc-50 px-3 py-1 text-xs font-medium"><CheckCircle2 className="size-3.5" /> Bağlı {source ? `· ${source}` : ""}</span>;
  return <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs"><XCircle className="size-3.5" /> Hata</span>;
}

export default function AyarlarPage() {
  const [connections, setConnections] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const [email, setEmail] = useState({ host: "mail.metu.edu.tr", port: "993", username: "", password: "" });
  const [odtu, setOdtu] = useState({ url: "https://odtuclass.metu.edu.tr", username: "", password: "" });
  const [sais, setSais] = useState({ username: "", password: "" });

  async function refresh() {
    try {
      const r = await fetch("/api/connections", { cache: "no-store" });
      const j = await r.json();
      setConnections(j);
    } catch {}
  }

  useEffect(() => { refresh(); }, []);

  async function act(service: "email" | "odtuclass" | "sais", kind: "test" | "save" | "delete") {
    setLoading(true);
    setMsg(null);
    try {
      if (kind === "delete") {
        const r = await fetch(`/api/connections?service=${service}`, { method: "DELETE" });
        const j = await r.json();
        setMsg({ text: j.message, ok: j.ok });
        await refresh();
        return;
      }
      const body =
        service === "email" ? { service, host: email.host, port: Number(email.port) || 993, username: email.username, password: email.password } :
        service === "odtuclass" ? { service, url: odtu.url, username: odtu.username, password: odtu.password } :
        { service, username: sais.username, password: sais.password };
      const url = kind === "test" ? "/api/connections/test" : "/api/connections";
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json();
      setMsg({ text: j.message, ok: j.ok });
      if (kind === "save") await refresh();
    } catch {
      setMsg({ text: "Agent'a ulaşılamıyor.", ok: false });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Ayarlar</h1>
        <p className="mt-1 text-sm text-muted-foreground">Bağlantılarını yönet. Şifreler asla düz metin gösterilmez.</p>
      </div>

      {msg && <div className={`rounded-lg border px-4 py-3 text-sm ${msg.ok ? "bg-zinc-50" : "bg-white"}`}>{msg.text}</div>}

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">Email (IMAP)</CardTitle>
              <CardDescription>mail.metu.edu.tr — okunmamış mailler ve arama.</CardDescription>
            </div>
            <StatusBadge ok={connections?.email?.configured ?? null} source={connections?.email?.source} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2"><label className="mb-1.5 block text-xs font-medium">Host</label><Input value={email.host} onChange={e => setEmail(s => ({ ...s, host: e.target.value }))} /></div>
            <div><label className="mb-1.5 block text-xs font-medium">Port</label><Input value={email.port} onChange={e => setEmail(s => ({ ...s, port: e.target.value }))} /></div>
          </div>
          <div><label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label><Input value={email.username} onChange={e => setEmail(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" /></div>
          <div><label className="mb-1.5 block text-xs font-medium">Şifre</label><Input type="password" value={email.password} onChange={e => setEmail(s => ({ ...s, password: e.target.value }))} /></div>
          {connections?.email?.username_masked && <p className="text-xs text-muted-foreground">Kayıtlı: {connections.email.username_masked} · {connections.email.host}:{connections.email.port} · {connections.email.source}</p>}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => act("email", "test")} disabled={loading}>Test Et</Button>
            <Button onClick={() => act("email", "save")} disabled={loading}>Kaydet</Button>
            <Button variant="ghost" onClick={() => act("email", "delete")} disabled={loading}>Bağlantıyı Kes</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">ODTÜClass</CardTitle>
              <CardDescription>Dersler, duyurular, ödevler.</CardDescription>
            </div>
            <StatusBadge ok={connections?.odtuclass?.configured ?? null} source={connections?.odtuclass?.source} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div><label className="mb-1.5 block text-xs font-medium">URL</label><Input value={odtu.url} onChange={e => setOdtu(s => ({ ...s, url: e.target.value }))} placeholder="https://odtuclass.metu.edu.tr" /></div>
          <div><label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label><Input value={odtu.username} onChange={e => setOdtu(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" /></div>
          <div><label className="mb-1.5 block text-xs font-medium">Şifre</label><Input type="password" value={odtu.password} onChange={e => setOdtu(s => ({ ...s, password: e.target.value }))} /></div>
          {connections?.odtuclass?.username_masked && <p className="text-xs text-muted-foreground">Kayıtlı: {connections.odtuclass.username_masked} · {connections.odtuclass.url} · {connections.odtuclass.source}</p>}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => act("odtuclass", "test")} disabled={loading}>Test Et</Button>
            <Button onClick={() => act("odtuclass", "save")} disabled={loading}>Kaydet</Button>
            <Button variant="ghost" onClick={() => act("odtuclass", "delete")} disabled={loading}>Bağlantıyı Kes</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">METU SAIS</CardTitle>
              <CardDescription>https://student.metu.edu.tr/portal/ — en zengin veri kaynağı.</CardDescription>
            </div>
            <StatusBadge ok={connections?.sais?.configured ?? null} source={connections?.sais?.source} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div><label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label><Input value={sais.username} onChange={e => setSais(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" /></div>
          <div><label className="mb-1.5 block text-xs font-medium">Şifre</label><Input type="password" value={sais.password} onChange={e => setSais(s => ({ ...s, password: e.target.value }))} /></div>
          {connections?.sais?.username_masked && <p className="text-xs text-muted-foreground">Kayıtlı: {connections.sais.username_masked} · {connections.sais.source}</p>}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => act("sais", "test")} disabled={loading}>Test Et</Button>
            <Button onClick={() => act("sais", "save")} disabled={loading}>Kaydet</Button>
            <Button variant="ghost" onClick={() => act("sais", "delete")} disabled={loading}>Bağlantıyı Kes</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
