"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

function ShieldCheckIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 shrink-0"
      aria-hidden="true"
    >
      <path d="M12 3l7 3v5c0 4.5-3 8.25-7 10-4-1.75-7-5.5-7-10V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

const baseLinks: { href: string; label: string; icon?: ReactNode }[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projetos" },
  { href: "/fidelity-coverage", label: "Fidelidade e Cobertura", icon: <ShieldCheckIcon /> },
  { href: "/instructor-profile", label: "Perfil do Instrutor" },
  { href: "/account/api-keys", label: "Minhas APIs" },
];

const adminLinks: { href: string; label: string; icon?: ReactNode }[] = [
  { href: "/admin/users", label: "Administração" },
];

type SidebarProps = {
  role?: string;
};

export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const links = role === "admin" ? [...baseLinks, ...adminLinks] : baseLinks;

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
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition ${
                active
                  ? "bg-gold-500 text-navy-950"
                  : "text-slate-300 hover:bg-white/[0.05] hover:text-white"
              }`}
            >
              {link.icon}
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
