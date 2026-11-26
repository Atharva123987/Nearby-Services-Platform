"use client";

import { useQuery } from "@tanstack/react-query";
import { adminKeys, fetchService } from "@/features/admin/api";
import { ApiError } from "@/lib/api/client";
import { ServiceForm } from "./ServiceForm";

export function EditService({ id }: { id: string }) {
  const { data, error, isPending } = useQuery({
    queryKey: adminKeys.detail(id),
    queryFn: () => fetchService(id),
    staleTime: 0, // always edit the latest version
  });

  if (isPending) return <p className="text-sm text-gray-500">Loading…</p>;
  if (error) {
    return (
      <p className="text-sm text-red-600">
        {error instanceof ApiError && error.status === 404
          ? "Service not found."
          : "Could not load the service."}
      </p>
    );
  }
  return <ServiceForm service={data} />;
}
