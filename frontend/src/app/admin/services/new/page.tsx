import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { ServiceForm } from "@/features/admin/components/ServiceForm";

// Protected by src/proxy.ts.
export default function NewServicePage() {
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <AdminHeader />
      <main className="mx-auto max-w-6xl p-6">
        <h1 className="mb-4 text-xl font-semibold">Add service</h1>
        <ServiceForm />
      </main>
    </div>
  );
}
