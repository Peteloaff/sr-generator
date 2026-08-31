"use client";

import { Fragment, useEffect, useState } from "react";
import { api, type Singer } from "@/lib/api";
import VoiceModelPanel from "@/components/VoiceModel";

export default function SingersPage() {
  const [singers, setSingers] = useState<Singer[]>([]);
  const [name, setName] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => api.listSingers().then(setSingers).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
  }, []);

  const add = async () => {
    if (!name.trim()) return;
    try {
      await api.createSinger(name.trim());
      setName("");
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  const consentBox = (s: Singer, field: "consent_training" | "consent_generation" | "consent_commercial", lbl: string) => (
    <label>
      <input
        type="checkbox"
        checked={s[field]}
        onChange={(e) => api.updateSinger(s.id, { [field]: e.target.checked }).then(refresh)}
      />{" "}
      {lbl}
    </label>
  );

  return (
    <div>
      <h1>Singers</h1>
      <p className="muted">
        Each singer is an independently modeled voice identity. Training and voice
        generation are blocked until the matching consent flag is set.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <input
          placeholder="New singer name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button onClick={add}>Add singer</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Consent (train / gen / comm)</th>
            <th>Voice model</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {singers.map((s) => (
            <Fragment key={s.id}>
              <tr>
                <td>{s.name}</td>
                <td>
                  {consentBox(s, "consent_training", "train")}{" "}
                  {consentBox(s, "consent_generation", "gen")}{" "}
                  {consentBox(s, "consent_commercial", "comm")}
                </td>
                <td>
                  <button onClick={() => setOpen(open === s.id ? null : s.id)}>
                    {open === s.id ? "close" : `${s.training_status}`}
                  </button>
                </td>
                <td>
                  <button className="danger" onClick={() => api.deleteSinger(s.id).then(refresh)}>
                    delete
                  </button>
                </td>
              </tr>
              {open === s.id && (
                <tr>
                  <td colSpan={4}>
                    <VoiceModelPanel singer={s} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {singers.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                no singers yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
