import type { Metadata } from "next";
import "./globals.css";
import { MainNav } from "@/components/main-nav";

export const metadata: Metadata = {
  title: "Devrimo",
  description: "Öğrenci asistanı",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body className="flex min-h-screen flex-col">
        <header className="border-b">
          <div className="mx-auto flex h-14 w-full max-w-4xl items-center gap-8 px-6">
            <span className="text-sm font-semibold tracking-tight">Devrimo</span>
            <MainNav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
          {children}
        </main>
        <footer className="border-t py-4">
          <div className="mx-auto w-full max-w-4xl px-6 text-xs text-muted-foreground">
            Demo — tek kullanıcı, auth yok.
          </div>
        </footer>
      </body>
    </html>
  );
}
