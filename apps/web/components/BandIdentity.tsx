"use client";

import { useEffect, useState } from "react";
import { api, getBandId, setBandId, type Band } from "@/lib/api";

export default function BandIdentity({ onSwitch }: { onSwitch?: () => void }) {
  const [bands, setBands] = useState<Band[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    const bs = await api.listBands();
    setBands(bs);
    const stored = getBandId();
    const active = stored && bs.some((b) => b.id === stored) ? stored : bs[0]?.id ?? null;
    setActiveId(active);
    setBandId(active);
    setName(bs.find((b) => b.id === active)?.name ?? "");
  };

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, []);

  const active = bands.find((b) => b.id === activeId);

  const switchTo = (id: string) => {
    setBandId(id);
    window.location.reload();
  };

  const rename = async () => {
    if (!active || !name.trim() || name.trim() === active.name) return;
    await api.updateBand(active.id, { name: name.trim() });
    await load();
    onSwitch?.();
  };

  const create = async () => {
    if (!newName.trim()) return;
    const b = await api.createBand(newName.trim());
    setNewName("");
    setCreating(false);
    switchTo(b.id);
  };

  return (
    <div className="card" style={{ marginBottom: "1rem" }}>
      {err && <p className="danger">{err}</p>}
      <div className="row space tight" style={{ flexWrap: "wrap" }}>
        <div className="row tight" style={{ flexWrap: "wrap" }}>
          <span className="faint">Band:</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={rename}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            style={{ fontWeight: 700, minWidth: 160 }}
            aria-label="Band name"
          />
          {bands.length > 1 && (
            <select
              value={activeId ?? ""}
              onChange={(e) => switchTo(e.target.value)}
              aria-label="Switch band"
            >
              {bands.map((b) => (
                <option key={b.id} value={b.id}>
                  switch to: {b.name}
                </option>
              ))}
            </select>
          )}
        </div>
        {creating ? (
          <div className="row tight">
            <input
              autoFocus
              placeholder="New band name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
            />
            <button className="sm primary" onClick={create}>create</button>
            <button className="sm ghost" onClick={() => setCreating(false)}>cancel</button>
          </div>
        ) : (
          <button className="sm" onClick={() => setCreating(true)}>+ new band</button>
        )}
      </div>
      <p className="faint" style={{ fontSize: "0.78rem", margin: "0.5rem 0 0" }}>
        Each band keeps its own singers, players and songs. Everything saves as you
        go — switch any time from here or the picker up top.
      </p>
    </div>
  );
}
