"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  adminKeys,
  fetchAdminServices,
  fetchCategoryCounts,
} from "@/features/admin/api";
import { CATEGORY_STYLES, formatRating } from "@/features/services/categories";
import type { ServiceCategory } from "@/types/api";

const CATEGORIES = Object.keys(CATEGORY_STYLES) as ServiceCategory[];

export function Dashboard() {
  const counts = useQuery({
    queryKey: adminKeys.categoryCounts(),
    queryFn: () => fetchCategoryCounts(CATEGORIES),
  });
  const recent = useQuery({
    queryKey: adminKeys.recent(),
    queryFn: () =>
      fetchAdminServices({ page: 1, pageSize: 5, search: "", category: null }),
  });
  const total = counts.data
    ? Object.values(counts.data).reduce((a, b) => a + b, 0)
    : null;

  return (
    <div className="flex flex-col gap-8">
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Services by category</h2>
        {counts.isError && (
          <p className="text-sm text-red-600">Could not load counts.</p>
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label="Total" value={total} />
          {CATEGORIES.map((category) => (
            <Stat
              key={category}
              label={CATEGORY_STYLES[category].label}
              color={CATEGORY_STYLES[category].color}
              value={counts.data?.[category] ?? null}
            />
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-semibold">Recently added</h2>
          <Link href="/admin/services" className="text-sm text-teal-800">
            Manage services →
          </Link>
        </div>
        {recent.isPending && <p className="text-sm text-gray-500">Loading…</p>}
        {recent.isError && (
          <p className="text-sm text-red-600">Could not load services.</p>
        )}
        {recent.data && (
          <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 text-sm">
            {recent.data.items.length === 0 && (
              <li className="px-4 py-3 text-gray-500">No services yet.</li>
            )}
            {recent.data.items.map((service) => (
              <li
                key={service.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <span>
                  <span className="font-medium">{service.name}</span>{" "}
                  <span className="text-gray-500">
                    · {CATEGORY_STYLES[service.category].label} ·{" "}
                    {formatRating(service.rating)}
                  </span>
                </span>
                <span className="text-gray-500">
                  {new Date(service.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        {color && (
          <span
            className="inline-block size-2.5 rounded-full"
            style={{ backgroundColor: color }}
          />
        )}
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">
        {value ?? "–"}
      </div>
    </div>
  );
}
