"use client";

import { Fragment, use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
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

export default function SongWorkspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [song, setSong] = useState<Song | null>(null);
  const [singers, setSingers] = useState<Singer[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [lines, setLines] = useState<LyricLine[]>([]);
  const [asset, setAsset] = useState<AudioAsset | null>(null);
  const [wave, setWave] = useState<WaveformData | null>(null);
  const [lyricsDraft, setLyricsDraft] = useState("");
  const [openSection, setOpenSection] = useState<string | null>(null);
  const [openLine, setOpenLine] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
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
      setLyricsDraft(ln.map((l) => l.text).join("\n"));
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

  if (err) return <p className="danger">{err}</p>;
  if (!song) return <p className="muted">loading…</p>;

  return (
    <div>
      <p>
        <Link href="/songs">← songs</Link>
      </p>
      <h1>{song.title}</h1>

      <div className="row">
        {(["bpm", "key", "seed"] as const).map((f) => (
          <label key={f}>
            {f}{" "}
            <input
              defaultValue={song[f] ?? ""}
              style={{ width: 70 }}
              onBlur={(e) => {
                const v = e.target.value;
                api
                  .updateSong(id, {
                    [f]: v === "" ? null : f === "key" ? v : Number(v),
                  } as Partial<Song>)
                  .then(setSong);
              }}
            />
          </label>
        ))}
        <span className="muted">
          {song.duration ? `${song.duration.toFixed(1)}s` : "no audio"}
        </span>
      </div>

      <h2>Audio</h2>
      {asset ? (
        <>
          <Waveform peaks={wave?.peaks ?? []} duration={song.duration} sections={sections} />
          <p className="muted">
            {asset.sample_rate} Hz · {asset.channels} ch · {asset.file_path}
          </p>
        </>
      ) : (
        <p className="muted">no audio uploaded yet</p>
      )}
      <input
        type="file"
        accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
        onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
      />

      <h2>Sections</h2>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Name</th>
            <th>Start</th>
            <th>End</th>
            <th>Vocal Director</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sections.map((s) => (
            <Fragment key={s.id}>
              <tr>
                <td>
                  <span className="pill" style={{ borderColor: sectionColor(s.section_type) }}>
                    <select
                      value={s.section_type}
                      onChange={(e) =>
                        api.updateSection(id, s.id, { section_type: e.target.value }).then(loadAll)
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
                    onBlur={(e) => api.updateSection(id, s.id, { name: e.target.value })}
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
                          .updateSection(id, s.id, {
                            [f]: e.target.value === "" ? null : Number(e.target.value),
                          })
                          .then(loadAll)
                      }
                    />
                  </td>
                ))}
                <td>
                  <button onClick={() => setOpenSection(openSection === s.id ? null : s.id)}>
                    {openSection === s.id ? "close" : "edit"}
                  </button>
                </td>
                <td>
                  <button className="danger" onClick={() => api.deleteSection(id, s.id).then(loadAll)}>
                    delete
                  </button>
                </td>
              </tr>
              {openSection === s.id && (
                <tr>
                  <td colSpan={6}>
                    <VocalDirector scope="section" id={s.id} singers={singers} />
                    <SectionRender songId={id} sectionId={s.id} singers={singers} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      <button
        onClick={() =>
          api
            .createSection(id, { section_type: "verse", order_index: sections.length })
            .then(loadAll)
        }
      >
        add section
      </button>

      <h2>Lyrics</h2>
      <p className="muted">One line per row. Save rebuilds the line list.</p>
      <textarea
        rows={8}
        style={{ width: "100%" }}
        value={lyricsDraft}
        onChange={(e) => setLyricsDraft(e.target.value)}
      />
      <div className="row">
        <button onClick={() => api.replaceLines(id, lyricsDraft).then(loadAll)}>save lyrics</button>
      </div>

      {lines.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Line</th>
              <th>Section</th>
              <th>Per-line singer(s)</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <Fragment key={l.id}>
                <tr>
                  <td className="muted">{l.order_index + 1}</td>
                  <td>{l.text || <span className="muted">(blank)</span>}</td>
                  <td>
                    <select
                      value={l.section_id ?? ""}
                      onChange={(e) =>
                        api
                          .updateLine(id, l.id, { section_id: e.target.value || null })
                          .then(loadAll)
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
                    <button onClick={() => setOpenLine(openLine === l.id ? null : l.id)}>
                      {openLine === l.id ? "close" : "override"}
                    </button>
                  </td>
                </tr>
                {openLine === l.id && (
                  <tr>
                    <td colSpan={4}>
                      <p className="muted">
                        Roles set here override the section for this line only.
                      </p>
                      <VocalDirector scope="line" id={l.id} singers={singers} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
