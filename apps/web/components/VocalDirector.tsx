"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  ROLE_TYPES,
  type NormalizedShare,
  type Singer,
  type VocalRole,
} from "@/lib/api";

const ENSEMBLE_ROLES = new Set(["background", "gang", "harmony"]);

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

  const refreshShares = useCallback(
    () => api.normalized(role.id).then(setShares),
    [role.id],
  );
  useEffect(() => {
    refreshShares();
  }, [refreshShares, role.assignments.length]);

  const unassigned = singers.filter(
    (s) => !role.assignments.some((a) => a.singer_id === s.id),
  );

  return (
    <div className="role-card">
      <div className="row space">
        <strong>{role.role_type}</strong>
        {ENSEMBLE_ROLES.has(role.role_type) && (
          <span className="muted">ensemble {role.ensemble_size}</span>
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
                    style={{ width: 64 }}
                    onChange={(e) =>
                      api
                        .updateAssignment(a.id, { weight_percent: Number(e.target.value) })
                        .then(onChanged)
                    }
                  />{" "}
                  %
                </td>
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
    const body = {
      role_type: roleType,
      ensemble_size: ENSEMBLE_ROLES.has(roleType) ? 10 : 1,
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
