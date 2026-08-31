"use client";

import { useEffect, useState } from "react";
import { api, getBandId, setBandId, type Band } from "@/lib/api";

export default function BandSwitcher() {
  const [bands, setBands] = useState<Band[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");

  const load = () =>
    api.listBands().then((bs) => {
      setBands(bs);
      const stored = getBandId();
      const active = stored && bs.some((b) => b.id === stored) ? stored : bs[0]?.id ?? null;
      setCurrent(active);
      setBandId(active);
    });

  useEffect(() => {
    load();
  }, []);

  const pick = (id: string) => {
    setBandId(id);
    setCurrent(id);
    window.location.reload();
  };

  const add = async () => {
    if (!name.trim()) return;
    const b = await api.createBand(name.trim());
    setName("");
    setAdding(false);
    await load();
    pick(b.id);
  };

  return (
    <span className="band-switcher">
      <select value={current ?? ""} onChange={(e) => pick(e.target.value)}>
        {bands.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      {adding ? (
        <>
          <input
            autoFocus
            placeholder="Band name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <button onClick={add}>save</button>
        </>
      ) : (
        <button onClick={() => setAdding(true)} title="Add another band">
          + band
        </button>
      )}
    </span>
  );
}
