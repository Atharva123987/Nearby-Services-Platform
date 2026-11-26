"use client";

import Link from "next/link";

// Catches render/data errors in any route below the root layout.
export default function ErrorPage({
  error,
}: {
  error: Error & { digest?: string };
}) {
  return (
    <main className="mx-auto max-w-md space-y-3 p-6 text-center text-gray-900">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="text-sm text-gray-600">
        Please try again. If it keeps happening, come back in a few minutes.
      </p>
      {error.digest && (
        <p className="text-xs text-gray-400">Reference: {error.digest}</p>
      )}
      <div className="flex justify-center gap-4 text-sm">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded bg-blue-600 px-3 py-1.5 font-medium text-white hover:bg-blue-700"
        >
          Try again
        </button>
        <Link
          href="/nearby"
          className="self-center text-blue-600 hover:underline"
        >
          Go to the map
        </Link>
      </div>
    </main>
  );
}
