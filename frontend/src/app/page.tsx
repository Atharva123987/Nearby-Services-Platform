import { Suspense } from "react";
import { LocationBanner } from "@/features/map/components/LocationBanner";
import { ServiceMapLoader } from "@/features/map/components/ServiceMapLoader";
import { CategoryChips } from "@/features/services/components/CategoryChips";

export default function HomePage() {
  return (
    <main className="relative h-dvh w-full">
      <ServiceMapLoader />
      {/* Inset so the chips never cover the top-left zoom controls. */}
      <div className="pointer-events-none absolute inset-x-14 top-3 z-[1000] flex justify-center">
        <div className="pointer-events-auto">
          {/* useSearchParams needs a Suspense boundary on a static page. */}
          <Suspense>
            <CategoryChips />
          </Suspense>
        </div>
      </div>
      {/* Bottom-centre so it never covers the zoom controls (top-left). */}
      <div className="pointer-events-none absolute inset-x-0 bottom-6 z-[1000] flex justify-center px-4">
        <div className="pointer-events-auto">
          <LocationBanner />
        </div>
      </div>
    </main>
  );
}
