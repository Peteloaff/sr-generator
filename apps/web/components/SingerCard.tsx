"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AudioAsset, type Singer, type VoiceModel } from "@/lib/api";
import MicRecorder from "@/components/MicRecorder";

const SLIDERS = [
  { key: "median_f0", label: "pitch", min: 70, max: 400, step: 1, def: 180 },
  { key: "formant_semitones", label: "formant", min: -12, max: 12, step: 0.5, def: 0 },
  { key: "brightness", label: "brightness", min: -1, max: 1, step: 0.05, def: 0 },
  { key: "breathiness", label: "breath", min: 0, max: 1, step: 0.05, def: 0 },
  { key: "roughness", label: "rasp", min: 0, max: 1, step: 0.05, def: 0 },
] as const;

const STATUS_LABEL: Record<string, string> = {
  none: "no voice yet",
  ready: "voice ready",
  training: "training…",
  failed: "training failed",
  disabled: "disabled",
};

export default function SingerCard({
  singer,
  onChange,
  isMe = false,
}: {
  singer: Singer;
  onChange: () => void;
  isMe?: boolean;
}) {
  const [model, setModel] = useState<VoiceModel | null>(null);
  const [samples, setSamples] = useState<AudioAsset[]>([]);
  const [busy, setBusy] = useState(false);
  const [tuning, setTuning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [m, s] = await Promise.all([
      api.getVoiceModel(singer.id),
      api.listVoiceSamples(singer.id),
    ]);
    setModel(m);
    setSamples(s);
  }, [singer.id]);

  useEffect(() => {
    load();
  }, [load]);

  const wrap = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await load();
      onChange();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const addSample = (file: File) =>
    wrap(async () => {
      if (!singer.consent_training) {
        await api.updateSinger(singer.id, { consent_training: true, consent_generation: true });
      }
      await api.uploadVoiceSample(singer.id, file);
    });

  const train = () => wrap(async () => void (await api.waitJob((await api.trainVoiceModel(singer.id)).id)));

  const status = model?.training_status ?? singer.training_status;
  const ready = status === "ready";
  const profile = (model?.voice_profile ?? {}) as Record<string, number>;

  return (
    <div className="card" style={{ padding: "0.9rem 1rem" }}>
      <div className="row space tight">
        <strong>
          {isMe ? "🎤 " : ""}
          {singer.name}
        </strong>
        <span className={`pill ${ready ? "ok" : status === "failed" ? "bad" : ""}`}>
          {STATUS_LABEL[status] ?? status}
        </span>
      </div>

      <div className="row tight" style={{ fontSize: "0.85rem" }}>
        <label>
          <input
            type="checkbox"
            checked={singer.consent_generation}
            onChange={(e) =>
              wrap(async () => void (await api.updateSinger(singer.id, { consent_generation: e.target.checked })))
            }
          />
          generation OK
        </label>
        <label>
          <input
            type="checkbox"
            checked={singer.consent_training}
            onChange={(e) =>
              wrap(async () => void (await api.updateSinger(singer.id, { consent_training: e.target.checked })))
            }
          />
          training OK
        </label>
        <span className="faint">
          {samples.length} sample{samples.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="row tight">
        <MicRecorder
          onRecorded={addSample}
          label={isMe ? "Record my voice" : `Record ${singer.name}`}
          hint="10–30s of clear singing works best. Record a few takes, then train."
        />
        <label className="btn sm ghost" style={{ cursor: "pointer" }}>
          upload file
          <input
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg,.webm"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && addSample(e.target.files[0])}
          />
        </label>
        <button
          className="sm primary"
          disabled={busy || samples.length === 0}
          onClick={train}
          title={samples.length === 0 ? "record or upload a sample first" : ""}
        >
          {busy ? "…" : ready ? "Retrain" : "Train voice"}
        </button>
      </div>

      {samples.length > 0 && (
        <div className="row tight" style={{ gap: "0.4rem" }}>
          {samples.map((a, i) => (
            <span key={a.id} className="pill">
              take {i + 1} · {a.duration ? `${a.duration.toFixed(1)}s` : "?"}
              <button
                className="danger sm"
                style={{ padding: "0 0.3rem", border: "none" }}
                onClick={() =>
                  wrap(async () => void (await api.deleteVoiceSample(singer.id, a.id)))
                }
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="row tight">
        <button className="sm ghost" onClick={() => setTuning((t) => !t)}>
          {tuning ? "hide tuning" : "tune by hand"}
        </button>
      </div>
      {tuning && (
        <table>
          <tbody>
            {SLIDERS.map(({ key, label, min, max, step, def }) => {
              const val = Number(profile[key] ?? def);
              return (
                <tr key={key}>
                  <td style={{ width: 80 }} className="muted">
                    {label}
                  </td>
                  <td>
                    <input
                      type="range"
                      min={min}
                      max={max}
                      step={step}
                      value={val}
                      style={{ width: "100%" }}
                      onChange={(e) =>
                        api.setVoiceProfile(singer.id, { [key]: Number(e.target.value) }).then((m) => {
                          setModel(m);
                          onChange();
                        })
                      }
                    />
                  </td>
                  <td style={{ width: 44 }} className="faint">
                    {val}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {err && <p className="danger" style={{ fontSize: "0.85rem" }}>{err}</p>}
    </div>
  );
}
