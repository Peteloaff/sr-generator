"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  PLAYER_ROLES,
  PLAYER_ROLE_LABEL,
  type Player,
  type PlayerRole,
} from "@/lib/api";
import PlayerCard from "@/components/PlayerCard";

export default function PlayersPage() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState<PlayerRole>("lead_guitar");
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => api.listPlayers().then(setPlayers).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
  }, []);

  const add = async () => {
    if (!name.trim()) return;
    try {
      await api.createPlayer(name.trim(), role);
      setName("");
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  const byRole = useMemo(() => {
    const m = new Map<PlayerRole, Player[]>();
    for (const r of PLAYER_ROLES) m.set(r, []);
    for (const p of players) m.get(p.role)?.push(p);
    return m;
  }, [players]);

  return (
    <div>
      <h1>Players</h1>
      <p className="muted">
        Your instrumentalists. Upload songs a player performed on — their part is
        separated out and their style is learned (drive, tone, timing feel, how
        busy, how dynamic). Then cast them on any song. Nothing generates until
        you grant consent.
      </p>
      {err && <p className="danger">{err}</p>}

      <div className="row">
        <input
          placeholder="New player name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <select value={role} onChange={(e) => setRole(e.target.value as PlayerRole)}>
          {PLAYER_ROLES.map((r) => (
            <option key={r} value={r}>
              {PLAYER_ROLE_LABEL[r]}
            </option>
          ))}
        </select>
        <button onClick={add}>Add player</button>
      </div>

      {players.length === 0 ? (
        <div className="empty">No players yet — add your drummer, bassist, guitarists…</div>
      ) : (
        <div className="stack">
          {PLAYER_ROLES.filter((r) => (byRole.get(r) ?? []).length > 0).map((r) => (
            <section key={r}>
              <h3 style={{ margin: "0.6rem 0 0.4rem" }}>{PLAYER_ROLE_LABEL[r]}</h3>
              <div className="grid">
                {(byRole.get(r) ?? []).map((p) => (
                  <div key={p.id} className="stack" style={{ gap: "0.4rem" }}>
                    <PlayerCard player={p} onChange={refresh} />
                    <button
                      className="danger sm"
                      style={{ alignSelf: "flex-end" }}
                      onClick={() => api.deletePlayer(p.id).then(refresh)}
                    >
                      delete player
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
