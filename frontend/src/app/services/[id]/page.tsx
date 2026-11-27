import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchServiceDetail } from "@/features/services/api";
import { CATEGORY_STYLES, formatRating } from "@/features/services/categories";
import { MetadataTable } from "@/features/services/components/MetadataTable";
import { ServiceLocation } from "@/features/services/components/ServiceLocation";
import { ApiError } from "@/lib/api/client";
import { backendUrl } from "@/lib/auth/session";

// ISR: pages render on first request and are cached; admin edits revalidate by tag.
export const revalidate = 60;
export function generateStaticParams() {
  return [];
}

type Props = { params: Promise<{ id: string }> };

/** 404 for unknown ids and malformed (non-UUID, 422) ids; anything else is a real error. */
async function getService(id: string) {
  try {
    return await fetchServiceDetail(id, backendUrl);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status)) {
      notFound();
    }
    throw error;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const service = await getService((await params).id);
  const category = CATEGORY_STYLES[service.category].label;
  return {
    title: `${service.name} · ${category} | Fieldguide`,
    description: `${service.name} (${category}), ${formatRating(service.rating)}. Location, details and directions.`,
  };
}

export default async function ServiceDetailPage({ params }: Props) {
  const service = await getService((await params).id);
  const style = CATEGORY_STYLES[service.category];

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6 text-gray-900">
      <Link href="/" className="text-sm text-blue-600 hover:underline">
        ← Back to map
      </Link>

      <header className="space-y-1">
        <h1 className="text-2xl font-semibold break-words">{service.name}</h1>
        <p className="flex gap-3 text-sm">
          <span style={{ color: style.color }}>{style.label}</span>
          <span>{formatRating(service.rating)}</span>
        </p>
      </header>

      <ServiceLocation
        position={{ lat: service.latitude, lng: service.longitude }}
        color={style.color}
      />

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Details</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-gray-600">Coordinates</dt>
          <dd>
            {service.latitude.toFixed(6)}, {service.longitude.toFixed(6)}
          </dd>
          <dt className="text-gray-600">Last updated</dt>
          <dd>
            <time dateTime={service.updated_at}>
              {new Date(service.updated_at).toUTCString()}
            </time>
          </dd>
        </dl>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">More information</h2>
        <MetadataTable metadata={service.metadata} />
      </section>
    </main>
  );
}
