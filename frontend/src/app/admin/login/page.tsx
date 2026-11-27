import { Suspense } from "react";
import { LoginForm } from "@/features/admin/components/LoginForm";

export default function AdminLoginPage() {
  return (
    <main className="flex min-h-[calc(100dvh-4rem)] items-center justify-center bg-gray-50 p-4">
      {/* useSearchParams (return URL) needs a Suspense boundary. */}
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
