"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { login } from "@/features/admin/api";
import { ApiError } from "@/lib/api/client";
import { safeReturnUrl } from "@/lib/auth/return-url";

const schema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const { retryAfter } = (error.details ?? {}) as {
        retryAfter?: number | null;
      };
      return retryAfter
        ? `Too many login attempts. Try again in ${retryAfter}s.`
        : "Too many login attempts. Please try again later.";
    }
    if (error.status === 401) return "Invalid email or password";
    return error.message;
  }
  return "Something went wrong, please try again";
}

export function LoginForm() {
  const router = useRouter();
  const next = safeReturnUrl(useSearchParams().get("next"));
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login(values);
      router.replace(next);
      router.refresh();
    } catch (error) {
      setError("root", { message: errorMessage(error) });
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
    >
      <h1 className="text-xl font-semibold">Admin sign in</h1>

      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          aria-describedby={errors.email ? "login-email-error" : undefined}
          type="email"
          autoComplete="username"
          className="rounded border border-gray-300 px-3 py-2"
          aria-invalid={!!errors.email}
          {...register("email")}
        />
        {errors.email && (
          <span id="login-email-error" className="text-red-600">
            {errors.email.message}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          aria-describedby={
            errors.password ? "login-password-error" : undefined
          }
          type="password"
          autoComplete="current-password"
          className="rounded border border-gray-300 px-3 py-2"
          aria-invalid={!!errors.password}
          {...register("password")}
        />
        {errors.password && (
          <span id="login-password-error" className="text-red-600">
            {errors.password.message}
          </span>
        )}
      </div>

      {errors.root && (
        <p role="alert" className="text-sm text-red-600">
          {errors.root.message}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-lg bg-teal-800 hover:bg-teal-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
