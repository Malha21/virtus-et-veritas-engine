"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  KeyRound,
  LayoutDashboard,
  UserCircle,
  Users,
  type LucideIcon,
} from "lucide-react";

const baseLinks: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/instructor-profile", label: "Perfil do Instrutor", icon: UserCircle },
  { href: "/account/api-keys", label: "Minhas APIs", icon: KeyRound },
];

const adminLinks: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/admin/users", label: "Administração", icon: Users },
];

type SidebarProps = {
  role?: string;
};

export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const links = role === "admin" ? [...baseLinks, ...adminLinks] : baseLinks;

  return (
    <aside className="flex min-h-screen w-[72px] flex-col items-center gap-1 border-r border-white/5 bg-navy-950 py-6">
      <nav className="flex flex-col gap-2">
        {links.map((link) => {
          const active = pathname.startsWith(link.href);
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              className={`group relative flex h-11 w-11 items-center justify-center rounded-full transition ${
                active
                  ? "bg-accent-500 text-navy-950"
                  : "text-zinc-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Icon className="h-5 w-5" strokeWidth={1.8} aria-hidden="true" />
              <span
                role="tooltip"
                className="pointer-events-none absolute left-full ml-3 whitespace-nowrap rounded-md bg-navy-700 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition group-hover:opacity-100"
              >
                {link.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
