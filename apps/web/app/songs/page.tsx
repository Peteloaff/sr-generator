"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Song } from "@/lib/api";

export default function SongsPage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [title, setTitle] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => api.listSongs().then(setSongs).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
  }, []);

  const add = async () => {
    if (!title.trim()) return;
    try {
      await api.createSong(title.trim());
      setTitle("");
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div>
      <h1>Songs</h1>
      <p className="muted">
        Open a song to upload audio, mark sections, edit lyrics, and direct vocals.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <input
          placeholder="New song title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button onClick={add}>Add song</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Duration</th>
            <th>BPM</th>
            <th>Key</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {songs.map((s) => (
            <tr key={s.id}>
              <td>
                <Link href={`/song?id=${s.id}`}>{s.title}</Link>
              </td>
              <td>
                <span className="pill">{s.status}</span>
              </td>
              <td>{s.duration ? `${s.duration.toFixed(1)}s` : "—"}</td>
              <td>{s.bpm ?? "—"}</td>
              <td>{s.key ?? "—"}</td>
              <td>
                <button className="danger" onClick={() => api.deleteSong(s.id).then(refresh)}>
                  delete
                </button>
              </td>
            </tr>
          ))}
          {songs.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">
                no songs yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
