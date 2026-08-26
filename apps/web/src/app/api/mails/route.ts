const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8300";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_URL}/api/mails`, { cache: "no-store" });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json(
      { error: "Agent'a ulaşılamıyor. Agent çalışıyor mu? (port 8300)" },
      { status: 502 }
    );
  }
}
