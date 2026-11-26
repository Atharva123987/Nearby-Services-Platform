import { AdminHeader } from "@/features/admin/components/AdminHeader";
import { BulkUpload } from "@/features/admin/components/BulkUpload";

// Protected by src/proxy.ts.
export default function UploadPage() {
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <AdminHeader />
      <main className="mx-auto max-w-6xl p-6">
        <h1 className="mb-4 text-xl font-semibold">Bulk upload</h1>
        <BulkUpload />
      </main>
    </div>
  );
}
