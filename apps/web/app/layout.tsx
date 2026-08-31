import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "SR Generator",
  description: "Private AI band music workstation - Stage 0",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <strong>SR Generator</strong>
          <nav>
            <Link href="/">Home</Link>
            <Link href="/singers">Singers</Link>
            <Link href="/songs">Songs</Link>
            <Link href="/jobs">Jobs</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
