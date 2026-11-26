import { AdminHeader } from "@/features/admin/components/AdminHeader";

// Protected by src/proxy.ts.
export default function AdminPage() {
  return (
    <div className="min-h-dvh">
      <AdminHeader />
      <main className="p-6 text-sm text-gray-600">Admin dashboard</main>
    </div>
  );
}
