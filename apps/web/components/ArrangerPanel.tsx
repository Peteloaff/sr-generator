"use client";

import { useState } from "react";
import { api, type SectionArrangement, type Singer } from "@/lib/api";

export default function ArrangerPanel({
  songId,
  singers,
  onChange,
}: {
  songId: string;
  singers: Singer[];
  onChange: () => void;
}) {
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

  const recommend = () =>
    run("rec", async () => {
      setRec((await api.recommendArrangement(songId)).sections);
    });

  const apply = () =>
    run("apply", async () => {
      const r = await api.applyArrangement(songId, { overwrite });
      if (r.skipped.length) {
        setErr(`skipped ${r.skipped.length} section(s) that already had roles — tick "replace" to overwrite`);
      }
      setRec(null);
      onChange();
    });

  return (
    <div className="card">
      <div className="row space tight">
        <h3 style={{ margin: 0 }}>Auto-cast</h3>
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          suggests who sings what, from each singer's preferences
        </span>
      </div>
      {err && <p className="danger">{err}</p>}
      <div className="row tight">
        <button disabled={!!busy} onClick={recommend}>
          {busy === "rec" ? "thinking…" : "Suggest casting"}
        </button>
        {rec && (
          <>
            <label>
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
              />
              replace existing roles
            </label>
            <button className="primary" disabled={!!busy} onClick={apply}>
              {busy === "apply" ? "…" : "Apply casting"}
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
              <th>Suggested</th>
            </tr>
          </thead>
          <tbody>
            {rec.map((s) => (
              <tr key={s.section_id}>
                <td>
                  {s.name || s.section_type}
                  {s.locked ? " 🔒" : ""}
                  {s.has_roles ? " · cast" : ""}
                </td>
                <td className="muted">{s.energy_band}</td>
                <td style={{ fontSize: "0.85rem" }}>
                  {s.recommendations.map((r, i) => (
                    <div key={i} className="muted">
                      <strong style={{ color: "var(--fg)" }}>{r.role_type}</strong>:{" "}
                      {r.assignments.map((a) => nameOf(a.singer_id)).join(" / ")}{" "}
                      <span className="faint">({Math.round(r.confidence * 100)}% — {r.rationale})</span>
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
