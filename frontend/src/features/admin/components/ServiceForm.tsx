"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import {
  adminKeys,
  createService,
  updateService,
  type ServiceInput,
} from "@/features/admin/api";
import { serviceKeys } from "@/features/services/api";
import { CATEGORY_STYLES } from "@/features/services/categories";
import { ApiError } from "@/lib/api/client";
import type { Service, ServiceCategory } from "@/types/api";

// Leaflet touches `window` on import, so the picker never renders on the server.
const LocationPicker = dynamic(() => import("./LocationPicker"), {
  ssr: false,
  loading: () => (
    <div className="h-64 w-full animate-pulse rounded bg-gray-100" />
  ),
});

const CATEGORIES = Object.keys(CATEGORY_STYLES) as [
  ServiceCategory,
  ...ServiceCategory[],
];

function parseMetadata(text: string): Record<string, unknown> | null {
  if (!text.trim()) return null;
  return JSON.parse(text) as Record<string, unknown>;
}

// Mirrors the backend ServiceCreate rules (backend/app/schemas/service.py).
const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  category: z.enum(CATEGORIES),
  latitude: z
    .number("Enter a number")
    .min(-90, "Latitude must be between -90 and 90")
    .max(90, "Latitude must be between -90 and 90"),
  longitude: z
    .number("Enter a number")
    .min(-180, "Longitude must be between -180 and 180")
    .max(180, "Longitude must be between -180 and 180"),
  rating: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || (/^\d(\.\d)?$/.test(v) && Number(v) <= 5),
      "0–5, one decimal place",
    ),
  metadata: z.string().refine((text) => {
    try {
      const value = parseMetadata(text);
      return (
        value === null || (typeof value === "object" && !Array.isArray(value))
      );
    } catch {
      return false;
    }
  }, 'Must be a JSON object, e.g. {"open_24h": true}'),
});

type FormValues = z.infer<typeof schema>;
const FIELDS = Object.keys(schema.shape) as (keyof FormValues)[];

const inputClass = "rounded border border-gray-300 px-3 py-2";

/** Create (no `service`) or edit form. */
export function ServiceForm({ service }: { service?: Service }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: service?.name ?? "",
      category: service?.category ?? "other",
      latitude: service?.latitude,
      longitude: service?.longitude,
      rating: service?.rating == null ? "" : Number(service.rating).toFixed(1),
      metadata: service?.metadata
        ? JSON.stringify(service.metadata, null, 2)
        : "",
    },
  });
  const [lat, lng] = useWatch({ control, name: ["latitude", "longitude"] });
  const point =
    Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? { lat, lng } : null;

  const onSubmit = handleSubmit(async ({ rating, metadata, ...rest }) => {
    const body: ServiceInput = {
      ...rest,
      rating: rating || null,
      metadata: parseMetadata(metadata),
    };
    try {
      if (service) await updateService(service.id, body);
      else await createService(body);
    } catch (error) {
      showServerError(error);
      return;
    }
    // Admin lists/dashboard and the public map all show services.
    await queryClient.invalidateQueries({ queryKey: adminKeys.services() });
    await queryClient.invalidateQueries({ queryKey: serviceKeys.all });
    router.push("/admin/services");
  });

  /** Puts backend validation errors on the field they belong to. */
  function showServerError(error: unknown) {
    if (!(error instanceof ApiError)) {
      setError("root", { message: "Could not save, please try again" });
      return;
    }
    if (error.status === 409) {
      setError("name", { message: error.message });
      return;
    }
    if (error.status === 422 && Array.isArray(error.details)) {
      let placed = false;
      for (const { loc, msg } of error.details as {
        loc: (string | number)[];
        msg: string;
      }[]) {
        const field = FIELDS.find((f) => f === loc[1]);
        if (field) {
          setError(field, { message: msg });
          placed = true;
        }
      }
      if (placed) return;
    }
    setError("root", { message: error.message });
  }

  return (
    <form
      noValidate
      onSubmit={onSubmit}
      className="flex max-w-2xl flex-col gap-4 text-sm"
    >
      <Field id="service-name" label="Name" error={errors.name?.message}>
        <input
          className={inputClass}
          id="service-name"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "service-name-error" : undefined}
          {...register("name")}
        />
      </Field>

      <Field
        id="service-category"
        label="Category"
        error={errors.category?.message}
      >
        <select
          className={inputClass}
          id="service-category"
          aria-invalid={!!errors.category}
          aria-describedby={
            errors.category ? "service-category-error" : undefined
          }
          {...register("category")}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_STYLES[c].label}
            </option>
          ))}
        </select>
      </Field>

      <div className="flex flex-col gap-2">
        <span>Location — click the map or type coordinates</span>
        <LocationPicker
          value={point}
          onPick={({ lat, lng }) => {
            setValue("latitude", lat, { shouldValidate: true });
            setValue("longitude", lng, { shouldValidate: true });
          }}
        />
        <div className="grid grid-cols-2 gap-3">
          <Field
            id="service-latitude"
            label="Latitude"
            error={errors.latitude?.message}
          >
            <input
              type="number"
              step="any"
              className={inputClass}
              id="service-latitude"
              aria-invalid={!!errors.latitude}
              aria-describedby={
                errors.latitude ? "service-latitude-error" : undefined
              }
              {...register("latitude", { valueAsNumber: true })}
            />
          </Field>
          <Field
            id="service-longitude"
            label="Longitude"
            error={errors.longitude?.message}
          >
            <input
              type="number"
              step="any"
              className={inputClass}
              id="service-longitude"
              aria-invalid={!!errors.longitude}
              aria-describedby={
                errors.longitude ? "service-longitude-error" : undefined
              }
              {...register("longitude", { valueAsNumber: true })}
            />
          </Field>
        </div>
      </div>

      <Field
        id="service-rating"
        label="Rating (optional)"
        error={errors.rating?.message}
      >
        <input
          inputMode="decimal"
          className={`${inputClass} w-32`}
          id="service-rating"
          aria-invalid={!!errors.rating}
          aria-describedby={errors.rating ? "service-rating-error" : undefined}
          {...register("rating")}
        />
      </Field>

      <Field
        id="service-metadata"
        label="Metadata (optional JSON)"
        error={errors.metadata?.message}
      >
        <textarea
          rows={5}
          spellCheck={false}
          placeholder='{"open_24h": true}'
          className={`${inputClass} font-mono`}
          id="service-metadata"
          aria-invalid={!!errors.metadata}
          aria-describedby={
            errors.metadata ? "service-metadata-error" : undefined
          }
          {...register("metadata")}
        />
      </Field>

      {errors.root && (
        <p role="alert" className="text-red-600">
          {errors.root.message}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-teal-800 hover:bg-teal-900 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {isSubmitting
            ? "Saving…"
            : service
              ? "Save changes"
              : "Create service"}
        </button>
        <Link
          href="/admin/services"
          className="rounded border border-gray-300 px-4 py-2"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <span id={`${id}-error`} className="text-red-600">
          {error}
        </span>
      )}
    </div>
  );
}
