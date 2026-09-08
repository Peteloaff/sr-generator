"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  PLAYER_ROLES,
  PLAYER_ROLE_LABEL,
  type PlayerPreset,
  type PlayerRole,
} from "@/lib/api";

export default function SignaturePlayers({ onChange }: { onChange: () => void }) {
  const [presets, setPresets] = useState<PlayerPreset[]>([]);
  const [role, setRole] = useState<PlayerRole>("lead_guitar");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listPlayerPresets().then(setPresets).catch((e) => setErr(String(e)));
  }, []);

  const forRole = useMemo(
    () => presets.filter((p) => p.role === role),
    [presets, role],
  );

  const add = async (p: PlayerPreset) => {
    setBusy(p.id);
    setErr(null);
    try {
      let name = p.label;
      for (let i = 2; i < 30; i++) {
        try {
          await api.createPlayerFromPreset(p.id, name);
          break;
        } catch (e) {
          if (String(e).includes("409")) name = `${p.label} ${i}`;
          else throw e;
        }
      }
      onChange();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="card">
      <div className="row space tight">
        <h3 style={{ margin: 0 }}>Signature players</h3>
        <select value={role} onChange={(e) => setRole(e.target.value as PlayerRole)}>
          {PLAYER_ROLES.map((r) => (
            <option key={r} value={r}>{PLAYER_ROLE_LABEL[r]}</option>
          ))}
        </select>
      </div>
      <p className="muted">
        Ready-made playing styles — acoustic through metal — for every instrument.
        Add one to your band and tweak it like any trained player. These are style
        archetypes, not anyone&apos;s recordings.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row tight" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
        {forRole.map((p) => (
          <button
            key={p.id}
            className="chip"
            disabled={busy === p.id}
            onClick={() => add(p)}
            title={`drive ${p.profile.drive} · bright ${p.profile.brightness} · busy ${p.profile.busyness}`}
          >
            {busy === p.id ? "…" : `+ ${p.label}`}
          </button>
        ))}
      </div>
    </div>
  );
}
