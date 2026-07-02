"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projetos" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex min-h-screen w-64 flex-col border-r border-white/10 bg-navy-950 px-5 py-6">
      <Link href="/dashboard" className="text-lg font-semibold text-white">
        Virtus et Veritas
      </Link>
      <p className="mt-1 text-xs text-gold-400">VVE Engine</p>

      <nav className="mt-10 grid gap-2">
        {links.map((link) => {
          const active = pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-md px-3 py-2 text-sm transition ${
                active
                  ? "bg-gold-500 text-navy-950"
                  : "text-slate-300 hover:bg-white/[0.05] hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
