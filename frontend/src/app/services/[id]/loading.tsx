// Skeleton matching the detail page layout while the service loads.
export default function Loading() {
  return (
    <main className="mx-auto max-w-3xl animate-pulse space-y-6 p-6">
      <div className="h-4 w-24 rounded bg-gray-100" />
      <div className="space-y-2">
        <div className="h-7 w-2/3 rounded bg-gray-100" />
        <div className="h-4 w-32 rounded bg-gray-100" />
      </div>
      <div className="h-64 rounded-lg bg-gray-100" />
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-gray-100" />
        <div className="h-4 w-5/6 rounded bg-gray-100" />
        <div className="h-4 w-4/6 rounded bg-gray-100" />
      </div>
    </main>
  );
}
