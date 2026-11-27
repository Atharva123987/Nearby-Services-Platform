import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fieldguide",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <header className="site-header">
          <Link href="/" aria-label="Fieldguide home" className="brand">
            <span aria-hidden="true">⌖</span>Fieldguide
          </Link>
          <nav
            aria-label="Main"
            className="flex items-center gap-4 text-sm font-semibold"
          >
            <Link href="/">Explore map</Link>
            <Link className="admin-link" href="/admin">
              Admin
            </Link>
          </nav>
        </header>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
