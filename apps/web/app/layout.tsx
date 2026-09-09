import type { Metadata } from "next";
import Link from "next/link";
import BandSwitcher from "@/components/BandSwitcher";
import NowPlaying from "@/components/NowPlaying";
import "./globals.css";

export const metadata: Metadata = {
  title: "SR Generator",
  description: "Private AI band music workstation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="appbar">
          <Link href="/" className="brand">
            <span className="dot" />
            SR Generator
          </Link>
          <nav>
            <Link href="/">Home</Link>
            <Link href="/songs">Songs</Link>
            <Link href="/band">Band</Link>
            <Link href="/references">Band DNA</Link>
            <Link href="/projects">Projects</Link>
            <Link href="/help">Help</Link>
          </nav>
          <span className="spacer" />
          <BandSwitcher />
        </header>
        <main>{children}</main>
        <NowPlaying />
      </body>
    </html>
  );
}
