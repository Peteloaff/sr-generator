"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  PLAYER_ROLE_LABEL,
  type AudioAsset,
  type Player,
  type StyleModel,
} from "@/lib/api";
import MicRecorder from "@/components/MicRecorder";

const SLIDERS = [
  { key: "drive", label: "drive / distortion", min: 0, max: 1, step: 0.02, def: 0.2 },
  { key: "brightness", label: "brightness", min: -1, max: 1, step: 0.05, def: 0 },
  { key: "busyness", label: "how busy", min: 0, max: 1, step: 0.02, def: 0.4 },
  { key: "attack", label: "attack (pick vs finger)", min: 0, max: 1, step: 0.02, def: 0.5 },
  { key: "sustain", label: "note length", min: 0, max: 1, step: 0.02, def: 0.5 },
  { key: "swing", label: "swing", min: 0, max: 1, step: 0.02, def: 0 },
] as const;

const STATUS_LABEL: Record<string, string> = {
  none: "no style yet",
  ready: "style ready",
  training: "learning…",
  failed: "training failed",
  disabled: "disabled",
};

export default function PlayerCard({
  player,
  onChange,
}: {
  player: Player;
  onChange: () => void;
}) {
  const [model, setModel] = useState<StyleModel | null>(null);
  const [samples, setSamples] = useState<AudioAsset[]>([]);
  const [busy, setBusy] = useState(false);
  const [tuning, setTuning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [m, s] = await Promise.all([
      api.getStyleModel(player.id),
      api.listPlayerSamples(player.id),
    ]);
    setModel(m);
    setSamples(s);
  }, [player.id]);

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
      if (!player.consent_training) {
        await api.updatePlayer(player.id, {
          consent_training: true,
          consent_generation: true,
        });
      }
      await api.uploadPlayerSample(player.id, file);
    });

  const train = () =>
    wrap(async () => void (await api.waitJob((await api.trainStyleModel(player.id)).id)));

  const status = model?.training_status ?? player.training_status;
  const ready = status === "ready";
  const profile = (model?.style_profile ?? {}) as Record<string, number>;

  return (
    <div className="card" style={{ padding: "0.9rem 1rem" }}>
      <div className="row space tight">
        <strong>
          {player.name}{" "}
          <span className="faint">· {PLAYER_ROLE_LABEL[player.role]}</span>
        </strong>
        <span className={`pill ${ready ? "ok" : status === "failed" ? "bad" : ""}`}>
          {STATUS_LABEL[status] ?? status}
        </span>
      </div>

      <div className="row tight" style={{ fontSize: "0.85rem" }}>
        <label>
          <input
            type="checkbox"
            checked={player.consent_generation}
            onChange={(e) =>
              wrap(async () =>
                void (await api.updatePlayer(player.id, { consent_generation: e.target.checked })),
              )
            }
          />
          generation OK
        </label>
        <label>
          <input
            type="checkbox"
            checked={player.consent_training}
            onChange={(e) =>
              wrap(async () =>
                void (await api.updatePlayer(player.id, { consent_training: e.target.checked })),
              )
            }
          />
          training OK
        </label>
        <span className="faint">
          {samples.length} song{samples.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="row tight">
        <label className="btn sm ghost" style={{ cursor: "pointer" }}>
          upload a song
          <input
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && addSample(e.target.files[0])}
          />
        </label>
        <MicRecorder
          onRecorded={addSample}
          label={`Record ${player.name}`}
          hint="Play a part on its own — a riff, a groove. A full-band track works too; it gets separated."
        />
        <button
          className="sm primary"
          disabled={busy || samples.length === 0}
          onClick={train}
          title={samples.length === 0 ? "upload a song this player performed on first" : ""}
        >
          {busy ? "…" : ready ? "Relearn style" : "Learn style"}
        </button>
      </div>

      {samples.length > 0 && (
        <div className="row tight" style={{ gap: "0.4rem" }}>
          {samples.map((a, i) => (
            <span key={a.id} className="pill">
              song {i + 1} · {a.duration ? `${a.duration.toFixed(0)}s` : "?"}
              <button
                className="danger sm"
                style={{ padding: "0 0.3rem", border: "none" }}
                onClick={() =>
                  wrap(async () => void (await api.deletePlayerSample(player.id, a.id)))
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
                  <td style={{ width: 150 }} className="muted">
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
                        api
                          .setStyleProfile(player.id, { [key]: Number(e.target.value) })
                          .then((m) => {
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
