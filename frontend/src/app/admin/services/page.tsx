import Link from "next/link";
import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { ServicesTable } from "@/features/admin/components/ServicesTable";

// Protected by src/proxy.ts.
export default function AdminServicesPage() {
  return (
    <div className="min-h-[calc(100dvh-4rem)] bg-stone-50 text-slate-900">
      <AdminHeader />
      <main className="mx-auto max-w-6xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Services</h1>
          <Link
            href="/admin/services/new"
            className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white"
          >
            Add service
          </Link>
        </div>
        <ServicesTable />
      </main>
    </div>
  );
}
