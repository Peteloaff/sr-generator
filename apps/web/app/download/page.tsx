"use client";

import Link from "next/link";

const ZIP = "https://github.com/Peteloaff/sr-generator/releases/latest/download/SR-Generator-desktop.zip";
const RELEASES = "https://github.com/Peteloaff/sr-generator/releases";

export default function DownloadPage() {
  return (
    <div className="help">
      <h1>Desktop app (Windows)</h1>
      <p className="muted">
        The desktop app runs the whole thing on your own PC — the same features as
        the website, but your audio and models stay local and there&apos;s no cloud
        bill. Use the website to try it, the app to work.
      </p>

      <p style={{ margin: "1.25rem 0" }}>
        <a className="btn primary big" href={ZIP}>↓ Download SR Generator</a>
      </p>
      <p className="faint">
        ~96 MB zip · Windows 10/11 · <a href={RELEASES}>all versions</a>
      </p>

      <h2>Setup</h2>
      <ol className="help-steps">
        <li>
          <h3>1 · Unzip the whole folder</h3>
          <p>
            Right-click the download → <b>Extract All</b>. Keep everything
            together — <code>SR Generator.exe</code> needs the folder next to it.
          </p>
        </li>
        <li>
          <h3>2 · Run <code>SR Generator.exe</code></h3>
          <p>
            A console window opens, sets up a local database, and your browser
            opens to the app. Windows SmartScreen may warn about an unsigned
            app — <b>More info → Run anyway</b>. Closing the console stops it.
          </p>
        </li>
        <li>
          <h3>3 · First time you train a player</h3>
          <p>
            Per-instrument separation (Demucs, ~2 GB) installs itself once — you
            need a system <b>Python 3.12+</b> on PATH and a network connection.
            Skip it by setting <code>SR_MULTISTEM_PROVIDER=bandsplit</code> for
            the rough built-in split.
          </p>
        </li>
      </ol>

      <h2>Where your stuff lives</h2>
      <p className="muted">
        Everything is under <code>C:\Users\&lt;you&gt;\.sr-generator</code> — the
        database, your recordings, generated audio. Back that folder up to keep
        your work; delete it for a clean slate.
      </p>

      <p style={{ marginTop: "1.5rem" }}>
        <Link href="/help">→ Read the walkthrough</Link>
      </p>
    </div>
  );
}
