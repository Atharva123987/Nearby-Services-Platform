export const ADMIN_HOME = "/admin";
export const ADMIN_LOGIN = "/admin/login";

/** Only same-site paths are allowed as a post-login target (no open redirects). */
export function safeReturnUrl(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return ADMIN_HOME;
  }
  return value.startsWith(ADMIN_LOGIN) ? ADMIN_HOME : value;
}

export function loginUrl(returnTo: string): string {
  return `${ADMIN_LOGIN}?next=${encodeURIComponent(returnTo)}`;
}
