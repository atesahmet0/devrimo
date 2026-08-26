import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { UpcomingDeadlines } from "@/components/upcoming-deadlines";
import { schedule } from "@/lib/stub-data";

const days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"];

export default function TakvimPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Takvim</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Haftalık ders programı. (stub veri)
        </p>
      </div>
      <Separator />
      <UpcomingDeadlines />
      <p className="text-sm font-medium text-muted-foreground">
        Haftalık ders programı
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {days.map((day) => {
          const slots = schedule.filter((s) => s.day === day);
          return (
            <Card key={day}>
              <CardHeader>
                <CardTitle className="text-base font-medium">{day}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {slots.length === 0 ? (
                  <p className="text-muted-foreground">Ders yok</p>
                ) : (
                  slots.map((s) => (
                    <div key={s.id}>
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-medium">{s.course}</span>
                        <Badge variant="outline">{s.code}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {s.start}–{s.end} · {s.place}
                      </p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
