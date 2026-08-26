import { Separator } from "@/components/ui/separator";
import { MailList } from "@/components/mail-list";

export default function MailPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mail</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Webmail özeti — okunmamışlar üstte. METU IMAP salt-okunur bağlanır.
        </p>
      </div>
      <Separator />
      <MailList />
    </div>
  );
}
