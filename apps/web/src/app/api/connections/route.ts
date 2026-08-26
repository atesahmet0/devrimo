import { NextRequest } from "next/server";

const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8300";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_URL}/api/connections`, { cache: "no-store" });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Agent'a ulaşılamıyor." }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.service) return Response.json({ error: "service gerekli" }, { status: 400 });
  try {
    const res = await fetch(`${AGENT_URL}/api/connections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Agent'a ulaşılamıyor." }, { status: 502 });
  }
}

export async function DELETE(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const service = searchParams.get("service");
  if (!service) return Response.json({ error: "service gerekli" }, { status: 400 });
  try {
    const res = await fetch(`${AGENT_URL}/api/connections/${encodeURIComponent(service)}`, { method: "DELETE" });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Agent'a ulaşılamıyor." }, { status: 502 });
  }
}
