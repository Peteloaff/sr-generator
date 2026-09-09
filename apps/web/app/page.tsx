"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type Singer, type Song } from "@/lib/api";
import { playSong } from "@/lib/player";

const STYLE_CHIPS = [
  "driving", "anthemic", "melodic", "heavy", "electronic",
  "ballad", "aggressive", "atmospheric", "uplifting", "dark",
];

export default function Home() {
  const router = useRouter();
  const [songs, setSongs] = useState<Song[]>([]);
  const [singers, setSingers] = useState<Singer[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [styles, setStyles] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.listSongs().then(setSongs).catch((e) => setErr(String(e)));
    api.listSingers().then(setSingers).catch(() => {});
  }, []);

  const toggleStyle = (s: string) =>
    setStyles((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const create = async () => {
    if (!title.trim() || creating) return;
    setCreating(true);
    setErr(null);
    try {
      const promptText = [styles.join(", "), prompt.trim()].filter(Boolean).join(". ");
      const song = await api.createSong(title.trim(), promptText ? { prompt: promptText } : {});
      router.push(`/song?id=${song.id}`);
    } catch (e) {
      setErr(String(e));
      setCreating(false);
    }
  };

  return (
    <div>
      <section className="hero">
        <h1>Make a song with your band.</h1>
        <p className="lede">
          Write the words and the vibe, cast your singers and players on every
          section, then generate a full, editable track — stems and all.
        </p>
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
        <h3 style={{ marginTop: 0 }}>Create a song</h3>
        {err && <p className="danger">{err}</p>}
        <div className="stack">
          <input
            placeholder="Song title"
            value={title}
            autoFocus
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            style={{ fontSize: "1.05rem" }}
          />
          <div>
            <label style={{ marginBottom: "0.4rem", display: "block" }}>Style</label>
            <div className="row tight" style={{ gap: "0.4rem" }}>
              {STYLE_CHIPS.map((s) => (
                <span
                  key={s}
                  className={`chip toggle ${styles.includes(s) ? "on" : ""}`}
                  onClick={() => toggleStyle(s)}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
          <textarea
            rows={2}
            placeholder="Anything else about the song — mood, subject, references…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="row" style={{ margin: 0 }}>
            <button className="primary big" onClick={create} disabled={!title.trim() || creating}>
              {creating ? "creating…" : "Create song →"}
            </button>
            <span className="faint">You'll add lyrics and singers on the next screen.</span>
          </div>
        </div>
      </div>

      <h2>Your songs</h2>
      {songs.length === 0 ? (
        <div className="empty">No songs yet — create one above.</div>
      ) : (
        <div className="grid">
          {songs
            .slice()
            .reverse()
            .map((s) => (
              <div key={s.id} className="card card-link">
                <div className="row space tight">
                  <Link href={`/song?id=${s.id}`} style={{ fontWeight: 700 }}>
                    {s.title}
                  </Link>
                  <span className={`pill ${s.status === "ready" ? "ok" : ""}`}>{s.status}</span>
                </div>
                <div className="row tight" style={{ margin: "0.3rem 0 0" }}>
                  {s.status === "ready" && (
                    <button
                      className="np-btn"
                      title="play"
                      onClick={() => playSong(s, songs.slice().reverse())}
                    >
                      ▶ play
                    </button>
                  )}
                  <span className="faint" style={{ fontSize: "0.85rem" }}>
                    {s.duration ? `${s.duration.toFixed(0)}s` : "not generated"}
                    {s.key ? ` · ${s.key}` : ""}
                    {s.bpm ? ` · ${Math.round(s.bpm)} bpm` : ""}
                  </span>
                </div>
              </div>
            ))}
        </div>
      )}

      <h2>Your band</h2>
      <div className="row" style={{ gap: "0.5rem" }}>
        {singers.map((s) => (
          <span key={s.id} className={`chip ${s.training_status === "ready" ? "ok" : ""}`}>
            {s.name}
          </span>
        ))}
        <Link href="/singers" className="btn sm ghost">
          {singers.length ? "Manage singers & record voices" : "Add singers & record your voice"}
        </Link>
      </div>
    </div>
  );
}
