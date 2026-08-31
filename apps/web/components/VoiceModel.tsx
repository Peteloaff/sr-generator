"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AudioAsset, type Singer, type VoiceModel } from "@/lib/api";

const SLIDERS: { key: keyof NonNullable<VoiceModel["voice_profile"]>; label: string; min: number; max: number; step: number }[] = [
  { key: "median_f0", label: "pitch (Hz)", min: 70, max: 400, step: 1 },
  { key: "formant_semitones", label: "formant", min: -12, max: 12, step: 0.5 },
  { key: "brightness", label: "brightness", min: -1, max: 1, step: 0.05 },
  { key: "breathiness", label: "breathiness", min: 0, max: 1, step: 0.05 },
  { key: "roughness", label: "roughness", min: 0, max: 1, step: 0.05 },
];

export default function VoiceModelPanel({ singer }: { singer: Singer }) {
  const [model, setModel] = useState<VoiceModel | null>(null);
  const [samples, setSamples] = useState<AudioAsset[]>([]);
  const [busy, setBusy] = useState(false);
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

  const addSample = async (file: File) => {
    setErr(null);
    try {
      await api.uploadVoiceSample(singer.id, file);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const train = async () => {
    setBusy(true);
    setErr(null);
    try {
      const job = await api.trainVoiceModel(singer.id);
      await api.waitJob(job.id);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const profile = model?.voice_profile ?? {};

  return (
    <div className="voice-model">
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <span>
          <strong>Voice model</strong>{" "}
          <span className="pill">{model?.training_status ?? "…"}</span>{" "}
          <span className="muted">
            {model?.voice_model_provider ?? "none"} · {samples.length} sample
            {samples.length === 1 ? "" : "s"}
          </span>
        </span>
      </div>

      <div className="row">
        <input
          type="file"
          accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
          onChange={(e) => e.target.files?.[0] && addSample(e.target.files[0])}
        />
        <button onClick={train} disabled={busy || !singer.consent_training || samples.length === 0}>
          {busy ? "training…" : "Train from samples"}
        </button>
        {!singer.consent_training && (
          <span className="muted">grant the “train” consent to enable training</span>
        )}
      </div>
      {samples.length > 0 && (
        <div className="muted" style={{ fontSize: "0.85rem" }}>
          {samples.map((a) => (
            <span key={a.id} style={{ marginRight: "0.75rem" }}>
              {a.label}{" "}
              <button className="danger" onClick={() => api.deleteVoiceSample(singer.id, a.id).then(load)}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <p className="muted" style={{ marginTop: "0.75rem" }}>
        Profile (edit to tune by hand — the guide vocal is converted toward these values):
      </p>
      <table>
        <tbody>
          {SLIDERS.map(({ key, label, min, max, step }) => {
            const val = Number(profile[key] ?? (key === "median_f0" ? 180 : 0));
            return (
              <tr key={key}>
                <td style={{ width: 110 }}>{label}</td>
                <td style={{ width: "100%" }}>
                  <input
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={val}
                    style={{ width: "100%" }}
                    onChange={(e) =>
                      api.setVoiceProfile(singer.id, { [key]: Number(e.target.value) }).then(setModel)
                    }
                  />
                </td>
                <td style={{ width: 56 }}>{val}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
