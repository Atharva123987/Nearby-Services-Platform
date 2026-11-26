// Values render as React text (escaped), never as HTML, so metadata can't inject markup.
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function MetadataTable({
  metadata,
}: {
  metadata: Record<string, unknown> | null;
}) {
  const entries = Object.entries(metadata ?? {});
  if (entries.length === 0) {
    return <p className="text-sm text-gray-500">No additional details.</p>;
  }
  return (
    <table className="w-full table-fixed text-left text-sm">
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key} className="border-t border-gray-100 align-top">
            <th className="w-1/3 py-2 pr-4 font-medium break-words text-gray-600">
              {key}
            </th>
            <td className="py-2">
              <pre className="font-sans whitespace-pre-wrap break-words">
                {formatValue(value)}
              </pre>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
