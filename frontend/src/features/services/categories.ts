import type { ServiceCategory } from "@/types/api";

export const CATEGORY_STYLES: Record<
  ServiceCategory,
  { label: string; color: string; glyph: string }
> = {
  hospital: { label: "Hospital", color: "#dc2626", glyph: "H" },
  atm: { label: "ATM", color: "#16a34a", glyph: "₹" },
  shop: { label: "Shop", color: "#2563eb", glyph: "S" },
  other: { label: "Other", color: "#6b7280", glyph: "•" },
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
