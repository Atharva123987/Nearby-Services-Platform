"use client";

import { useQuery } from "@tanstack/react-query";
import { adminKeys, fetchMe } from "@/features/admin/api";
import { LogoutButton } from "./LogoutButton";

export function AdminHeader() {
  const { data: me } = useQuery({ queryKey: adminKeys.me(), queryFn: fetchMe });

  return (
    <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
      <span className="font-semibold">Fieldguide admin</span>
      <div className="flex items-center gap-3 text-sm text-gray-600">
        {me && <span>{me.email}</span>}
        <LogoutButton />
      </div>
    </header>
  );
}
