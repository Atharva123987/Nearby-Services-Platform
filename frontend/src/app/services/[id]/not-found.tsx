import Link from "next/link";

// Shown for unknown, malformed or deleted service ids (the page calls notFound()).
export default function ServiceNotFound() {
  return (
    <main className="mx-auto max-w-md space-y-3 p-6 text-center text-gray-900">
      <h1 className="text-2xl font-semibold">Service not found</h1>
      <p className="text-sm text-gray-600">
        This service doesn&apos;t exist or has been removed.
      </p>
      <Link href="/nearby" className="text-sm text-blue-600 hover:underline">
        Find services nearby
      </Link>
    </main>
  );
}
