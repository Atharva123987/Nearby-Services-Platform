"use client";

import type { ServiceCategory } from "@/types/api";

const CHIPS: { value: ServiceCategory | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "hospital", label: "Hospitals" },
  { value: "atm", label: "ATMs" },
  { value: "shop", label: "Shops" },
  { value: "other", label: "Others" },
];

export function CategoryChips({
  selected,
  onSelect,
}: {
  selected: ServiceCategory | null;
  onSelect: (value: ServiceCategory | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {CHIPS.map(({ value, label }) => {
        const active = value === selected;
        return (
          <button
            key={label}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(value)}
            className={`rounded-full border border-slate-200 px-2.5 py-1.5 text-xs font-semibold ${
              active
                ? "bg-teal-800 text-white"
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
