"use client";

import { useEffect, useState } from "react";
import { api, type Genre, type Song } from "@/lib/api";

export default function GeneratePanel({
  song,
  onChange,
}: {
  song: Song;
  onChange: () => void;
}) {
  const [prompt, setPrompt] = useState(song.prompt ?? "");
  const [genre, setGenre] = useState<string>(song.genre ?? "");
  const [blend, setBlend] = useState<number>(song.style_blend ?? 0.6);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    api.listGenres().then(setGenres).catch(() => setGenres([]));
  }, []);

  const generate = async () => {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      await api.updateSong(song.id, { genre: genre || null, style_blend: blend });
      const job = await api.generateFullSong(song.id, {
        prompt: prompt || undefined,
        genre: genre || null,
        style_blend: blend,
      });
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
  const genreLabel = genres.find((g) => g.id === genre)?.label ?? genre.replace(/_/g, " ");

  return (
    <div className="card pad-lg">
      <h3 style={{ marginTop: 0 }}>Style &amp; feel</h3>
      <p className="muted">
        Pick a feel for the whole song, then say more in words. This drives the
        structure, the tempo, the instrumental — and, if you haven&apos;t written
        any, the lyrics.
      </p>

      <div className="row tight" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ display: "block" }}>
          <span className="faint" style={{ display: "block", fontSize: "0.8rem" }}>
            Genre / feel
          </span>
          <select value={genre} onChange={(e) => setGenre(e.target.value)}>
            <option value="">— our band&apos;s own sound —</option>
            {genres.map((g) => (
              <option key={g.id} value={g.id}>
                {g.label}
              </option>
            ))}
          </select>
        </label>

        {genre && (
          <label style={{ flex: 1, minWidth: 220 }}>
            <span className="faint" style={{ display: "block", fontSize: "0.8rem" }}>
              How far toward {genreLabel}? {Math.round(blend * 100)}%
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={blend}
              style={{ width: "100%" }}
              onChange={(e) => setBlend(Number(e.target.value))}
            />
            <span className="faint" style={{ fontSize: "0.72rem" }}>
              0% = play it like your band · 100% = fully {genreLabel.toLowerCase()}
            </span>
          </label>
        )}
      </div>

      <textarea
        rows={3}
        placeholder="e.g. a driving night-time anthem, heavy chorus, melodic verses"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        style={{ marginTop: "0.7rem" }}
      />
      {err && <p className="danger">{err}</p>}
      {note && <p className="muted">{note}</p>}
      <div className="row" style={{ margin: "0.75rem 0 0" }}>
        <button className="primary big" onClick={generate} disabled={busy}>
          {busy ? "generating…" : already ? "Regenerate whole song" : "Generate song"}
        </button>
        <span className="faint">
          Builds the full structure and, for any singer/player with consent set,
          performs it too. Cast your band next and regenerate any section.
        </span>
      </div>
    </div>
  );
}
