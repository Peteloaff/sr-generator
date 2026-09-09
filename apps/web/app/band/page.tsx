"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  PLAYER_ROLES,
  PLAYER_ROLE_LABEL,
  type BandLineup,
  type Player,
  type PlayerRole,
  type Singer,
} from "@/lib/api";
import SingerCard from "@/components/SingerCard";
import PlayerCard from "@/components/PlayerCard";
import SignaturePlayers from "@/components/SignaturePlayers";
import BandIdentity from "@/components/BandIdentity";

export default function BandPage() {
  const [lineup, setLineup] = useState<BandLineup | null>(null);
  const [singers, setSingers] = useState<Singer[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [sName, setSName] = useState("");
  const [pName, setPName] = useState("");
  const [pRole, setPRole] = useState<PlayerRole>("lead_guitar");
  const [fromSongName, setFromSongName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [bands, s, p] = await Promise.all([
        api.listBands(),
        api.listSingers(),
        api.listPlayers(),
      ]);
      setSingers(s);
      setPlayers(p);
      const bid = bands[0]?.id;
      if (bid) setLineup(await api.bandLineup(bid));
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addSinger = async () => {
    if (!sName.trim()) return;
    await api.createSinger(sName.trim());
    setSName("");
    refresh();
  };
  const addPlayer = async () => {
    if (!pName.trim()) return;
    await api.createPlayer(pName.trim(), pRole);
    setPName("");
    refresh();
  };
  const singerFromSong = async (file: File) => {
    if (!fromSongName.trim()) {
      setErr("give the new vocalist a name first");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const job = await api.createSingerFromSong(fromSongName.trim(), file);
      await api.waitJob(job.id);
      setFromSongName("");
      refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Your Band</h1>
      <p className="muted">
        Everyone in your band — singers and players. Train each one, then when you
        make a song you can cast the whole band in one click, or pick members
        part by part. New to this? <Link href="/help">See the walkthrough →</Link>
      </p>
      {err && <p className="danger">{err}</p>}

      <BandIdentity onSwitch={refresh} />

      {lineup && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>Lineup</h3>
          <table>
            <tbody>
              <tr>
                <td className="muted" style={{ width: 130 }}>Vocals</td>
                <td>
                  {lineup.singers.length
                    ? lineup.singers.map((s) => s.name).join(", ")
                    : <span className="faint">— none yet —</span>}
                </td>
              </tr>
              {PLAYER_ROLES.map((r) => {
                const ps = lineup.players[r] ?? [];
                return (
                  <tr key={r}>
                    <td className="muted">{PLAYER_ROLE_LABEL[r]}</td>
                    <td>
                      {ps.length ? (
                        ps.map((p) => (
                          <span key={p.id} className={`pill ${p.consent_generation ? "ok" : ""}`}>
                            {p.name}
                            {p.training_status === "ready" ? " ✓" : ""}
                          </span>
                        ))
                      ) : (
                        <span className="faint">— none yet —</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <h2>Vocalists</h2>
      <div className="row">
        <input
          placeholder="New vocalist name"
          value={sName}
          onChange={(e) => setSName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addSinger()}
        />
        <button onClick={addSinger}>Add vocalist</button>
        {!singers.some((s) => s.name === "Me") && (
          <button className="primary" onClick={() => setSName("Me")}>
            🎤 name it “Me”
          </button>
        )}
      </div>
      <div className="row tight" style={{ marginTop: "0.3rem" }}>
        <span className="faint">…or from a song:</span>
        <input
          placeholder="Vocalist name"
          value={fromSongName}
          onChange={(e) => setFromSongName(e.target.value)}
          style={{ maxWidth: 180 }}
        />
        <label className="btn sm ghost" style={{ cursor: "pointer" }}>
          {busy ? "separating…" : "upload a song"}
          <input
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
            style={{ display: "none" }}
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && singerFromSong(e.target.files[0])}
          />
        </label>
        <span className="faint" style={{ fontSize: "0.78rem" }}>
          strips the vocal and trains a new singer
        </span>
      </div>
      {singers.length === 0 ? (
        <div className="empty">No vocalists yet.</div>
      ) : (
        <div className="grid">
          {singers.map((s) => (
            <div key={s.id} className="stack" style={{ gap: "0.4rem" }}>
              <SingerCard singer={s} onChange={refresh} isMe={s.name === "Me"} />
              <button
                className="danger sm"
                style={{ alignSelf: "flex-end" }}
                onClick={() => api.deleteSinger(s.id).then(refresh)}
              >
                remove
              </button>
            </div>
          ))}
        </div>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>Players</h2>
      <SignaturePlayers onChange={refresh} />
      <div className="row" style={{ marginTop: "0.6rem" }}>
        <input
          placeholder="New player name"
          value={pName}
          onChange={(e) => setPName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addPlayer()}
        />
        <select value={pRole} onChange={(e) => setPRole(e.target.value as PlayerRole)}>
          {PLAYER_ROLES.map((r) => (
            <option key={r} value={r}>{PLAYER_ROLE_LABEL[r]}</option>
          ))}
        </select>
        <button onClick={addPlayer}>Add player</button>
        <Link href="/players" className="btn ghost">full players page →</Link>
      </div>
      {players.length === 0 ? (
        <div className="empty">No players yet — add your rhythm section and guitars.</div>
      ) : (
        <div className="grid">
          {players.map((p) => (
            <div key={p.id} className="stack" style={{ gap: "0.4rem" }}>
              <PlayerCard player={p} onChange={refresh} />
              <button
                className="danger sm"
                style={{ alignSelf: "flex-end" }}
                onClick={() => api.deletePlayer(p.id).then(refresh)}
              >
                remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
