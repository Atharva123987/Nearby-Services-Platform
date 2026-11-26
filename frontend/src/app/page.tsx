import { Suspense } from "react";
import { NearbyView } from "@/features/map/components/NearbyView";

export default function HomePage() {
  return (
    <main className="search-page">
      {/* useSearchParams needs a Suspense boundary on a static page. */}
      <Suspense>
        <NearbyView />
      </Suspense>
    </main>
  );
}
