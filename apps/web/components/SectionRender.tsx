"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  assetUrl,
  type ABResult,
  type AudioAsset,
  type Job,
  type RenderTake,
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
  sectionId,
  singers,
}: {
  songId: string;
  sectionId: string;
  singers: Singer[];
}) {
  const [takes, setTakes] = useState<AudioAsset[]>([]);
  const [renders, setRenders] = useState<Job[]>([]);
  const [takeRows, setTakeRows] = useState<RenderTake[]>([]);
  const [roles, setRoles] = useState<VocalRole[]>([]);
  const [guide, setGuide] = useState<AudioAsset | null>(null);
  const [presets, setPresets] = useState<VocalPreset[]>([]);
  const [ab, setAb] = useState<ABResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const singersInSection = Array.from(
    new Set(roles.flatMap((r) => r.assignments.map((a) => a.singer_id))),
  )
    .map((id) => singers.find((s) => s.id === id))
    .filter((s): s is Singer => !!s);

  const load = useCallback(async () => {
    const [t, r, rl, sa, pr] = await Promise.all([
      api.listSourceTakes(songId, sectionId),
      api.listSectionRenders(songId, sectionId),
      api.sectionRoles(sectionId),
      api.listAssets(songId),
      api.listPresets(),
    ]);
    setTakes(t);
    setRenders(r);
    setRoles(rl);
    setPresets(pr);
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

  return (
    <div className="section-render">
      {err && <p className="danger">{err}</p>}

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
      </div>

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
