"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { logout } from "@/features/admin/api";
import { ADMIN_LOGIN } from "@/lib/auth/return-url";

export function LogoutButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);

  async function onClick() {
    setPending(true);
    try {
      await logout();
    } finally {
      // Drop every cached response so nothing from this session leaks to the next one.
      queryClient.clear();
      router.replace(ADMIN_LOGIN);
      router.refresh();
    }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="rounded border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
    >
      Log out
    </button>
  );
}
