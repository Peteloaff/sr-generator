"use client";

import { useEffect, useState } from "react";
import { api, type Singer } from "@/lib/api";

export default function SingersPage() {
  const [singers, setSingers] = useState<Singer[]>([]);
  const [name, setName] = useState("");
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

  return (
    <div>
      <h1>Singers</h1>
      <p className="muted">
        Each singer is an independently modeled voice identity with its own consent
        flags. Add as many as you need.
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
            <th>Clean</th>
            <th>Scream</th>
            <th>Consent (train / gen / comm)</th>
            <th>Training</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {singers.map((s) => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td>{s.clean_enabled ? "yes" : "no"}</td>
              <td>{s.scream_enabled ? "yes" : "no"}</td>
              <td>
                <label>
                  <input
                    type="checkbox"
                    checked={s.consent_training}
                    onChange={(e) =>
                      api.updateSinger(s.id, { consent_training: e.target.checked }).then(refresh)
                    }
                  />{" "}
                  train
                </label>{" "}
                <label>
                  <input
                    type="checkbox"
                    checked={s.consent_generation}
                    onChange={(e) =>
                      api.updateSinger(s.id, { consent_generation: e.target.checked }).then(refresh)
                    }
                  />{" "}
                  gen
                </label>{" "}
                <label>
                  <input
                    type="checkbox"
                    checked={s.consent_commercial}
                    onChange={(e) =>
                      api.updateSinger(s.id, { consent_commercial: e.target.checked }).then(refresh)
                    }
                  />{" "}
                  comm
                </label>
              </td>
              <td>
                <span className="pill">{s.training_status}</span>
              </td>
              <td>
                <button
                  className="danger"
                  onClick={() => api.deleteSinger(s.id).then(refresh)}
                >
                  delete
                </button>
              </td>
            </tr>
          ))}
          {singers.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">
                no singers yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
