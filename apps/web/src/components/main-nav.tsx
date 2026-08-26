"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Sohbet" },
  { href: "/duyurular", label: "Duyurular" },
  { href: "/takvim", label: "Takvim" },
  { href: "/mail", label: "Mail" },
];

export function MainNav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={
            pathname === item.href
              ? "rounded-md bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground"
              : "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground"
          }
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
