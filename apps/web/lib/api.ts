export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const BAND_KEY = "sr.bandId";

export function getBandId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(BAND_KEY);
  } catch {
    return null;
  }
}

export function setBandId(id: string | null) {
  try {
    if (id) window.localStorage.setItem(BAND_KEY, id);
    else window.localStorage.removeItem(BAND_KEY);
  } catch {
    /* ignore */
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const band = getBandId();
  if (band) headers["X-Band-Id"] = band;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const headers: Record<string, string> = {};
  const band = getBandId();
  if (band) headers["X-Band-Id"] = band;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd, headers });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export interface Band { id: string; name: string; slug: string; notes: string | null }
export interface Singer {
  id: string; band_id: string; name: string; display_name: string | null;
  clean_enabled: boolean; scream_enabled: boolean;
  consent_training: boolean; consent_generation: boolean; consent_commercial: boolean;
  training_status: string;
}
export interface Song {
  id: string; band_id: string; project_id: string | null; title: string;
  status: string; bpm: number | null; key: string | null; duration: number | null; seed: number | null;
}
export interface Project { id: string; band_id: string; name: string; description: string | null }
export interface Section {
  id: string; song_id: string; section_type: string; name: string | null;
  start_time: number | null; end_time: number | null; order_index: number;
}
export interface LyricLine {
  id: string; song_id: string; section_id: string | null; order_index: number;
  text: string; start_time: number | null; end_time: number | null;
}
export interface Assignment {
  id: string; vocal_role_id: string; singer_id: string; weight_percent: number;
  gain_db: number; pan: number; pitch_offset_semitones: number; style: string | null;
}
export interface VocalRole {
  id: string; section_id: string | null; lyric_line_id: string | null; role_type: string;
  ensemble_size: number; width: number; notes: string | null; assignments: Assignment[];
}
export interface NormalizedShare {
  singer_id: string; weight_percent: number; normalized_percent: number; ensemble_takes: number;
}
export interface AudioAsset {
  id: string; asset_type: string; file_path: string; duration: number | null;
  sample_rate: number | null; channels: number | null;
}
export interface Waveform { asset_id: string; buckets: number; duration: number | null; peaks: number[][] }
export interface Job {
  id: string; job_type: string; status: string; provider: string;
  provider_version: string | null; progress: number;
  outputs: { id: string; asset_type: string; file_path: string; duration: number | null }[];
}

export const ROLE_TYPES = ["lead", "double", "harmony", "background", "gang", "scream"] as const;
export const SECTION_TYPES = [
  "intro", "verse", "pre_chorus", "chorus", "post_chorus", "bridge", "breakdown", "solo", "outro", "other",
] as const;

export const api = {
  health: () => req<Record<string, unknown>>("/health"),

  listBands: () => req<Band[]>("/bands"),
  createBand: (name: string) => req<Band>("/bands", { method: "POST", body: JSON.stringify({ name }) }),
  bandStats: (id: string) => req<{ singers: number; projects: number }>(`/bands/${id}/stats`),

  listSingers: () => req<Singer[]>("/singers"),
  createSinger: (name: string) => req<Singer>("/singers", { method: "POST", body: JSON.stringify({ name }) }),
  updateSinger: (id: string, patch: Partial<Singer>) =>
    req<Singer>(`/singers/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSinger: (id: string) => req<void>(`/singers/${id}`, { method: "DELETE" }),

  listProjects: () => req<Project[]>("/projects"),
  createProject: (name: string) => req<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  exportProject: (id: string) => req<unknown>(`/projects/${id}/export`),
  importProject: (data: unknown) =>
    req<Project>("/projects/import", { method: "POST", body: JSON.stringify(data) }),

  listSongs: () => req<Song[]>("/songs"),
  createSong: (title: string) => req<Song>("/songs", { method: "POST", body: JSON.stringify({ title }) }),
  getSong: (id: string) => req<Song>(`/songs/${id}`),
  updateSong: (id: string, patch: Partial<Song>) =>
    req<Song>(`/songs/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSong: (id: string) => req<void>(`/songs/${id}`, { method: "DELETE" }),

  uploadAudio: (songId: string, file: File) => upload<AudioAsset>(`/songs/${songId}/audio`, file),
  listAssets: (songId: string) => req<AudioAsset[]>(`/songs/${songId}/assets`),
  waveform: (songId: string, assetId: string) =>
    req<Waveform>(`/songs/${songId}/assets/${assetId}/waveform`),

  listSections: (songId: string) => req<Section[]>(`/songs/${songId}/sections`),
  createSection: (songId: string, body: Partial<Section>) =>
    req<Section>(`/songs/${songId}/sections`, { method: "POST", body: JSON.stringify(body) }),
  updateSection: (songId: string, id: string, patch: Partial<Section>) =>
    req<Section>(`/songs/${songId}/sections/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSection: (songId: string, id: string) =>
    req<void>(`/songs/${songId}/sections/${id}`, { method: "DELETE" }),

  listLines: (songId: string) => req<LyricLine[]>(`/songs/${songId}/lines`),
  replaceLines: (songId: string, text: string) =>
    req<LyricLine[]>(`/songs/${songId}/lines`, { method: "PUT", body: JSON.stringify({ text }) }),
  updateLine: (songId: string, id: string, patch: Partial<LyricLine>) =>
    req<LyricLine>(`/songs/${songId}/lines/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  sectionRoles: (sectionId: string) => req<VocalRole[]>(`/sections/${sectionId}/roles`),
  lineRoles: (lineId: string) => req<VocalRole[]>(`/lines/${lineId}/roles`),
  createSectionRole: (sectionId: string, body: Partial<VocalRole>) =>
    req<VocalRole>(`/sections/${sectionId}/roles`, { method: "POST", body: JSON.stringify(body) }),
  createLineRole: (lineId: string, body: Partial<VocalRole>) =>
    req<VocalRole>(`/lines/${lineId}/roles`, { method: "POST", body: JSON.stringify(body) }),
  deleteRole: (id: string) => req<void>(`/roles/${id}`, { method: "DELETE" }),
  normalized: (roleId: string) => req<NormalizedShare[]>(`/roles/${roleId}/normalized`),
  addAssignment: (roleId: string, singer_id: string, weight_percent: number) =>
    req<Assignment>(`/roles/${roleId}/assignments`, {
      method: "POST",
      body: JSON.stringify({ singer_id, weight_percent }),
    }),
  updateAssignment: (id: string, patch: Partial<Assignment>) =>
    req<Assignment>(`/assignments/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteAssignment: (id: string) => req<void>(`/assignments/${id}`, { method: "DELETE" }),

  listJobs: () => req<Job[]>("/jobs"),
  createMockJob: (songId: string | null) =>
    req<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify({
        job_type: "mock_generation",
        song_id: songId,
        parameters: { prompt: "stage 1 smoke", duration: 2.0 },
      }),
    }),
};
