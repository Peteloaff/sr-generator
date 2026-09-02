"use client";

import { Fragment, Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  api,
  assetUrl,
  SECTION_TYPES,
  type AudioAsset,
  type LyricLine,
  type Section,
  type Singer,
  type Song,
  type Waveform as WaveformData,
} from "@/lib/api";
import Waveform, { sectionColor } from "@/components/Waveform";
import VocalDirector from "@/components/VocalDirector";
import SectionRender from "@/components/SectionRender";
import CoverStudio from "@/components/CoverStudio";
import GeneratePanel from "@/components/GeneratePanel";
import ArrangerPanel from "@/components/ArrangerPanel";
import SingerCard from "@/components/SingerCard";

type Step = "story" | "cast" | "studio";

const STEPS: { id: Step; label: string; hint: string }[] = [
  { id: "story", label: "Story", hint: "title, style, lyrics" },
  { id: "cast", label: "Cast", hint: "who sings what" },
  { id: "studio", label: "Studio", hint: "generate & listen" },
];

export default function SongWorkspacePage() {
  return (
    <Suspense fallback={<p className="muted">loading…</p>}>
      <SongWorkspace />
    </Suspense>
  );
}

function SongWorkspace() {
  const id = useSearchParams().get("id") ?? "";

  const [song, setSong] = useState<Song | null>(null);
  const [singers, setSingers] = useState<Singer[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [lines, setLines] = useState<LyricLine[]>([]);
  const [asset, setAsset] = useState<AudioAsset | null>(null);
  const [wave, setWave] = useState<WaveformData | null>(null);
  const [lyricsDraft, setLyricsDraft] = useState("");
  const [step, setStep] = useState<Step>("story");
  const [castOpen, setCastOpen] = useState<string | null>(null);
  const [studioOpen, setStudioOpen] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    if (!id) return;
    try {
      const [s, sg, sec, ln, assets] = await Promise.all([
        api.getSong(id),
        api.listSingers(),
        api.listSections(id),
        api.listLines(id),
        api.listAssets(id),
      ]);
      setSong(s);
      setSingers(sg);
      setSections(sec);
      setLines(ln);
      setLyricsDraft(s.lyrics ?? ln.map((l) => l.text).join("\n"));
      const upload = assets.find((a) => a.asset_type === "upload") ?? null;
      setAsset(upload);
      if (upload) setWave(await api.waveform(id, upload.id));
    } catch (e) {
      setErr(String(e));
    }
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const onUpload = async (file: File) => {
    setErr(null);
    try {
      await api.uploadAudio(id, file);
      loadAll();
    } catch (e) {
      setErr(String(e));
    }
  };

  const saveLyrics = async () => {
    setErr(null);
    try {
      await api.updateSong(id, { lyrics: lyricsDraft });
      await api.replaceLines(id, lyricsDraft);
      loadAll();
    } catch (e) {
      setErr(String(e));
    }
  };

  if (!id) return <p className="danger">No song id in the URL.</p>;
  if (err) return <p className="danger">{err}</p>;
  if (!song) return <p className="muted">loading…</p>;

  return (
    <div>
      <p>
        <Link href="/songs">← songs</Link>
      </p>
      <div className="row space" style={{ marginTop: 0 }}>
        <input
          defaultValue={song.title}
          style={{ fontSize: "1.5rem", fontWeight: 700, border: "none", background: "transparent", padding: 0 }}
          onBlur={(e) => e.target.value.trim() && api.updateSong(id, { title: e.target.value.trim() }).then(setSong)}
        />
        <span className={`pill ${song.status === "ready" ? "ok" : ""}`}>{song.status}</span>
      </div>
      <p className="faint" style={{ marginTop: "-0.4rem" }}>
        {song.bpm ? `${Math.round(song.bpm)} bpm` : "no tempo yet"}
        {song.key ? ` · ${song.key}` : ""}
        {song.duration ? ` · ${song.duration.toFixed(0)}s` : ""}
      </p>

      <nav className="stepnav">
        {STEPS.map((s, i) => (
          <button key={s.id} className={step === s.id ? "on" : ""} onClick={() => setStep(s.id)}>
            <span className="n">{i + 1}</span>
            {s.label}
            <span className="faint" style={{ display: "block", fontWeight: 400, fontSize: "0.78rem" }}>
              {s.hint}
            </span>
          </button>
        ))}
      </nav>

      {step === "story" && (
        <StoryStep
          song={song}
          sections={sections}
          lyricsDraft={lyricsDraft}
          setLyricsDraft={setLyricsDraft}
          saveLyrics={saveLyrics}
          asset={asset}
          wave={wave}
          onUpload={onUpload}
          onChange={loadAll}
          showAdvanced={showAdvanced}
          setShowAdvanced={setShowAdvanced}
        />
      )}

      {step === "cast" && (
        <CastStep
          songId={id}
          singers={singers}
          sections={sections}
          lines={lines}
          castOpen={castOpen}
          setCastOpen={setCastOpen}
          onChange={loadAll}
        />
      )}

      {step === "studio" && (
        <StudioStep
          song={song}
          songId={id}
          sections={sections}
          singers={singers}
          studioOpen={studioOpen}
          setStudioOpen={setStudioOpen}
          onChange={loadAll}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Story ---

function StoryStep({
  song,
  sections,
  lyricsDraft,
  setLyricsDraft,
  saveLyrics,
  asset,
  wave,
  onUpload,
  onChange,
  showAdvanced,
  setShowAdvanced,
}: {
  song: Song;
  sections: Section[];
  lyricsDraft: string;
  setLyricsDraft: (v: string) => void;
  saveLyrics: () => void;
  asset: AudioAsset | null;
  wave: WaveformData | null;
  onUpload: (f: File) => void;
  onChange: () => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}) {
  return (
    <div className="stack">
      <GeneratePanel song={song} onChange={onChange} />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Lyrics</h3>
        <p className="muted">
          One line per row. Leave blank and generate — a placeholder scaffold
          fills in so you can hear the structure, then come back and rewrite it.
        </p>
        <textarea rows={10} value={lyricsDraft} onChange={(e) => setLyricsDraft(e.target.value)} />
        <div className="row" style={{ margin: "0.6rem 0 0" }}>
          <button className="primary" onClick={saveLyrics}>
            Save lyrics
          </button>
        </div>
      </div>

      <div className="card">
        <div className="row space tight">
          <h3 style={{ margin: 0 }}>Cover an existing recording (optional)</h3>
        </div>
        <p className="muted">
          Prefer to start from a demo instead of generating from scratch? Upload
          a mix here to separate stems and replace the vocal, keeping the melody.
        </p>
        {asset ? (
          <>
            <Waveform peaks={wave?.peaks ?? []} duration={song.duration} sections={sections} />
            <CoverStudio songId={song.id} />
          </>
        ) : (
          <input
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
            onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          />
        )}
      </div>

      <button className="ghost sm" onClick={() => setShowAdvanced(!showAdvanced)} style={{ alignSelf: "flex-start" }}>
        {showAdvanced ? "hide" : "show"} manual section editor
      </button>
      {showAdvanced && <ManualSections songId={song.id} sections={sections} onChange={onChange} />}
    </div>
  );
}

function ManualSections({
  songId,
  sections,
  onChange,
}: {
  songId: string;
  sections: Section[];
  onChange: () => void;
}) {
  return (
    <div className="card">
      <p className="muted">
        Sections are normally created for you when you generate. Add or adjust
        them by hand if you're building a song manually.
      </p>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Name</th>
            <th>Start</th>
            <th>End</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sections.map((s) => (
            <tr key={s.id}>
              <td>
                <span className="pill" style={{ borderColor: sectionColor(s.section_type) }}>
                  <select
                    value={s.section_type}
                    onChange={(e) =>
                      api.updateSection(songId, s.id, { section_type: e.target.value }).then(onChange)
                    }
                  >
                    {SECTION_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </span>
              </td>
              <td>
                <input
                  defaultValue={s.name ?? ""}
                  style={{ width: 110 }}
                  onBlur={(e) => api.updateSection(songId, s.id, { name: e.target.value })}
                />
              </td>
              {(["start_time", "end_time"] as const).map((f) => (
                <td key={f}>
                  <input
                    type="number"
                    defaultValue={s[f] ?? ""}
                    style={{ width: 60 }}
                    onBlur={(e) =>
                      api
                        .updateSection(songId, s.id, {
                          [f]: e.target.value === "" ? null : Number(e.target.value),
                        })
                        .then(onChange)
                    }
                  />
                </td>
              ))}
              <td>
                <button className="danger sm" onClick={() => api.deleteSection(songId, s.id).then(onChange)}>
                  delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        className="sm"
        onClick={() =>
          api.createSection(songId, { section_type: "verse", order_index: sections.length }).then(onChange)
        }
      >
        add section
      </button>
    </div>
  );
}

// ----------------------------------------------------------------- Cast ---

function CastStep({
  songId,
  singers,
  sections,
  lines,
  castOpen,
  setCastOpen,
  onChange,
}: {
  songId: string;
  singers: Singer[];
  sections: Section[];
  lines: LyricLine[];
  castOpen: string | null;
  setCastOpen: (v: string | null) => void;
  onChange: () => void;
}) {
  const [openLine, setOpenLine] = useState<string | null>(null);

  return (
    <div className="stack">
      <div className="card">
        <div className="row space tight">
          <h3 style={{ margin: 0 }}>Your band</h3>
          <Link href="/singers" className="btn sm ghost">
            manage singers
          </Link>
        </div>
        {singers.length === 0 ? (
          <div className="empty">
            No singers yet. <Link href="/singers">Add one, or record your own voice.</Link>
          </div>
        ) : (
          <div className="grid">
            {singers.map((s) => (
              <SingerCard key={s.id} singer={s} onChange={onChange} isMe={s.name === "Me"} />
            ))}
          </div>
        )}
      </div>

      {sections.length === 0 ? (
        <div className="empty">Generate the song on the Story step first to get sections to cast.</div>
      ) : (
        <>
          <ArrangerPanel songId={songId} singers={singers} onChange={onChange} />

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Sections</h3>
            <p className="muted">Fine-tune who sings each part.</p>
            <div className="stack">
              {sections.map((s) => (
                <div key={s.id} className="role-card" style={{ background: "var(--surface-2)" }}>
                  <div className="row space tight">
                    <strong>
                      {s.name || s.section_type}{" "}
                      <span className="faint">({s.section_type})</span>
                      {s.locked ? " 🔒" : ""}
                    </strong>
                    <button className="sm ghost" onClick={() => setCastOpen(castOpen === s.id ? null : s.id)}>
                      {castOpen === s.id ? "close" : "edit cast"}
                    </button>
                  </div>
                  {castOpen === s.id && <VocalDirector scope="section" id={s.id} singers={singers} />}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {lines.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Per-line overrides</h3>
          <p className="muted">Rare, but a specific line can override its section's cast.</p>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Line</th>
                <th>Section</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <Fragment key={l.id}>
                  <tr>
                    <td className="faint">{l.order_index + 1}</td>
                    <td>{l.text || <span className="muted">(blank)</span>}</td>
                    <td>
                      <select
                        value={l.section_id ?? ""}
                        onChange={(e) =>
                          api.updateLine(songId, l.id, { section_id: e.target.value || null }).then(onChange)
                        }
                      >
                        <option value="">— none —</option>
                        {sections.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name || s.section_type}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button className="sm ghost" onClick={() => setOpenLine(openLine === l.id ? null : l.id)}>
                        {openLine === l.id ? "close" : "override"}
                      </button>
                    </td>
                  </tr>
                  {openLine === l.id && (
                    <tr>
                      <td colSpan={4}>
                        <VocalDirector scope="line" id={l.id} singers={singers} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Studio ---

function StudioStep({
  song,
  songId,
  sections,
  singers,
  studioOpen,
  setStudioOpen,
  onChange,
}: {
  song: Song;
  songId: string;
  sections: Section[];
  singers: Singer[];
  studioOpen: string | null;
  setStudioOpen: (v: string | null) => void;
  onChange: () => void;
}) {
  const [assets, setAssets] = useState<AudioAsset[]>([]);

  const refresh = useCallback(async () => {
    setAssets(await api.listAssets(songId));
    onChange();
  }, [songId, onChange]);

  useEffect(() => {
    api.listAssets(songId).then(setAssets);
  }, [songId]);

  const songLevel = assets.filter((a) => !a.section_id);
  const master = songLevel.find((a) => a.asset_type === "song_master");
  const mix = songLevel.find((a) => a.asset_type === "song_mix");
  const stems = songLevel.filter((a) => a.asset_type !== "song_master" && a.asset_type !== "song_mix");

  return (
    <div className="stack">
      <div className="card pad-lg">
        <h3 style={{ marginTop: 0 }}>Full mix</h3>
        {master || mix ? (
          <div className="stack" style={{ gap: "0.6rem" }}>
            {master && (
              <div>
                <div className="row tight" style={{ margin: "0.2rem 0" }}>
                  <span className="pill ok">master</span>
                  <a href={assetUrl(songId, master.id)}>download</a>
                </div>
                <audio controls preload="none" src={assetUrl(songId, master.id, { inline: true })} />
              </div>
            )}
            {mix && (
              <div>
                <div className="row tight" style={{ margin: "0.2rem 0" }}>
                  <span className="pill">mix</span>
                  <a href={assetUrl(songId, mix.id)}>download</a>
                </div>
                <audio controls preload="none" src={assetUrl(songId, mix.id, { inline: true })} />
              </div>
            )}
            {stems.length > 0 && (
              <details>
                <summary className="muted">song-level stems ({stems.length})</summary>
                <table>
                  <tbody>
                    {stems.map((a) => (
                      <tr key={a.id}>
                        <td style={{ whiteSpace: "nowrap" }}>{a.asset_type.replace(/_/g, " ")}</td>
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
              </details>
            )}
          </div>
        ) : (
          <div className="empty">
            Nothing generated yet — go to the Story step and hit "Generate song".
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Sections</h3>
        <p className="muted">
          Open a section to re-render it, regenerate a single layer, swap a
          singer, lock it, or roll back — the rest of the song stays untouched.
        </p>
        {sections.length === 0 && <div className="empty">No sections yet.</div>}
        <div className="stack">
          {sections.map((s) => (
            <div key={s.id} className="role-card" style={{ background: "var(--surface-2)" }}>
              <div className="row space tight">
                <strong>
                  {s.name || s.section_type} <span className="faint">({s.section_type})</span>
                  {s.locked ? " 🔒" : ""}
                </strong>
                <button
                  className="sm ghost"
                  onClick={() => setStudioOpen(studioOpen === s.id ? null : s.id)}
                >
                  {studioOpen === s.id ? "close" : "open"}
                </button>
              </div>
              {studioOpen === s.id && (
                <SectionRender songId={songId} section={s} singers={singers} onChange={refresh} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
