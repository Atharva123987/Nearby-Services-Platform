import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { EditService } from "@/features/admin/components/EditService";

// Protected by src/proxy.ts.
export default async function EditServicePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <AdminHeader />
      <main className="mx-auto max-w-6xl p-6">
        <h1 className="mb-4 text-xl font-semibold">Edit service</h1>
        <EditService id={id} />
      </main>
    </div>
  );
}
