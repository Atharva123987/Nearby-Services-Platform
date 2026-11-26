"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";
import {
  BULK_TEMPLATE_URL,
  MAX_UPLOAD_BYTES,
  adminKeys,
  bulkUpload,
} from "@/features/admin/api";
import { serviceKeys } from "@/features/services/api";
import { ApiError } from "@/lib/api/client";

const ACCEPTED = [".csv", ".json"];

/** Same checks the API makes, so obvious mistakes never leave the browser. */
function checkFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED.some((ext) => name.endsWith(ext))) {
    return "File must be .csv or .json";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File must be at most ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB`;
  }
  if (file.size === 0) return "File is empty";
  return null;
}

export function BulkUpload() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const upload = useMutation({
    mutationFn: bulkUpload,
    onSuccess: (result) => {
      if (result.inserted > 0) {
        queryClient.invalidateQueries({ queryKey: adminKeys.services() });
        queryClient.invalidateQueries({ queryKey: serviceKeys.all });
      }
    },
  });

  function pick(next: File | undefined) {
    if (!next) return;
    upload.reset();
    const error = checkFile(next);
    setFileError(error);
    setFile(error ? null : next);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  }

  const result = upload.data;

  return (
    <div className="flex max-w-3xl flex-col gap-4 text-sm">
      <p className="text-gray-600">
        Upload a .csv or .json file (max 5 MB, 10,000 rows) with columns name,
        category, latitude, longitude and optional rating, metadata. Valid rows
        are added; invalid rows are listed below.{" "}
        <a href={BULK_TEMPLATE_URL} className="text-teal-800 hover:underline">
          Download the CSV template
        </a>
      </p>

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed p-10 text-center ${
          dragging ? "border-blue-500 bg-blue-50" : "border-gray-300"
        }`}
      >
        <span className="font-medium">
          {file ? file.name : "Drop a file here or click to choose"}
        </span>
        {file && (
          <span className="text-gray-500">
            {(file.size / 1024).toFixed(1)} KB
          </span>
        )}
        <input
          type="file"
          accept={ACCEPTED.join(",")}
          className="sr-only"
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = ""; // allow re-picking the same file
          }}
        />
      </label>

      {fileError && <p className="text-red-600">{fileError}</p>}
      {upload.isError && (
        <p role="alert" className="text-red-600">
          {upload.error instanceof ApiError
            ? upload.error.message
            : "Upload failed, please try again"}
        </p>
      )}

      <div>
        <button
          type="button"
          disabled={!file || upload.isPending}
          onClick={() => file && upload.mutate(file)}
          className="rounded bg-teal-800 hover:bg-teal-900 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {upload.isPending ? "Uploading…" : "Upload"}
        </button>
      </div>

      {result && (
        <section className="flex flex-col gap-3">
          <p>
            <span className="font-medium">{result.inserted}</span> of{" "}
            {result.total} rows added
            {result.failed > 0 && (
              <>
                , <span className="text-red-600">{result.failed} failed</span>
              </>
            )}
            .
          </p>
          {result.errors.length > 0 && (
            <div className="max-h-96 overflow-auto rounded-lg border border-gray-200">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-4 py-2 font-medium">Row</th>
                    <th className="px-4 py-2 font-medium">Field</th>
                    <th className="px-4 py-2 font-medium">Error</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {result.errors.map((e, i) => (
                    <tr key={i}>
                      <td className="px-4 py-2 tabular-nums">{e.row}</td>
                      <td className="px-4 py-2">{e.field ?? "—"}</td>
                      <td className="px-4 py-2">{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
