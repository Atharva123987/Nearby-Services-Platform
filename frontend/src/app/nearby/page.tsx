import { Suspense } from "react";
import { NearbyView } from "@/features/map/components/NearbyView";

export default function NearbyPage() {
  return (
    <main className="relative h-dvh w-full">
      {/* useSearchParams needs a Suspense boundary on a static page. */}
      <Suspense>
        <NearbyView />
      </Suspense>
    </main>
  );
}
