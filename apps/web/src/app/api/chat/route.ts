const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8300";

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!body || typeof body.message !== "string" || !body.message.trim()) {
    return Response.json({ error: "message gerekli" }, { status: 400 });
  }

  try {
    const res = await fetch(`${AGENT_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: body.message }),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json(
      { error: "Agent'a ulaşılamıyor. Agent çalışıyor mu? (port 8300)" },
      { status: 502 }
    );
  }
}
