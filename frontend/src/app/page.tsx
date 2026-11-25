import { LocationBanner } from "@/features/map/components/LocationBanner";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-semibold">Fieldguide</h1>
      <LocationBanner />
    </main>
  );
}
