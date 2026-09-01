"use client";

import { useState } from "react";
import { api, type Song } from "@/lib/api";

export default function GeneratePanel({
  song,
  onChange,
}: {
  song: Song;
  onChange: () => void;
}) {
  const [prompt, setPrompt] = useState(song.prompt ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const job = await api.generateFullSong(song.id, { prompt: prompt || undefined });
      const done = await api.waitJob(job.id);
      if (done.status !== "succeeded") {
        setErr(done.error || "generation failed");
      } else {
        const r = done.result_json as {
          sections_created?: number;
          sections_rendered?: number;
          lyrics_source?: string;
        } | null;
        setNote(
          `Built ${r?.sections_created ?? "?"} sections, sang ${r?.sections_rendered ?? 0} of them` +
            (r?.lyrics_source === "scaffold"
              ? " (placeholder lyrics — write your own below and generate again)"
              : ""),
        );
      }
      onChange();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const already = song.status === "ready" || song.status === "generating";

  return (
    <div className="card pad-lg">
      <h3 style={{ marginTop: 0 }}>Style</h3>
      <p className="muted">
        Describe the song — mood, genre, references. This drives the structure,
        the instrumental, and (if you haven't written any yet) the lyrics.
      </p>
      <textarea
        rows={3}
        placeholder="e.g. a driving night-time anthem, heavy chorus, melodic verses"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      {err && <p className="danger">{err}</p>}
      {note && <p className="muted">{note}</p>}
      <div className="row" style={{ margin: "0.75rem 0 0" }}>
        <button className="primary big" onClick={generate} disabled={busy}>
          {busy ? "generating…" : already ? "Regenerate whole song" : "Generate song"}
        </button>
        <span className="faint">
          Builds the full structure and, for any singer with consent set, sings it too.
          You can cast more singers next and regenerate just their sections.
        </span>
      </div>
    </div>
  );
}
