"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/Modal";
import {
  adminKeys,
  deleteService,
  fetchAdminServices,
} from "@/features/admin/api";
import { serviceKeys } from "@/features/services/api";
import {
  CATEGORY_STYLES,
  formatRating,
  parseCategory,
} from "@/features/services/categories";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError } from "@/lib/api/client";
import type { Service, ServiceCategory, ServicePage } from "@/types/api";

const PAGE_SIZE = 20;
const CATEGORIES = Object.keys(CATEGORY_STYLES) as ServiceCategory[];
const listKey = [...adminKeys.services(), "list"];

export function ServicesTable() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<ServiceCategory | null>(null);
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<Service | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  const params = {
    page,
    pageSize: PAGE_SIZE,
    search: debouncedSearch,
    category,
  };
  const { data, isPending, isError, isFetching } = useQuery({
    queryKey: adminKeys.serviceList(params),
    queryFn: () => fetchAdminServices(params),
    placeholderData: keepPreviousData,
  });
  const pageCount = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1;

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(id);
  }, [toast]);

  const remove = useMutation({
    mutationFn: (service: Service) => deleteService(service.id),
    // Optimistic: drop the row from every cached list now, roll back on failure.
    onMutate: async (service) => {
      await queryClient.cancelQueries({ queryKey: listKey });
      const snapshot = queryClient.getQueriesData<ServicePage>({
        queryKey: listKey,
      });
      queryClient.setQueriesData<ServicePage>({ queryKey: listKey }, (old) =>
        old?.items.some((s) => s.id === service.id)
          ? {
              ...old,
              items: old.items.filter((s) => s.id !== service.id),
              total: old.total - 1,
            }
          : old,
      );
      return { snapshot };
    },
    onError: (error, service, context) => {
      context?.snapshot.forEach(([key, value]) =>
        queryClient.setQueryData(key, value),
      );
      const reason = error instanceof ApiError ? `: ${error.message}` : "";
      setToast(`Could not delete "${service.name}"${reason}`);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.services() });
      queryClient.invalidateQueries({ queryKey: serviceKeys.all });
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search by name"
          aria-label="Search by name"
          className="w-64 rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <select
          value={category ?? ""}
          onChange={(e) => {
            setCategory(parseCategory(e.target.value));
            setPage(1);
          }}
          aria-label="Category"
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_STYLES[c].label}
            </option>
          ))}
        </select>
        {isFetching && <span className="text-sm text-gray-400">Loading…</span>}
      </div>

      {isError && (
        <p className="text-sm text-red-600">Could not load services.</p>
      )}

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Rating</th>
              <th className="px-4 py-2 font-medium">Location</th>
              <th className="px-4 py-2 font-medium">Added</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!isPending && data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-gray-500">
                  No services match.
                </td>
              </tr>
            )}
            {data?.items.map((service) => (
              <tr key={service.id}>
                <td className="px-4 py-2 font-medium">{service.name}</td>
                <td className="px-4 py-2">
                  {CATEGORY_STYLES[service.category].label}
                </td>
                <td className="px-4 py-2">{formatRating(service.rating)}</td>
                <td className="px-4 py-2 tabular-nums text-gray-600">
                  {service.latitude.toFixed(4)}, {service.longitude.toFixed(4)}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {new Date(service.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-2 text-right whitespace-nowrap">
                  <Link
                    href={`/admin/services/${service.id}/edit`}
                    className="text-blue-600 hover:underline"
                  >
                    Edit
                  </Link>
                  <button
                    type="button"
                    onClick={() => setDeleting(service)}
                    className="ml-3 text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>{data ? `${data.total} services` : ""}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>

      {deleting && (
        <Modal title="Delete service?" onClose={() => setDeleting(null)}>
          <p className="text-sm text-gray-600">
            &ldquo;{deleting.name}&rdquo; will be permanently deleted.
          </p>
          <div className="mt-6 flex justify-end gap-2 text-sm">
            <button
              type="button"
              onClick={() => setDeleting(null)}
              className="rounded border border-gray-300 px-4 py-2"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                remove.mutate(deleting, {
                  onSuccess: () => {
                    if (data?.items.length === 1 && page > 1) {
                      setPage((current) =>
                        current === page ? page - 1 : current,
                      );
                    }
                  },
                });
                setDeleting(null);
              }}
              className="rounded bg-red-600 px-4 py-2 font-medium text-white"
            >
              Delete
            </button>
          </div>
        </Modal>
      )}

      {toast && (
        <div
          role="alert"
          className="fixed right-4 bottom-4 z-[2100] rounded-lg bg-red-600 px-4 py-3 text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
