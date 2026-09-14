"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  PLAYER_ROLES,
  PLAYER_ROLE_LABEL,
  type Genre,
  type Player,
  type PlayerPreset,
  type PlayerRole,
  type Singer,
  type Song,
} from "@/lib/api";
import { playSong } from "@/lib/player";

const EMPTY_ROLE_PICKS: Record<PlayerRole, string> = {
  lead_guitar: "", rhythm_guitar: "", bass: "", drums: "", keys: "",
};

async function waitForJob(jobId: string, rounds = 4) {
  let job = await api.waitJob(jobId);
  let n = 1;
  while (job.status !== "succeeded" && job.status !== "failed" && n < rounds) {
    job = await api.waitJob(jobId);
    n++;
  }
  return job;
}

export default function Home() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [singers, setSingers] = useState<Singer[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [presets, setPresets] = useState<PlayerPreset[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [styleTags, setStyleTags] = useState<string[]>([]);
  const [styleInput, setStyleInput] = useState("");
  const [vibe, setVibe] = useState("");
  const [lyrics, setLyrics] = useState("");
  const [pickBand, setPickBand] = useState(false);
  const [singerId, setSingerId] = useState("");
  const [rolePicks, setRolePicks] = useState<Record<PlayerRole, string>>(EMPTY_ROLE_PICKS);

  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.listSongs().then(setSongs).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    refresh();
    api.listSingers().then(setSingers).catch(() => {});
    api.listPlayers().then(setPlayers).catch(() => {});
    api.listPlayerPresets().then(setPresets).catch(() => setPresets([]));
    api.listGenres().then(setGenres).catch(() => setGenres([]));
  }, [refresh]);

  const addStyleTag = (raw: string) => {
    const v = raw.trim();
    setStyleInput("");
    if (!v) return;
    setStyleTags((cur) => (cur.some((t) => t.toLowerCase() === v.toLowerCase()) ? cur : [...cur, v]));
  };
  const removeStyleTag = (v: string) => setStyleTags((cur) => cur.filter((t) => t !== v));

  const resolveRolePlayer = async (pick: string): Promise<string | null> => {
    if (!pick) return null;
    if (pick.startsWith("p:")) return pick.slice(2);
    if (pick.startsWith("preset:")) {
      const presetId = pick.slice(7);
      const preset = presets.find((pr) => pr.id === presetId);
      if (!preset) return null;
      try {
        const created = await api.createPlayerFromPreset(presetId, preset.label);
        setPlayers((cur) => [...cur, created]);
        return created.id;
      } catch {
        // name collision, most likely — someone already added this preset under this name
        const existing = players.find((p) => p.name === preset.label);
        return existing?.id ?? null;
      }
    }
    return null;
  };

  const castSingerOnAllSections = async (songId: string, id: string) => {
    const sections = await api.listSections(songId);
    for (const sec of sections) {
      const role = await api.createSectionRole(sec.id, {
        role_type: "lead", ensemble_size: 1, width: 0,
      });
      await api.addAssignment(role.id, id, 100);
      await waitForJob((await api.renderSection(songId, sec.id)).id);
    }
  };

  const create = async () => {
    if (!title.trim() || creating) return;
    setCreating(true);
    setErr(null);
    setNote(null);
    try {
      const genreSlug = styleTags[0]?.trim().toLowerCase().replace(/\s+/g, "_") || null;
      const styleText = [styleTags.join(", "), vibe.trim()].filter(Boolean).join(". ");
      const song = await api.createSong(title.trim(), {
        prompt: styleText || undefined,
        lyrics: lyrics.trim() || undefined,
        genre: genreSlug,
      });
      // Note: not calling replaceLines here — generateFullSong reads
      // song.lyrics directly and rebuilds the section/line structure itself
      // (wastefully creating and immediately deleting rows otherwise).

      if (pickBand) {
        for (const role of PLAYER_ROLES) {
          const pid = await resolveRolePlayer(rolePicks[role]);
          if (pid) await api.setInstrument(song.id, { role, player_id: pid });
        }
      }

      const job = await api.generateFullSong(song.id, {
        prompt: styleText || undefined,
        genre: genreSlug,
      });
      const done = await waitForJob(job.id);

      if (done.status === "failed") {
        setErr(done.error || "generation failed");
      } else {
        if (pickBand && singerId) {
          setNote("Casting your singer…");
          await castSingerOnAllSections(song.id, singerId);
        }
        setNote(done.status === "succeeded" ? `"${song.title}" is ready — see it below.` : `"${song.title}" is still rendering — it'll appear below shortly.`);
      }
      setTitle("");
      setStyleTags([]);
      setVibe("");
      setLyrics("");
      setSingerId("");
      setRolePicks(EMPTY_ROLE_PICKS);
      refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setCreating(false);
    }
  };

  const remix = async (song: Song) => {
    setBusyId(song.id);
    setErr(null);
    setNote(null);
    try {
      const copy = await api.createSong(`${song.title} (remix)`, {
        prompt: song.prompt ?? undefined,
        lyrics: song.lyrics ?? undefined,
        genre: song.genre,
        style_blend: song.style_blend,
        seed: Math.floor(Math.random() * 1_000_000),
      });
      const job = await api.generateFullSong(copy.id, {
        prompt: song.prompt ?? undefined,
        genre: song.genre,
        seed: Math.floor(Math.random() * 1_000_000),
      });
      const done = await waitForJob(job.id);
      if (done.status === "failed") setErr(done.error || "remix failed");
      else setNote(`"${copy.title}" is ready — see it below.`);
      refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (song: Song) => {
    if (!confirm(`Delete "${song.title}"? This can't be undone.`)) return;
    setErr(null);
    try {
      await api.deleteSong(song.id);
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="stack">
      <section className="hero">
        <h1>Make a song with your band.</h1>
        <div className="row tight" style={{ marginTop: "0.9rem" }}>
          <a
            className="btn primary"
            href="https://github.com/Peteloaff/sr-generator/releases/latest/download/SR-Generator-desktop.zip"
          >
            ↓ Download for Windows
          </a>
          <Link href="/download" className="btn ghost sm">
            how it works &amp; setup
          </Link>
          <Link href="/help" className="btn ghost sm">
            walkthrough
          </Link>
        </div>
      </section>

      <div className="card pad-lg">
        <h2 style={{ marginTop: 0 }}>Create a song</h2>
        {err && <p className="danger">{err}</p>}
        {note && <p className="muted">{note}</p>}
        <div className="stack">
          <input
            placeholder="Song title"
            value={title}
            autoFocus
            onChange={(e) => setTitle(e.target.value)}
            style={{ fontSize: "1.05rem" }}
          />

          <div>
            <label style={{ marginBottom: "0.4rem", display: "block" }}>Style</label>
            <div
              className="row tight"
              style={{ flexWrap: "wrap", border: "1px solid var(--line)", borderRadius: 8, padding: "0.4rem" }}
            >
              {styleTags.map((t) => (
                <span key={t} className="chip toggle on">
                  {t}
                  <button
                    type="button"
                    aria-label={`remove ${t}`}
                    onClick={() => removeStyleTag(t)}
                    style={{
                      marginLeft: "0.4rem", background: "none", border: "none",
                      color: "inherit", cursor: "pointer", font: "inherit",
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                list="style-suggestions"
                placeholder={styleTags.length ? "add another…" : "type a style and press Enter — e.g. metal, ballad, driving"}
                value={styleInput}
                onChange={(e) => setStyleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") {
                    e.preventDefault();
                    addStyleTag(styleInput);
                  } else if (e.key === "Backspace" && !styleInput && styleTags.length) {
                    removeStyleTag(styleTags[styleTags.length - 1]);
                  }
                }}
                onBlur={() => addStyleTag(styleInput)}
                style={{ flex: 1, minWidth: 180, border: "none" }}
              />
              <datalist id="style-suggestions">
                {genres.map((g) => (
                  <option key={g.id} value={g.label} />
                ))}
              </datalist>
            </div>
            <input
              placeholder="anything else — mood, subject, references… (optional)"
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              style={{ marginTop: "0.4rem" }}
            />
          </div>

          <div>
            <label style={{ marginBottom: "0.4rem", display: "block" }}>Lyrics</label>
            <textarea
              rows={8}
              placeholder="One line per row. Leave blank and a placeholder scaffold fills in — come back and rewrite it after."
              value={lyrics}
              onChange={(e) => setLyrics(e.target.value)}
            />
          </div>

          <div>
            <button
              type="button"
              className="ghost sm"
              onClick={() => setPickBand(!pickBand)}
              style={{ alignSelf: "flex-start" }}
            >
              {pickBand ? "hide" : "+"} pick players / band (optional — leave closed for a generic song)
            </button>
            {pickBand && (
              <div className="card" style={{ marginTop: "0.6rem", background: "var(--surface-2)" }}>
                <div className="row space tight">
                  <p className="muted" style={{ margin: 0 }}>
                    Choose uploaded, created, predefined (signature) or leave as default for each part.
                  </p>
                  <Link href="/band" className="btn sm ghost">
                    build your band →
                  </Link>
                </div>
                <div className="grid" style={{ marginTop: "0.5rem" }}>
                  <label style={{ display: "block" }}>
                    <span className="faint" style={{ display: "block", fontSize: "0.8rem" }}>
                      Vocalist
                    </span>
                    <select value={singerId} onChange={(e) => setSingerId(e.target.value)}>
                      <option value="">— default —</option>
                      {singers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {PLAYER_ROLES.map((role) => {
                    const mine = players.filter((p) => p.role === role);
                    const defaults = presets.filter(
                      (pr) => pr.role === role && !mine.some((p) => p.name === pr.label),
                    );
                    return (
                      <label key={role} style={{ display: "block" }}>
                        <span className="faint" style={{ display: "block", fontSize: "0.8rem" }}>
                          {PLAYER_ROLE_LABEL[role]}
                        </span>
                        <select
                          value={rolePicks[role]}
                          onChange={(e) => setRolePicks({ ...rolePicks, [role]: e.target.value })}
                        >
                          <option value="">— none —</option>
                          {mine.length > 0 && (
                            <optgroup label="Your players">
                              {mine.map((p) => (
                                <option key={p.id} value={`p:${p.id}`}>
                                  {p.name}
                                </option>
                              ))}
                            </optgroup>
                          )}
                          {defaults.length > 0 && (
                            <optgroup label="Default players">
                              {defaults.map((pr) => (
                                <option key={pr.id} value={`preset:${pr.id}`}>
                                  {pr.label}
                                </option>
                              ))}
                            </optgroup>
                          )}
                        </select>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="row" style={{ margin: 0 }}>
            <button className="primary big" onClick={create} disabled={!title.trim() || creating}>
              {creating ? "generating…" : "Generate song →"}
            </button>
          </div>
        </div>
      </div>

      <div>
        <h2>Songs</h2>
        {songs.length === 0 ? (
          <div className="empty">No songs yet — create one above.</div>
        ) : (
          <div className="grid">
            {songs.map((s) => (
              <div key={s.id} className="card card-link">
                <div className="row space tight">
                  <Link href={`/song?id=${s.id}`} style={{ fontWeight: 700 }}>
                    {s.title}
                  </Link>
                  <span className={`pill ${s.status === "ready" ? "ok" : ""}`}>{s.status}</span>
                </div>
                <div className="row tight" style={{ margin: "0.3rem 0 0" }}>
                  <span className="faint" style={{ fontSize: "0.85rem" }}>
                    {s.duration ? `${s.duration.toFixed(0)}s` : "not generated"}
                    {s.key ? ` · ${s.key}` : ""}
                    {s.bpm ? ` · ${Math.round(s.bpm)} bpm` : ""}
                  </span>
                </div>
                <div className="row tight" style={{ margin: "0.5rem 0 0" }}>
                  <button
                    className="np-btn"
                    title="play"
                    disabled={s.status !== "ready"}
                    onClick={() => playSong(s, songs)}
                  >
                    ▶ play
                  </button>
                  <button
                    className="sm ghost"
                    title="remix"
                    disabled={busyId === s.id}
                    onClick={() => remix(s)}
                  >
                    {busyId === s.id ? "remixing…" : "⤾ remix"}
                  </button>
                  <button className="danger sm" title="delete" onClick={() => remove(s)}>
                    delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
