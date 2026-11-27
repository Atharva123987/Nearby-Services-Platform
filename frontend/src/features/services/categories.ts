import type { ServiceCategory } from "@/types/api";

export const CATEGORY_STYLES: Record<
  ServiceCategory,
  { label: string; color: string; iconPath: string }
> = {
  hospital: {
    label: "Hospital",
    color: "#dc2626",
    iconPath: "M9 3h6v6h6v6h-6v6H9v-6H3V9h6z",
  },
  atm: {
    label: "ATM",
    color: "#16a34a",
    iconPath:
      "M2 5h20v14H2z M7 12h.1 M17 12h.1 M14 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0",
  },
  shop: {
    label: "Shop",
    color: "#2563eb",
    iconPath: "M4 10h16v10H4z M3 10l2-6h14l2 6 M9 20v-6h5v6",
  },
  other: {
    label: "Other",
    color: "#6b7280",
    iconPath:
      "M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0z M14 10a2 2 0 1 1-4 0 2 2 0 1 1 4 0",
  },
};

export function formatRating(rating: string | null): string {
  return rating === null ? "No rating" : `${Number(rating).toFixed(1)} ★`;
}

/** Reads a `?category=` value; anything unknown falls back to "All" (null). */
export function parseCategory(value: string | null): ServiceCategory | null {
  return value !== null && Object.hasOwn(CATEGORY_STYLES, value)
    ? (value as ServiceCategory)
    : null;
}
