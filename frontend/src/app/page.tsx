import { LocationBanner } from "@/features/map/components/LocationBanner";
import { ServiceMapLoader } from "@/features/map/components/ServiceMapLoader";

export default function HomePage() {
  return (
    <main className="relative h-dvh w-full">
      <ServiceMapLoader />
      {/* Bottom-centre so it never covers the zoom controls (top-left). */}
      <div className="pointer-events-none absolute inset-x-0 bottom-6 z-[1000] flex justify-center px-4">
        <div className="pointer-events-auto">
          <LocationBanner />
        </div>
      </div>
    </main>
  );
}
