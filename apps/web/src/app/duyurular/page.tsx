import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { WatchedUpdates } from "@/components/watched-updates";
import { announcements } from "@/lib/stub-data";

export default function DuyurularPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Duyurular</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          ODTÜClass, bölüm sayfası ve OIDB — tek akışta. (stub veri)
        </p>
      </div>
      <Separator />
      <WatchedUpdates />
      <div className="space-y-4">
        {announcements.map((a) => (
          <Card key={a.id}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{a.source}</Badge>
                {a.course ? (
                  <Badge variant="outline">{a.course}</Badge>
                ) : null}
                <span className="ml-auto text-xs text-muted-foreground">
                  {a.date}
                </span>
              </div>
              <CardTitle className="text-base font-medium">
                {a.title}
              </CardTitle>
              <CardDescription>{a.summary}</CardDescription>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </div>
    </div>
  );
}
