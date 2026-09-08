"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  PLAYER_ROLES,
  PLAYER_ROLE_LABEL,
  type InstrumentSlot,
  type Player,
  type PlayerRole,
} from "@/lib/api";

const DIALS: { key: string; label: string }[] = [
  { key: "busier", label: "sparser ↔ busier" },
  { key: "brighter", label: "darker ↔ brighter" },
  { key: "harder", label: "softer ↔ harder" },
  { key: "push", label: "laid-back ↔ pushed" },
  { key: "swing", label: "straight ↔ swung" },
];

export default function InstrumentCast({
  songId,
  onChange,
}: {
  songId: string;
  onChange?: () => void;
}) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [slots, setSlots] = useState<InstrumentSlot[]>([]);
  const [open, setOpen] = useState<PlayerRole | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([
        api.listPlayers(),
        api.listInstruments(songId),
      ]);
      setPlayers(p);
      setSlots(s);
    } catch (e) {
      setErr(String(e));
    }
  }, [songId]);

  useEffect(() => {
    load();
  }, [load]);

  // the whole-song slot for a role (section_id === null)
  const songSlot = (role: PlayerRole) =>
    slots.find((s) => s.role === role && s.section_id === null) ?? null;

  const save = async (role: PlayerRole, patch: Partial<InstrumentSlot> & { dials?: Record<string, number> }) => {
    const cur = songSlot(role);
    try {
      await api.setInstrument(songId, {
        role,
        player_id: patch.player_id !== undefined ? patch.player_id : cur?.player_id ?? null,
        muted: patch.muted !== undefined ? patch.muted : cur?.muted ?? false,
        explore: patch.explore !== undefined ? patch.explore : cur?.explore ?? 0,
        dials: patch.dials ?? cur?.dials_json ?? undefined,
      });
      await load();
      onChange?.();
    } catch (e) {
      setErr(String(e));
    }
  };

  const castTheBand = async () => {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const r = await api.castBand(songId, true);
      const filled = Object.entries(r.players)
        .map(([role, name]) => `${role.replace(/_/g, " ")}: ${name}`)
        .join(" · ");
      setNote(filled ? `Cast ${filled}` : "No trained players to cast yet — add some on the Band page.");
      await load();
      onChange?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="row space tight">
        <h3 style={{ margin: 0 }}>Instruments</h3>
        <div className="row tight">
          <button className="sm primary" onClick={castTheBand} disabled={busy}>
            {busy ? "…" : "Cast the whole band"}
          </button>
          <Link href="/band" className="btn sm ghost">
            manage band
          </Link>
        </div>
      </div>
      <p className="muted">
        Who plays each part. Each player performs in their own learned style —
        nudge it with the dials, or turn up “explore” to let them try new things.
      </p>
      {note && <p className="muted">{note}</p>}
      {err && <p className="danger">{err}</p>}

      <div className="stack">
        {PLAYER_ROLES.map((role) => {
          const slot = songSlot(role);
          const pool = players.filter((p) => p.role === role);
          const chosen = players.find((p) => p.id === slot?.player_id);
          const dials = (slot?.dials_json ?? {}) as Record<string, number>;
          return (
            <div key={role} className="role-card" style={{ background: "var(--surface-2)" }}>
              <div className="row space tight">
                <strong>{PLAYER_ROLE_LABEL[role]}</strong>
                <div className="row tight">
                  <select
                    value={slot?.player_id ?? ""}
                    onChange={(e) => save(role, { player_id: e.target.value || null })}
                  >
                    <option value="">
                      {pool.length ? "— synth default —" : "— no player added —"}
                    </option>
                    {pool.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                        {p.consent_generation ? "" : " (needs consent)"}
                      </option>
                    ))}
                  </select>
                  <label className="faint" style={{ fontSize: "0.8rem" }}>
                    <input
                      type="checkbox"
                      checked={slot?.muted ?? false}
                      onChange={(e) => save(role, { muted: e.target.checked })}
                    />
                    mute
                  </label>
                  <button
                    className="sm ghost"
                    onClick={() => setOpen(open === role ? null : role)}
                  >
                    {open === role ? "close" : "tweak"}
                  </button>
                </div>
              </div>

              {chosen && !chosen.consent_generation && (
                <p className="danger" style={{ fontSize: "0.8rem", margin: "0.3rem 0 0" }}>
                  {chosen.name} hasn&apos;t authorized generation — set consent on the Players page.
                </p>
              )}

              {open === role && (
                <div className="stack" style={{ gap: "0.5rem", marginTop: "0.6rem" }}>
                  <label>
                    <span className="faint" style={{ fontSize: "0.8rem" }}>
                      explore — {Math.round((slot?.explore ?? 0) * 100)}%
                      {" "}(0 = faithful to their style, 100 = wander)
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={slot?.explore ?? 0}
                      style={{ width: "100%" }}
                      onChange={(e) => save(role, { explore: Number(e.target.value) })}
                    />
                  </label>
                  {DIALS.map((d) => (
                    <label key={d.key}>
                      <span className="faint" style={{ fontSize: "0.8rem" }}>
                        {d.label}
                      </span>
                      <input
                        type="range"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={dials[d.key] ?? 0}
                        style={{ width: "100%" }}
                        onChange={(e) =>
                          save(role, {
                            dials: { ...dials, [d.key]: Number(e.target.value) },
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="faint" style={{ fontSize: "0.78rem", marginTop: "0.6rem" }}>
        These are the whole-song defaults. After generating, open a section in
        Studio to override a player just for that section, then regenerate it.
      </p>
    </div>
  );
}
