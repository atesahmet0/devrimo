import { Chat } from "@/components/chat";

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Sohbet</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Devrimo asistanına sor — ders programı ve duyurular için araçları var.
        </p>
      </div>
      <Chat />
    </div>
  );
}
