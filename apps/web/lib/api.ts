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

async function upload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  const headers: Record<string, string> = {};
  const band = getBandId();
  if (band) headers["X-Band-Id"] = band;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd, headers });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export function assetUrl(songId: string, assetId: string, opts: { inline?: boolean } = {}) {
  const q = opts.inline ? "?inline=true" : "";
  return `${API_BASE}/songs/${songId}/assets/${assetId}/download${q}`;
}

export interface Band { id: string; name: string; slug: string; notes: string | null }
export interface Singer {
  id: string; band_id: string; name: string; display_name: string | null;
  clean_enabled: boolean; scream_enabled: boolean;
  consent_training: boolean; consent_generation: boolean; consent_commercial: boolean;
  training_status: string;
}
export interface VoiceProfile {
  median_f0?: number; formant_semitones?: number; brightness?: number;
  breathiness?: number; roughness?: number;
}
export interface VoiceModel {
  singer_id: string; training_status: string; training_samples: number;
  voice_model_provider: string | null; voice_profile: VoiceProfile | null;
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
  gain_db: number; pan: number; interval_semitones: number;
  pitch_offset_semitones: number; style: string | null;
}
export type FxStep = { type: string } & Record<string, number | string>;
export interface VocalRole {
  id: string; section_id: string | null; lyric_line_id: string | null; role_type: string;
  ensemble_size: number; width: number; notes: string | null;
  processing_json: FxStep[] | null; assignments: Assignment[];
}
export interface VocalPreset {
  id: string; band_id: string; name: string; description: string | null;
  spec_json: { roles: unknown[] };
}
export interface ABResult {
  seed: number; ensemble_job_id: string; flat_job_id: string;
  ensemble: Record<string, number | string>; flat: Record<string, number | string>;
  verdict: Record<string, boolean | number>;
}
export interface NormalizedShare {
  singer_id: string; weight_percent: number; normalized_percent: number; ensemble_takes: number;
}
export interface AudioAsset {
  id: string; asset_type: string; label: string | null; file_path: string;
  duration: number | null; sample_rate: number | null; channels: number | null;
  singer_id: string | null; section_id: string | null; generation_job_id: string | null;
}
export interface Waveform { asset_id: string; buckets: number; duration: number | null; peaks: number[][] }
export interface Job {
  id: string; job_type: string; status: string; provider: string;
  provider_version: string | null; progress: number; seed: number | null; error: string | null;
  logs: string | null;
  outputs: AudioAsset[];
}
export interface RenderTake {
  id: string; vocal_role_id: string; singer_id: string; take_index: number; child_seed: number;
  timing_offset_ms: number; pitch_cents: number; formant_shift: number; gain_db: number; pan: number;
  source_kind: string; source_asset_id: string | null; output_asset_id: string | null;
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
  createSectionRole: (sectionId: string, body: Record<string, unknown>) =>
    req<VocalRole>(`/sections/${sectionId}/roles`, { method: "POST", body: JSON.stringify(body) }),
  createLineRole: (lineId: string, body: Record<string, unknown>) =>
    req<VocalRole>(`/lines/${lineId}/roles`, { method: "POST", body: JSON.stringify(body) }),
  updateRole: (id: string, patch: Record<string, unknown>) =>
    req<VocalRole>(`/roles/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
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

  listPresets: () => req<VocalPreset[]>("/vocal-presets"),
  savePresetFromSection: (name: string, from_section_id: string) =>
    req<VocalPreset>("/vocal-presets", {
      method: "POST",
      body: JSON.stringify({ name, from_section_id }),
    }),
  applyPreset: (presetId: string, section_id: string) =>
    req<{ created_roles: VocalRole[]; skipped_singers: string[] }>(
      `/vocal-presets/${presetId}/apply`,
      { method: "POST", body: JSON.stringify({ section_id }) },
    ),
  deletePreset: (id: string) => req<void>(`/vocal-presets/${id}`, { method: "DELETE" }),
  renderAB: (songId: string, sectionId: string) =>
    req<ABResult>(`/songs/${songId}/sections/${sectionId}/ab`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getVoiceModel: (singerId: string) => req<VoiceModel>(`/singers/${singerId}/voice-model`),
  setVoiceProfile: (singerId: string, patch: VoiceProfile) =>
    req<VoiceModel>(`/singers/${singerId}/voice-model`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  trainVoiceModel: (singerId: string) =>
    req<Job>(`/singers/${singerId}/voice-model/train`, { method: "POST" }),
  listVoiceSamples: (singerId: string) =>
    req<AudioAsset[]>(`/singers/${singerId}/samples`),
  uploadVoiceSample: (singerId: string, file: File) =>
    upload<AudioAsset>(`/singers/${singerId}/samples`, file),
  deleteVoiceSample: (singerId: string, assetId: string) =>
    req<void>(`/singers/${singerId}/samples/${assetId}`, { method: "DELETE" }),
  uploadGuide: (songId: string, sectionId: string, file: File) =>
    upload<AudioAsset>(`/songs/${songId}/sections/${sectionId}/guide`, file),

  listSourceTakes: (songId: string, sectionId: string) =>
    req<AudioAsset[]>(`/songs/${songId}/sections/${sectionId}/takes`),
  uploadSourceTake: (songId: string, sectionId: string, singerId: string, file: File) =>
    upload<AudioAsset>(`/songs/${songId}/sections/${sectionId}/takes`, file, {
      singer_id: singerId,
    }),
  uploadInstrumental: (songId: string, sectionId: string, file: File) =>
    upload<AudioAsset>(`/songs/${songId}/sections/${sectionId}/instrumental`, file),
  renderSection: (
    songId: string,
    sectionId: string,
    body: { seed?: number | null; mode?: "ensemble" | "flat" } = {},
  ) =>
    req<Job>(`/songs/${songId}/sections/${sectionId}/render`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSectionRenders: (songId: string, sectionId: string) =>
    req<Job[]>(`/songs/${songId}/sections/${sectionId}/renders`),
  listRenderTakes: (songId: string, jobId: string) =>
    req<RenderTake[]>(`/songs/${songId}/renders/${jobId}/takes`),
  getJob: (jobId: string) => req<Job>(`/jobs/${jobId}`),
  waitJob: (jobId: string) =>
    req<Job>(`/jobs/${jobId}/wait?timeout=90`, { method: "POST" }),

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
