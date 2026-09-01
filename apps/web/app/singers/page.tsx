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
                    <h4>Arranger metadata</h4>
                    <p className="muted">
                      User-entered, not measured. Feeds the Stage 10 auto arranger.
                    </p>
                    <div className="row">
                      <label>
                        preferred roles{" "}
                        <input
                          defaultValue={(s.preferred_roles ?? []).join(", ")}
                          placeholder="chorus_lead, scream, high_harmony"
                          style={{ width: 260 }}
                          onBlur={(e) =>
                            api
                              .updateSinger(s.id, {
                                preferred_roles: e.target.value
                                  .split(",")
                                  .map((x) => x.trim())
                                  .filter(Boolean),
                              })
                              .then(refresh)
                          }
                        />
                      </label>
                      <label>
                        energy fit{" "}
                        <select
                          defaultValue={s.energy_fit ?? ""}
                          onChange={(e) =>
                            api
                              .updateSinger(s.id, { energy_fit: e.target.value || null })
                              .then(refresh)
                          }
                        >
                          <option value="">—</option>
                          <option value="low">low</option>
                          <option value="mid">mid</option>
                          <option value="high">high</option>
                        </select>
                      </label>
                      {(["range_low_midi", "range_high_midi"] as const).map((f) => (
                        <label key={f}>
                          {f === "range_low_midi" ? "range low" : "range high"} (MIDI){" "}
                          <input
                            type="number"
                            defaultValue={s[f] ?? ""}
                            style={{ width: 60 }}
                            onBlur={(e) =>
                              api
                                .updateSinger(s.id, {
                                  [f]: e.target.value === "" ? null : Number(e.target.value),
                                })
                                .then(refresh)
                            }
                          />
                        </label>
                      ))}
                    </div>
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
