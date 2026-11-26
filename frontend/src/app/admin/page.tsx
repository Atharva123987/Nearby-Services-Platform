import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { Dashboard } from "@/features/admin/components/Dashboard";

// Protected by src/proxy.ts.
export default function AdminPage() {
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <AdminHeader />
      <main className="mx-auto max-w-5xl p-6">
        <Dashboard />
      </main>
    </div>
  );
}
