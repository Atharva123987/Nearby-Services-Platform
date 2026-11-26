"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Modal } from "@/components/ui/Modal";
import { adminKeys, updateService } from "@/features/admin/api";
import { CATEGORY_STYLES } from "@/features/services/categories";
import { serviceKeys } from "@/features/services/api";
import { ApiError } from "@/lib/api/client";
import type { Service, ServiceCategory } from "@/types/api";

const CATEGORIES = Object.keys(CATEGORY_STYLES) as [
  ServiceCategory,
  ...ServiceCategory[],
];

// Mirrors the backend ServiceUpdate rules (backend/app/schemas/service.py).
const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  category: z.enum(CATEGORIES),
  latitude: z.number("Enter a number").min(-90).max(90),
  longitude: z.number("Enter a number").min(-180).max(180),
  rating: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || (/^\d(\.\d)?$/.test(v) && Number(v) <= 5),
      "0–5, one decimal place",
    ),
});

type FormValues = z.infer<typeof schema>;

const inputClass = "rounded border border-gray-300 px-3 py-2";

export function EditServiceDialog({
  service,
  onClose,
}: {
  service: Service;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: service.name,
      category: service.category,
      latitude: service.latitude,
      longitude: service.longitude,
      rating: service.rating === null ? "" : Number(service.rating).toFixed(1),
    },
  });

  const mutation = useMutation({
    mutationFn: ({ rating, ...rest }: FormValues) =>
      updateService(service.id, { ...rest, rating: rating || null }),
    onSuccess: () => {
      // Admin lists/dashboard and the public map all show services.
      queryClient.invalidateQueries({ queryKey: adminKeys.services() });
      queryClient.invalidateQueries({ queryKey: serviceKeys.all });
      onClose();
    },
    onError: (error) =>
      setError("root", {
        message:
          error instanceof ApiError ? error.message : "Could not save changes",
      }),
  });

  return (
    <Modal title="Edit service" onClose={onClose}>
      <form
        noValidate
        // onError shows the failure; catch so it isn't also an unhandled rejection.
        onSubmit={handleSubmit((values) =>
          mutation.mutateAsync(values).catch(() => undefined),
        )}
        className="flex flex-col gap-3 text-sm"
      >
        <Field label="Name" error={errors.name?.message}>
          <input className={inputClass} {...register("name")} />
        </Field>
        <Field label="Category" error={errors.category?.message}>
          <select className={inputClass} {...register("category")}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_STYLES[c].label}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Latitude" error={errors.latitude?.message}>
            <input
              type="number"
              step="any"
              className={inputClass}
              {...register("latitude", { valueAsNumber: true })}
            />
          </Field>
          <Field label="Longitude" error={errors.longitude?.message}>
            <input
              type="number"
              step="any"
              className={inputClass}
              {...register("longitude", { valueAsNumber: true })}
            />
          </Field>
        </div>
        <Field label="Rating (optional)" error={errors.rating?.message}>
          <input
            inputMode="decimal"
            className={inputClass}
            {...register("rating")}
          />
        </Field>

        {errors.root && (
          <p role="alert" className="text-red-600">
            {errors.root.message}
          </p>
        )}

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-gray-300 px-4 py-2"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded bg-gray-900 px-4 py-2 font-medium text-white disabled:opacity-50"
          >
            {isSubmitting ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      {label}
      {children}
      {error && <span className="text-red-600">{error}</span>}
    </label>
  );
}
