"use client";

import { useState } from "react";
import { api, type SectionArrangement, type Singer } from "@/lib/api";

export default function ComposePanel({
  songId,
  singers,
  onChange,
}: {
  songId: string;
  singers: Singer[];
  onChange: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rec, setRec] = useState<SectionArrangement[] | null>(null);
  const [overwrite, setOverwrite] = useState(false);

  const nameOf = (id: string) => singers.find((s) => s.id === id)?.name ?? "?";

  const run = async (tag: string, fn: () => Promise<void>) => {
    setBusy(tag);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const generate = () =>
    run("gen", async () => {
      const job = await api.generateFullSong(songId, { prompt });
      await api.waitJob(job.id);
      onChange();
    });

  const recommend = () =>
    run("rec", async () => {
      setRec((await api.recommendArrangement(songId)).sections);
    });

  const apply = () =>
    run("apply", async () => {
      const r = await api.applyArrangement(songId, { overwrite });
      if (r.skipped.length) {
        setErr(
          "skipped: " +
            r.skipped.map((s) => `${s.section_id.slice(0, 6)} (${s.reason})`).join(", "),
        );
      }
      setRec(null);
      onChange();
    });

  return (
    <div className="ab">
      <h3>Full song generator</h3>
      <p className="muted">
        A prompt becomes a structured, editable project: sections, a default
        arrangement, a per-section instrumental + guide melody, rendered band
        vocals, and a song master. Regenerating one section later never touches
        the rest.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <input
          placeholder="e.g. a driving night-time anthem"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ minWidth: 320 }}
        />
        <button disabled={!!busy} onClick={generate}>
          {busy === "gen" ? "generating…" : "Generate song"}
        </button>
      </div>

      <h3 style={{ marginTop: 16 }}>Auto arranger</h3>
      <p className="muted">
        Recommends lead / double / harmony / gang roles from singer metadata and
        section energy. Applying never overwrites existing roles unless you tick
        the box.
      </p>
      <div className="row">
        <button disabled={!!busy} onClick={recommend}>
          {busy === "rec" ? "…" : "Recommend arrangement"}
        </button>
        {rec && (
          <>
            <label>
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
              />{" "}
              replace existing roles
            </label>
            <button disabled={!!busy} onClick={apply}>
              {busy === "apply" ? "…" : "Apply"}
            </button>
          </>
        )}
      </div>
      {rec && (
        <table>
          <thead>
            <tr>
              <th>Section</th>
              <th>Energy</th>
              <th>Recommended roles</th>
            </tr>
          </thead>
          <tbody>
            {rec.map((s) => (
              <tr key={s.section_id}>
                <td>
                  {s.name || s.section_type}
                  {s.locked ? " 🔒" : ""}
                  {s.has_roles ? " ·has roles" : ""}
                </td>
                <td className="muted">
                  {s.energy_band} ({s.energy.toFixed(2)})
                </td>
                <td>
                  {s.recommendations.map((r, i) => (
                    <div key={i} className="muted">
                      <strong>{r.role_type}</strong>:{" "}
                      {r.assignments.map((a) => nameOf(a.singer_id)).join(" / ")} · conf{" "}
                      {r.confidence.toFixed(2)} · {r.rationale}
                    </div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
