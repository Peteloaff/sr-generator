"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  ROLE_TYPES,
  type FxStep,
  type NormalizedShare,
  type Singer,
  type VocalRole,
} from "@/lib/api";

const ENSEMBLE_ROLES = new Set(["background", "gang", "harmony"]);
const INTERVAL_ROLES = new Set(["harmony", "double"]);

const FX_DEFAULTS: Record<string, FxStep> = {
  deesser: { type: "deesser", amount: 0.5 },
  eq: { type: "eq", low_shelf_db: 0, high_shelf_db: 2, presence_db: 2 },
  compressor: { type: "compressor", ratio: 3, threshold_db: -18 },
};

function FxChain({ role, onChanged }: { role: VocalRole; onChanged: () => void }) {
  const chain = role.processing_json ?? [];
  const save = (next: FxStep[]) =>
    api.updateRole(role.id, { processing: next.length ? next : null }).then(onChanged);

  return (
    <div className="fx-chain">
      <span className="muted">processing:</span>{" "}
      {chain.map((step, i) => (
        <span key={i} className="pill">
          {step.type}
          {Object.entries(step)
            .filter(([k]) => k !== "type")
            .map(([k, v]) => (
              <input
                key={k}
                type="number"
                step={0.1}
                value={v as number}
                title={k}
                style={{ width: 52, marginLeft: 4 }}
                onChange={(e) => {
                  const next = chain.map((s, j) =>
                    j === i ? { ...s, [k]: Number(e.target.value) } : s,
                  );
                  save(next);
                }}
              />
            ))}
          <button className="danger" onClick={() => save(chain.filter((_, j) => j !== i))}>
            ×
          </button>
        </span>
      ))}
      <select
        value=""
        onChange={(e) => e.target.value && save([...chain, FX_DEFAULTS[e.target.value]])}
      >
        <option value="">+ fx…</option>
        {Object.keys(FX_DEFAULTS)
          .filter((t) => !chain.some((s) => s.type === t))
          .map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
      </select>
    </div>
  );
}

function RoleCard({
  role,
  singers,
  onChanged,
}: {
  role: VocalRole;
  singers: Singer[];
  onChanged: () => void;
}) {
  const [shares, setShares] = useState<NormalizedShare[]>([]);
  const name = (id: string) => singers.find((s) => s.id === id)?.name ?? "?";
  const showInterval = INTERVAL_ROLES.has(role.role_type);

  const refreshShares = useCallback(() => api.normalized(role.id).then(setShares), [role.id]);
  useEffect(() => {
    refreshShares();
  }, [refreshShares, role.assignments.length]);

  const unassigned = singers.filter((s) => !role.assignments.some((a) => a.singer_id === s.id));

  return (
    <div className="role-card">
      <div className="row space">
        <strong>{role.role_type}</strong>
        {ENSEMBLE_ROLES.has(role.role_type) && (
          <label className="muted">
            ensemble{" "}
            <input
              type="number"
              min={1}
              max={64}
              value={role.ensemble_size}
              style={{ width: 52 }}
              onChange={(e) =>
                api.updateRole(role.id, { ensemble_size: Number(e.target.value) }).then(onChanged)
              }
            />{" "}
            width{" "}
            <input
              type="number"
              min={0}
              max={100}
              value={role.width}
              style={{ width: 52 }}
              onChange={(e) =>
                api.updateRole(role.id, { width: Number(e.target.value) }).then(onChanged)
              }
            />
          </label>
        )}
        <button className="danger" onClick={() => api.deleteRole(role.id).then(onChanged)}>
          remove role
        </button>
      </div>
      <table>
        <tbody>
          {role.assignments.map((a) => {
            const share = shares.find((x) => x.singer_id === a.singer_id);
            return (
              <tr key={a.id}>
                <td>{name(a.singer_id)}</td>
                <td>
                  <input
                    type="number"
                    min={0}
                    value={a.weight_percent}
                    style={{ width: 60 }}
                    onChange={(e) =>
                      api
                        .updateAssignment(a.id, { weight_percent: Number(e.target.value) })
                        .then(onChanged)
                    }
                  />{" "}
                  %
                </td>
                {showInterval && (
                  <td>
                    <input
                      type="number"
                      step={1}
                      value={a.interval_semitones}
                      title="interval (semitones)"
                      style={{ width: 56 }}
                      onChange={(e) =>
                        api
                          .updateAssignment(a.id, {
                            interval_semitones: Number(e.target.value),
                          })
                          .then(onChanged)
                      }
                    />{" "}
                    st
                  </td>
                )}
                <td className="muted">
                  = {share ? share.normalized_percent.toFixed(1) : "…"}%
                  {ENSEMBLE_ROLES.has(role.role_type) && share
                    ? ` → ${share.ensemble_takes} take${share.ensemble_takes === 1 ? "" : "s"}`
                    : ""}
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() => api.deleteAssignment(a.id).then(onChanged)}
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {unassigned.length > 0 && (
        <select
          value=""
          onChange={(e) =>
            e.target.value && api.addAssignment(role.id, e.target.value, 100).then(onChanged)
          }
        >
          <option value="">+ add singer…</option>
          {unassigned.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      )}
      <FxChain role={role} onChanged={onChanged} />
    </div>
  );
}

export default function VocalDirector({
  scope,
  id,
  singers,
}: {
  scope: "section" | "line";
  id: string;
  singers: Singer[];
}) {
  const [roles, setRoles] = useState<VocalRole[]>([]);
  const [roleType, setRoleType] = useState<string>("lead");

  const load = useCallback(() => {
    (scope === "section" ? api.sectionRoles(id) : api.lineRoles(id)).then(setRoles);
  }, [scope, id]);
  useEffect(() => {
    load();
  }, [load]);

  const addRole = async () => {
    const body: Record<string, unknown> = {
      role_type: roleType,
      ensemble_size: ENSEMBLE_ROLES.has(roleType) ? 8 : 1,
      width: ENSEMBLE_ROLES.has(roleType) ? 70 : 0,
      humanize_timing_ms: ENSEMBLE_ROLES.has(roleType) ? 16 : 0,
      humanize_pitch_cents: ENSEMBLE_ROLES.has(roleType) ? 6 : 0,
    };
    if (scope === "section") await api.createSectionRole(id, body);
    else await api.createLineRole(id, body);
    load();
  };

  return (
    <div className="vocal-director">
      {roles.length === 0 && <p className="muted">no vocal roles yet</p>}
      {roles.map((r) => (
        <RoleCard key={r.id} role={r} singers={singers} onChanged={load} />
      ))}
      <div className="row">
        <select value={roleType} onChange={(e) => setRoleType(e.target.value)}>
          {ROLE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button onClick={addRole}>add role</button>
      </div>
    </div>
  );
}
