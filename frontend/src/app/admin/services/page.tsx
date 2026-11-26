import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { ServicesTable } from "@/features/admin/components/ServicesTable";

// Protected by src/proxy.ts.
export default function AdminServicesPage() {
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <AdminHeader />
      <main className="mx-auto max-w-6xl p-6">
        <h1 className="mb-4 text-xl font-semibold">Services</h1>
        <ServicesTable />
      </main>
    </div>
  );
}
