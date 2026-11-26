"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { parseCategory } from "@/features/services/categories";
import { useMapStore } from "@/stores/map-store";
import type { ServiceCategory } from "@/types/api";

const CHIPS: { value: ServiceCategory | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "hospital", label: "Hospitals" },
  { value: "atm", label: "ATMs" },
  { value: "shop", label: "Shops" },
  { value: "other", label: "Others" },
];

/** Category filter kept in the map store and mirrored to `?category=` so links are shareable. */
export function CategoryChips() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selected = useMapStore((s) => s.selectedCategory);
  const setSelected = useMapStore((s) => s.setSelectedCategory);
  const urlCategory = parseCategory(searchParams.get("category"));

  // URL -> store (initial load, shared links, back/forward).
  useEffect(() => setSelected(urlCategory), [urlCategory, setSelected]);

  function select(category: ServiceCategory | null) {
    setSelected(category);
    const params = new URLSearchParams(searchParams);
    if (category) params.set("category", category);
    else params.delete("category");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  }

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {CHIPS.map(({ value, label }) => {
        const active = value === selected;
        return (
          <button
            key={label}
            type="button"
            aria-pressed={active}
            onClick={() => select(value)}
            className={`rounded-full px-3 py-1 text-sm font-medium shadow ${
              active
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 hover:bg-gray-100"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
