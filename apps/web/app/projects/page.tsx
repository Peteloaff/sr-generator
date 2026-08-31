"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () => api.listProjects().then(setProjects).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
  }, []);

  const add = async () => {
    if (!name.trim()) return;
    await api.createProject(name.trim());
    setName("");
    refresh();
  };

  const doExport = async (p: Project) => {
    const data = await api.exportProject(p.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${p.name.replace(/\W+/g, "_")}.srproject.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const doImport = async (file: File) => {
    setErr(null);
    try {
      const data = JSON.parse(await file.text());
      await api.importProject(data);
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div>
      <h1>Projects</h1>
      <p className="muted">
        A project bundles songs, sections, lyric lines, and every vocal role/weight.
        Export is a portable snapshot — import it into this band or another one.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <input
          placeholder="New project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button onClick={add}>Add project</button>
        <button onClick={() => fileRef.current?.click()}>Import .srproject.json</button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => e.target.files?.[0] && doImport(e.target.files[0])}
        />
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr key={p.id}>
              <td>{p.name}</td>
              <td className="muted">{p.description ?? "—"}</td>
              <td>
                <button onClick={() => doExport(p)}>export</button>
              </td>
            </tr>
          ))}
          {projects.length === 0 && (
            <tr>
              <td colSpan={3} className="muted">
                no projects yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
