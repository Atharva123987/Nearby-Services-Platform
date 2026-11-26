"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { adminKeys, fetchMe } from "@/features/admin/api";
import { LogoutButton } from "./LogoutButton";

const NAV = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/services", label: "Services" },
];

export function AdminHeader() {
  const pathname = usePathname();
  const { data: me } = useQuery({ queryKey: adminKeys.me(), queryFn: fetchMe });

  return (
    <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
      <nav className="flex items-center gap-4 text-sm">
        <span className="font-semibold">Fieldguide admin</span>
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={
              pathname === href
                ? "font-medium text-blue-600"
                : "text-gray-600 hover:text-gray-900"
            }
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="flex items-center gap-3 text-sm text-gray-600">
        {me && <span>{me.email}</span>}
        <LogoutButton />
      </div>
    </header>
  );
}
