import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        // Client errors (4xx) won't fix themselves on retry.
        retry: (failureCount, error) =>
          !(
            error instanceof ApiError &&
            error.status >= 400 &&
            error.status < 500
          ) && failureCount < 2,
      },
    },
  });
}
