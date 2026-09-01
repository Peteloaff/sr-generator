"use client";

import { useEffect, useState } from "react";
import { api, type Singer } from "@/lib/api";
import SingerCard from "@/components/SingerCard";

export default function SingersPage() {
  const [singers, setSingers] = useState<Singer[]>([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => api.listSingers().then(setSingers).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
  }, []);

  const add = async (n: string) => {
    if (!n.trim()) return;
    try {
      await api.createSinger(n.trim());
      setName("");
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div>
      <h1>Singers</h1>
      <p className="muted">
        Each singer is an independently modeled voice — record or upload a few
        takes, train, and they're ready to sing lead, harmony, or gang vocals on
        any song. Nothing generates until you grant consent below.
      </p>
      {err && <p className="danger">{err}</p>}

      <div className="row">
        <input
          placeholder="New singer name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add(name)}
        />
        <button onClick={() => add(name)}>Add singer</button>
        {!singers.some((s) => s.name === "Me") && (
          <button className="primary" onClick={() => add("Me")}>
            🎤 Add your voice
          </button>
        )}
      </div>

      {singers.length === 0 ? (
        <div className="empty">No singers yet — add one above.</div>
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
                delete singer
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
