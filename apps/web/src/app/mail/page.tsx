import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { mails } from "@/lib/stub-data";

export default function MailPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mail</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Webmail özeti — okunmamışlar üstte. (stub veri)
        </p>
      </div>
      <Separator />
      <ul className="divide-y rounded-lg border">
        {mails.map((m) => (
          <li key={m.id} className="px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="max-w-[60%] truncate text-sm font-medium">
                {m.from}
              </span>
              {m.unread ? <Badge>okunmadı</Badge> : null}
              <span className="ml-auto text-xs text-muted-foreground">
                {m.date}
              </span>
            </div>
            <p className="mt-1 text-sm">{m.subject}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {m.preview}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
