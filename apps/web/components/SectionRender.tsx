"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  assetUrl,
  getBandId,
  type ABResult,
  type AudioAsset,
  type BandAdapter,
  type Job,
  type Morph,
  type RenderTake,
  type Section,
  type SectionRevision,
  type Singer,
  type VocalPreset,
  type VocalRole,
} from "@/lib/api";

const STEM_ORDER = [
  "master", "mix", "vocal_bus", "stem_instrumental",
  "stem_lead_vocal", "stem_background_vocal", "stem_gang_vocal",
  "role_stem", "take_stem",
];

function stemRank(t: string) {
  const i = STEM_ORDER.indexOf(t);
  return i === -1 ? 99 : i;
}

export default function SectionRender({
  songId,
  section,
  singers,
  onChange,
}: {
  songId: string;
  section: Section;
  singers: Singer[];
  onChange?: () => void;
}) {
  const sectionId = section.id;
  const [takes, setTakes] = useState<AudioAsset[]>([]);
  const [renders, setRenders] = useState<Job[]>([]);
  const [takeRows, setTakeRows] = useState<RenderTake[]>([]);
  const [roles, setRoles] = useState<VocalRole[]>([]);
  const [guide, setGuide] = useState<AudioAsset | null>(null);
  const [presets, setPresets] = useState<VocalPreset[]>([]);
  const [ab, setAb] = useState<ABResult | null>(null);
  const [adapters, setAdapters] = useState<BandAdapter[]>([]);
  const [generations, setGenerations] = useState<Job[]>([]);
  const [adapterId, setAdapterId] = useState<string>("");
  const [revisions, setRevisions] = useState<SectionRevision[]>([]);
  const [morphEnabled, setMorphEnabled] = useState(false);
  const [morphs, setMorphs] = useState<Morph[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const singersInSection = Array.from(
    new Set(roles.flatMap((r) => r.assignments.map((a) => a.singer_id))),
  )
    .map((id) => singers.find((s) => s.id === id))
    .filter((s): s is Singer => !!s);

  const load = useCallback(async () => {
    const bandId = getBandId() ?? (await api.listBands())[0]?.id ?? null;
    const [t, r, rl, sa, pr, g, ad, rev, exp] = await Promise.all([
      api.listSourceTakes(songId, sectionId),
      api.listSectionRenders(songId, sectionId),
      api.sectionRoles(sectionId),
      api.listAssets(songId),
      api.listPresets(),
      api.listGenerations(songId, sectionId),
      bandId ? api.listAdapters(bandId) : Promise.resolve([] as BandAdapter[]),
      api.listRevisions(sectionId),
      api.experimentalStatus(),
    ]);
    setTakes(t);
    setRenders(r);
    setRoles(rl);
    setPresets(pr);
    setGenerations(g);
    setAdapters(ad);
    setRevisions(rev);
    setMorphEnabled(exp.morph_enabled);
    setMorphs(exp.morph_enabled ? await api.listMorphs(sectionId) : []);
    setGuide(
      sa.find((a) => a.asset_type === "guide_vocal" && a.section_id === sectionId) ?? null,
    );
    if (r[0]) setTakeRows(await api.listRenderTakes(songId, r[0].id));
    else setTakeRows([]);
  }, [songId, sectionId]);

  useEffect(() => {
    load();
  }, [load]);

  const uploadTake = async (singerId: string, file: File) => {
    setErr(null);
    try {
      await api.uploadSourceTake(songId, sectionId, singerId, file);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const render = async () => {
    setBusy(true);
    setErr(null);
    try {
      const job = await api.renderSection(songId, sectionId, {});
      await api.waitJob(job.id);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runAB = async () => {
    setBusy(true);
    setErr(null);
    try {
      setAb(await api.renderAB(songId, sectionId));
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const savePreset = async () => {
    const name = window.prompt("Preset name (e.g. 'Big Chorus')");
    if (!name) return;
    try {
      await api.savePresetFromSection(name, sectionId);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const applyPreset = async (presetId: string) => {
    try {
      const res = await api.applyPreset(presetId, sectionId);
      if (res.skipped_singers.length) setErr(`skipped: ${res.skipped_singers.join(", ")}`);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const latest = renders[0];
  const takenBy = new Set(takes.map((t) => t.singer_id));
  const nameOf = (id: string) => singers.find((s) => s.id === id)?.name ?? "?";

  const uploadGuide = async (file: File) => {
    setErr(null);
    try {
      await api.uploadGuide(songId, sectionId, file);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const useSeparated = async () => {
    setErr(null);
    try {
      await api.useDerivedStems(songId, sectionId);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const generateBed = async () => {
    setBusy(true);
    setErr(null);
    try {
      const job = await api.generateInstrumental(songId, sectionId, {
        prompt: "band instrumental",
        adapter_id: adapterId || null,
      });
      await api.waitJob(job.id);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const lastGen = generations[0];
  const refresh = async () => {
    await load();
    onChange?.();
  };

  const runJob = async (tag: string, mk: () => Promise<Job>) => {
    setBusy(true);
    setErr(null);
    try {
      const job = await mk();
      const done = await api.waitJob(job.id);
      if (done.status !== "succeeded") setErr(done.error || `${tag} failed`);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleLock = async () => {
    setErr(null);
    try {
      await api.lockSection(sectionId, !section.locked);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  const rollback = async (revision: number) => {
    setErr(null);
    try {
      await api.rollbackSection(sectionId, revision);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="section-render">
      {err && <p className="danger">{err}</p>}

      <h4>Surgical regeneration</h4>
      <div className="row">
        <label>
          <input type="checkbox" checked={section.locked} onChange={toggleLock} /> locked
        </label>
        <button
          disabled={busy || section.locked}
          onClick={() => runJob("regenerate", () => api.regenerateSection(sectionId))}
        >
          {busy ? "working…" : "Regenerate section"}
        </button>
        {revisions[0] && (
          <span className="muted">
            revision {revisions[0].revision} ({revisions[0].kind})
          </span>
        )}
      </div>
      {roles.length > 0 && (
        <div className="row">
          <span className="muted">regenerate one layer:</span>
          {roles.map((r) => (
            <button
              key={r.id}
              disabled={busy || section.locked}
              onClick={() => runJob("role", () => api.regenerateRole(r.id))}
            >
              {r.role_type}
            </button>
          ))}
        </div>
      )}
      {revisions.length > 1 && (
        <div className="row">
          <span className="muted">rollback to:</span>
          {revisions
            .slice()
            .reverse()
            .map((rev) => (
              <button
                key={rev.id}
                disabled={busy || section.locked || rev.is_current}
                onClick={() => rollback(rev.revision)}
              >
                r{rev.revision}
              </button>
            ))}
        </div>
      )}

      {morphEnabled && (
        <MorphLane
          sectionId={sectionId}
          songId={songId}
          singers={singersInSection}
          morphs={morphs}
          onChange={refresh}
        />
      )}

      <h4>Guide vocal</h4>
      <p className="muted">
        One melody/phrase for the section. Any singer with a ready voice model (and
        no uploaded take) has the guide converted into their voice.
      </p>
      <div className="row">
        {guide ? (
          <>
            <span className="pill">uploaded</span>
            <audio controls preload="none" src={assetUrl(songId, guide.id, { inline: true })} />
          </>
        ) : (
          <span className="muted">no guide vocal</span>
        )}
        <input
          type="file"
          accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
          onChange={(e) => e.target.files?.[0] && uploadGuide(e.target.files[0])}
        />
        <button onClick={useSeparated} title="slice this song's separated stems into this section">
          Use separated stems
        </button>
      </div>

      <h4>Generated instrumental bed</h4>
      <p className="muted">
        Render a deterministic instrumental for this section with the music provider,
        tempo/key-locked to the song. It becomes the section&apos;s bed, so band vocals
        render over it.
      </p>
      <div className="row">
        <select value={adapterId} onChange={(e) => setAdapterId(e.target.value)}>
          <option value="">no adapter (priors from song)</option>
          {adapters.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} · {a.dataset_version ?? "—"}
            </option>
          ))}
        </select>
        <button onClick={generateBed} disabled={busy}>
          {busy ? "working…" : "Generate instrumental"}
        </button>
        {lastGen && (
          <span className="muted">
            {generations.length} generation{generations.length === 1 ? "" : "s"} · latest{" "}
            {lastGen.status}
          </span>
        )}
      </div>
      {lastGen?.status === "succeeded" &&
        lastGen.outputs
          .filter((o) => o.asset_type === "instrumental_bed")
          .map((o) => (
            <div className="row" key={o.id}>
              <span className="muted">{o.label}</span>
              <audio controls preload="none" src={assetUrl(songId, o.id, { inline: true })} />
              <a href={assetUrl(songId, o.id)}>download</a>
            </div>
          ))}

      <h4>Source takes</h4>
      <p className="muted">
        A real recording of a singer overrides both the guide conversion and the
        placeholder for that singer.
      </p>
      <table>
        <tbody>
          {singersInSection.map((s) => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td>
                <span className="pill">
                  {takenBy.has(s.id) ? "uploaded" : guide ? "guide → voice" : "placeholder"}
                </span>
              </td>
              <td>
                <input
                  ref={(el) => {
                    fileRefs.current[s.id] = el;
                  }}
                  type="file"
                  accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
                  onChange={(e) => e.target.files?.[0] && uploadTake(s.id, e.target.files[0])}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Presets</h4>
      <div className="row">
        <button onClick={savePreset}>Save section as preset</button>
        <select value="" onChange={(e) => e.target.value && applyPreset(e.target.value)}>
          <option value="">Apply preset…</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <div className="row">
        <button onClick={render} disabled={busy}>
          {busy ? "working…" : "Render section"}
        </button>
        <button onClick={runAB} disabled={busy} title="ensemble vs naive gain stack">
          Render A/B
        </button>
        {latest && (
          <span className="muted">
            {renders.length} render{renders.length === 1 ? "" : "s"} · latest seed{" "}
            {latest.seed ?? "—"} · {latest.status}
          </span>
        )}
      </div>

      {ab && (
        <div className="ab">
          <strong>
            A/B — ensemble is{" "}
            {ab.verdict.ensemble_clearly_different ? "clearly different" : "NOT clearly different"}
          </strong>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>width</th>
                <th>L/R correlation</th>
                <th>mono-compat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {([
                ["flat gain stack", ab.flat, ab.flat_job_id],
                ["ensemble", ab.ensemble, ab.ensemble_job_id],
              ] as const).map(([label, m, jobId]) => {
                const masterId = renders
                  .find((r) => r.id === jobId)
                  ?.outputs.find((o) => o.asset_type === "master")?.id;
                return (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>{Number(m.width_ratio).toFixed(3)}</td>
                    <td>{Number(m.stereo_correlation).toFixed(3)}</td>
                    <td>{Number(m.mono_compat).toFixed(3)}</td>
                    <td>
                      {masterId && (
                        <audio
                          controls
                          preload="none"
                          src={assetUrl(songId, masterId, { inline: true })}
                        />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {latest && latest.status === "succeeded" && (
        <>
          <h4>Stems &amp; mix</h4>
          <table>
            <tbody>
              {[...latest.outputs]
                .sort((a, b) => stemRank(a.asset_type) - stemRank(b.asset_type))
                .map((o) => (
                  <tr key={o.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <strong>{o.asset_type.replace(/_/g, " ")}</strong>
                      <br />
                      <span className="muted">{o.label}</span>
                    </td>
                    <td style={{ width: "100%" }}>
                      <audio controls preload="none" src={assetUrl(songId, o.id, { inline: true })} />
                    </td>
                    <td>
                      <a href={assetUrl(songId, o.id)}>download</a>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>

          <h4>Take breakdown</h4>
          <table>
            <thead>
              <tr>
                <th>Singer</th>
                <th>Take</th>
                <th>Source</th>
                <th>Timing (ms)</th>
                <th>Pitch (cents)</th>
                <th>Pan</th>
                <th>Gain (dB)</th>
              </tr>
            </thead>
            <tbody>
              {takeRows.map((t) => (
                <tr key={t.id}>
                  <td>{nameOf(t.singer_id)}</td>
                  <td>{t.take_index + 1}</td>
                  <td>
                    <span className="pill">{t.source_kind}</span>
                  </td>
                  <td>{t.timing_offset_ms.toFixed(1)}</td>
                  <td>{t.pitch_cents.toFixed(1)}</td>
                  <td>{t.pan.toFixed(0)}</td>
                  <td>{t.gain_db.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function MorphLane({
  sectionId,
  songId,
  singers,
  morphs,
  onChange,
}: {
  sectionId: string;
  songId: string;
  singers: Singer[];
  morphs: Morph[];
  onChange: () => void;
}) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nameOf = (id: string) => singers.find((s) => s.id === id)?.name ?? id.slice(0, 6);

  const wrap = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      onChange();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <details style={{ marginTop: 8 }}>
      <summary>Vocal morph (experimental)</summary>
      <p className="muted">
        Automates a transition from one singer identity to another across the
        section. Preview-only: a morph flagged unreliable cannot be committed.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <select value={from} onChange={(e) => setFrom(e.target.value)}>
          <option value="">from…</option>
          {singers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select value={to} onChange={(e) => setTo(e.target.value)}>
          <option value="">to…</option>
          {singers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button
          disabled={busy || !from || !to || from === to}
          onClick={() =>
            wrap(async () => {
              await api.createMorph(sectionId, { from_singer_id: from, to_singer_id: to });
            })
          }
        >
          add morph
        </button>
      </div>
      {morphs.map((m) => (
        <div key={m.id} className="row">
          <span>
            {nameOf(m.from_singer_id)} → {nameOf(m.to_singer_id)} ({m.curve})
          </span>
          <button
            disabled={busy}
            onClick={() =>
              wrap(async () => {
                const j = await api.previewMorph(m.id);
                await api.waitJob(j.id);
              })
            }
          >
            preview
          </button>
          {m.quality && (
            <span className={m.quality.usable ? "muted" : "danger"}>
              score {m.quality.score} {m.quality.flags.join(",") || "clean"}
              {m.quality.usable ? "" : " — not committable"}
            </span>
          )}
          {m.preview_asset_id && (
            <audio
              controls
              preload="none"
              src={assetUrl(songId, m.preview_asset_id, { inline: true })}
            />
          )}
          {m.quality?.usable && !m.committed && (
            <button
              disabled={busy}
              onClick={() => wrap(async () => void (await api.commitMorph(m.id)))}
            >
              commit
            </button>
          )}
          {m.committed && <span className="pill">committed</span>}
          <button
            className="danger"
            disabled={busy}
            onClick={() => wrap(async () => await api.deleteMorph(m.id))}
          >
            delete
          </button>
        </div>
      ))}
    </details>
  );
}
