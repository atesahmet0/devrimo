"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, XCircle, AlertCircle, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Service = "email" | "odtuclass" | "sais";
type Step = 1 | 2 | 3;

function StatusBadge({ ok, source }: { ok: boolean | null; source?: string }) {
  if (ok === null) return <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground"><AlertCircle className="size-3.5" /> Bağlı değil</span>;
  if (ok) return <span className="inline-flex items-center gap-1.5 rounded-full border bg-zinc-50 px-3 py-1 text-xs font-medium"><CheckCircle2 className="size-3.5" /> Bağlı {source ? `· ${source}` : ""}</span>;
  return <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs"><XCircle className="size-3.5" /> Hata</span>;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [connections, setConnections] = useState<any>(null);

  const [email, setEmail] = useState({ host: "mail.metu.edu.tr", port: "993", username: "", password: "" });
  const [odtu, setOdtu] = useState({ url: "https://odtuclass.metu.edu.tr", username: "", password: "" });
  const [sais, setSais] = useState({ username: "", password: "" });

  useEffect(() => {
    fetch("/api/connections").then(r => r.json()).then(setConnections).catch(() => {});
  }, []);

  async function testAndSave(service: Service) {
    setLoading(true);
    setMsg(null);
    try {
      const body =
        service === "email" ? { service, host: email.host, port: Number(email.port) || 993, username: email.username, password: email.password } :
        service === "odtuclass" ? { service, url: odtu.url, username: odtu.username, password: odtu.password } :
        { service, username: sais.username, password: sais.password };

      const res = await fetch("/api/connections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      if (data.ok) {
        setMsg({ type: "ok", text: data.message || "Bağlantı başarılı." });
        const c = await fetch("/api/connections").then(r => r.json()).catch(() => null);
        if (c) setConnections(c);
      } else {
        setMsg({ type: "err", text: data.message || "Bağlantı başarısız." });
      }
    } catch {
      setMsg({ type: "err", text: "Agent'a ulaşılamıyor." });
    } finally {
      setLoading(false);
    }
  }

  async function testOnly(service: Service) {
    setLoading(true);
    setMsg(null);
    try {
      const body =
        service === "email" ? { service, host: email.host, port: Number(email.port) || 993, username: email.username, password: email.password } :
        service === "odtuclass" ? { service, url: odtu.url, username: odtu.username, password: odtu.password } :
        { service, username: sais.username, password: sais.password };
      const res = await fetch("/api/connections/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      setMsg({ type: data.ok ? "ok" : "err", text: data.message });
    } catch {
      setMsg({ type: "err", text: "Agent'a ulaşılamıyor." });
    } finally {
      setLoading(false);
    }
  }

  const emailOk = connections?.email?.configured ?? null;
  const odtuOk = connections?.odtuclass?.configured ?? null;
  const saisOk = connections?.sais?.configured ?? null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Onboarding</h1>
        <p className="mt-1 text-sm text-muted-foreground">Devrimo&apos;yu hesaplarına bağla. Her adım atlanabilir — daha sonra Ayarlar&apos;dan değiştirebilirsin.</p>
      </div>

      <div className="flex items-center gap-2">
        {[1, 2, 3].map(n => (
          <button key={n} onClick={() => setStep(n as Step)} className={`flex h-8 w-8 items-center justify-center rounded-full border text-sm font-medium ${step === n ? "bg-zinc-900 text-white border-zinc-900" : "bg-white text-zinc-600 hover:bg-zinc-50"}`}>{n}</button>
        ))}
        <div className="ml-2 h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">{step}/3</span>
      </div>

      {msg && <div className={`rounded-lg border px-4 py-3 text-sm ${msg.type === "ok" ? "bg-zinc-50" : "bg-white border-zinc-200"}`}>{msg.text}</div>}

      {step === 1 && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">1 · Email (IMAP)</CardTitle>
                <CardDescription>mail.metu.edu.tr üzerinden okunmamış mailler ve arama.</CardDescription>
              </div>
              <StatusBadge ok={emailOk} source={connections?.email?.source} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="mb-1.5 block text-xs font-medium">Host</label>
                <Input value={email.host} onChange={e => setEmail(s => ({ ...s, host: e.target.value }))} placeholder="mail.metu.edu.tr" />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium">Port</label>
                <Input value={email.port} onChange={e => setEmail(s => ({ ...s, port: e.target.value }))} inputMode="numeric" />
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label>
              <Input value={email.username} onChange={e => setEmail(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium">Şifre</label>
              <Input type="password" value={email.password} onChange={e => setEmail(s => ({ ...s, password: e.target.value }))} />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => testOnly("email")} disabled={loading}>Test Et</Button>
              <Button onClick={() => testAndSave("email")} disabled={loading}>Kaydet {loading ? "…" : <ArrowRight className="size-4" />}</Button>
              <Button variant="ghost" onClick={() => setStep(2)}>Atla</Button>
            </div>
            {connections?.email?.username_masked && <p className="text-xs text-muted-foreground">Kayıtlı: {connections.email.username_masked} · {connections.email.source}</p>}
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">2 · ODTÜClass</CardTitle>
                <CardDescription>Dersler, duyurular, ödevler. URL dönem başına değişir.</CardDescription>
              </div>
              <StatusBadge ok={odtuOk} source={connections?.odtuclass?.source} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium">ODTÜClass URL</label>
              <Input value={odtu.url} onChange={e => setOdtu(s => ({ ...s, url: e.target.value }))} placeholder="https://odtuclass.metu.edu.tr" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label>
              <Input value={odtu.username} onChange={e => setOdtu(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium">Şifre</label>
              <Input type="password" value={odtu.password} onChange={e => setOdtu(s => ({ ...s, password: e.target.value }))} />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => testOnly("odtuclass")} disabled={loading}>Test Et</Button>
              <Button onClick={() => testAndSave("odtuclass")} disabled={loading}>Kaydet {loading ? "…" : <ArrowRight className="size-4" />}</Button>
              <Button variant="ghost" onClick={() => setStep(3)}>Atla</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">3 · METU SAIS</CardTitle>
                <CardDescription>Öğrenci portalı — en zengin veri kaynağı. <span className="text-muted-foreground">https://student.metu.edu.tr/portal/</span></CardDescription>
              </div>
              <StatusBadge ok={saisOk} source={connections?.sais?.source} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium">Kullanıcı adı</label>
              <Input value={sais.username} onChange={e => setSais(s => ({ ...s, username: e.target.value }))} placeholder="eXXXXXXX" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium">Şifre</label>
              <Input type="password" value={sais.password} onChange={e => setSais(s => ({ ...s, password: e.target.value }))} />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => testOnly("sais")} disabled={loading}>Test Et</Button>
              <Button onClick={() => testAndSave("sais")} disabled={loading}>Kaydet</Button>
              <Button variant="ghost" onClick={() => router.push("/")}>Bitir</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-between">
        <Button variant="ghost" disabled={step === 1} onClick={() => setStep((s => Math.max(1, s - 1) as Step)(step))}>Geri</Button>
        {step < 3 ? <Button variant="outline" onClick={() => setStep(s => Math.min(3, s + 1) as Step)}>İleri</Button> : <Button onClick={() => router.push("/")}>Sohbete git</Button>}
      </div>
    </div>
  );
}
