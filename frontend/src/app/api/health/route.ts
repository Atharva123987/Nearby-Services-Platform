// Liveness for the web container: 200 while Next.js serves HTTP. Touches no dependencies.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
