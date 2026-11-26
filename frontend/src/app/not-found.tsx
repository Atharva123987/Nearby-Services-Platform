import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-md space-y-3 p-6 text-center text-gray-900">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-gray-600">
        The page you are looking for doesn&apos;t exist.
      </p>
      <Link href="/nearby" className="text-sm text-blue-600 hover:underline">
        Go to the map
      </Link>
    </main>
  );
}
