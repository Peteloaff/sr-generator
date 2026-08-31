"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Home() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div>
      <h1>SR Generator — Stage 0</h1>
      <p className="muted">
        Private AI band music workstation. Stage 0 is foundation only: data model,
        job/asset pipeline, and mock providers. No AI models yet.
      </p>
      <h2>API health</h2>
      {err && <p className="danger">API unreachable: {err}</p>}
      {health ? (
        <pre>{JSON.stringify(health, null, 2)}</pre>
      ) : (
        !err && <p className="muted">checking…</p>
      )}
    </div>
  );
}
