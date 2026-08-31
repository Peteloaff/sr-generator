"use client";

import { useCallback, useEffect, useState } from "react";
import { api, assetUrl, type AudioAsset } from "@/lib/api";

export default function CoverStudio({ songId }: { songId: string }) {
  const [stems, setStems] = useState<AudioAsset[]>([]);
  const [mixes, setMixes] = useState<AudioAsset[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, m] = await Promise.all([api.listSongStems(songId), api.listSongMixes(songId)]);
    setStems(s);
    setMixes(m);
  }, [songId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (label: string, fn: () => Promise<{ id: string }>) => {
    setBusy(label);
    setErr(null);
    try {
      const job = await fn();
      await api.waitJob(job.id);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const latestByType = new Map<string, AudioAsset>();
  for (const a of stems) if (!latestByType.has(a.asset_type)) latestByType.set(a.asset_type, a);

  return (
    <div className="section-render">
      <h4>Cover studio — replace the vocal, keep the melody</h4>
      <p className="muted">
        Separate the uploaded mix into vocal + instrumental, wire the separated
        stems into a section (its panel below → “Use separated stems”), render it
        with your singers, then assemble a new full mix. Untouched sections stay
        exactly as recorded.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <button
          onClick={() => run("separate", () => api.separateStems(songId))}
          disabled={!!busy}
        >
          {busy === "separate" ? "separating…" : "Separate stems"}
        </button>
        <button
          onClick={() => run("assemble", () => api.assembleSong(songId))}
          disabled={!!busy}
        >
          {busy === "assemble" ? "assembling…" : "Assemble full mix"}
        </button>
      </div>

      {latestByType.size > 0 && (
        <table>
          <tbody>
            {[...latestByType.values()].map((a) => (
              <tr key={a.id}>
                <td style={{ whiteSpace: "nowrap" }}>
                  {a.asset_type.replace(/_/g, " ")} v{a.version}
                </td>
                <td style={{ width: "100%" }}>
                  <audio controls preload="none" src={assetUrl(songId, a.id, { inline: true })} />
                </td>
                <td>
                  <a href={assetUrl(songId, a.id)}>download</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {mixes.length > 0 && (
        <>
          <h4>Assembled mixes</h4>
          <table>
            <tbody>
              {mixes.map((m) => (
                <tr key={m.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{m.label}</td>
                  <td style={{ width: "100%" }}>
                    <audio
                      controls
                      preload="none"
                      src={assetUrl(songId, m.id, { inline: true })}
                    />
                  </td>
                  <td>
                    <a href={assetUrl(songId, m.id)}>download</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
