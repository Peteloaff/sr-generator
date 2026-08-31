export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface Singer {
  id: string;
  name: string;
  display_name: string | null;
  clean_enabled: boolean;
  scream_enabled: boolean;
  consent_training: boolean;
  consent_generation: boolean;
  consent_commercial: boolean;
  training_status: string;
}

export interface Song {
  id: string;
  title: string;
  status: string;
  bpm: number | null;
  key: string | null;
  seed: number | null;
}

export interface Job {
  id: string;
  job_type: string;
  status: string;
  provider: string;
  provider_version: string | null;
  progress: number;
  outputs: { id: string; asset_type: string; file_path: string; duration: number | null }[];
}

export const api = {
  health: () => req<Record<string, unknown>>("/health"),
  listSingers: () => req<Singer[]>("/singers"),
  createSinger: (name: string) =>
    req<Singer>("/singers", { method: "POST", body: JSON.stringify({ name }) }),
  updateSinger: (id: string, patch: Partial<Singer>) =>
    req<Singer>(`/singers/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSinger: (id: string) => req<void>(`/singers/${id}`, { method: "DELETE" }),
  listSongs: () => req<Song[]>("/songs"),
  createSong: (title: string) =>
    req<Song>("/songs", { method: "POST", body: JSON.stringify({ title }) }),
  deleteSong: (id: string) => req<void>(`/songs/${id}`, { method: "DELETE" }),
  listJobs: () => req<Job[]>("/jobs"),
  createMockJob: (songId: string | null) =>
    req<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify({
        job_type: "mock_generation",
        song_id: songId,
        parameters: { prompt: "stage 0 smoke", duration: 2.0 },
      }),
    }),
};
