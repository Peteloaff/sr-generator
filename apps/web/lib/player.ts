import { api, assetUrl, type Song } from "./api";

type PlayerState = {
  song: Song | null;
  src: string | null;
  loading: boolean;
  queue: Song[];
};

const LS_KEY = "sr.nowplaying";
let state: PlayerState = { song: null, src: null, loading: false, queue: [] };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

let restored = false;
/** Reload whatever was playing before a full page reload. Call once on mount. */
export function restorePlayer() {
  if (restored || typeof window === "undefined") return;
  restored = true;
  try {
    const id = window.localStorage.getItem(LS_KEY);
    if (!id) return;
    api.getSong(id).then((s) => playSong(s, [s])).catch(() => {});
  } catch {
    /* ignore */
  }
}

export const playerStore = {
  subscribe: (f: () => void) => {
    subs.add(f);
    return () => subs.delete(f);
  },
  get: () => state,
};

const PLAYABLE = ["song_master", "song_mix", "master", "mix", "section_render"];

export async function playSong(song: Song, queue: Song[] = []) {
  state = {
    song,
    src: null,
    loading: true,
    queue: queue.length ? queue : [song],
  };
  emit();
  try {
    window.localStorage.setItem(LS_KEY, song.id);
  } catch {
    /* ignore */
  }
  try {
    const assets = await api.listAssets(song.id);
    let asset = null;
    for (const t of PLAYABLE) {
      asset = assets.find((a) => a.asset_type === t) ?? null;
      if (asset) break;
    }
    state = {
      ...state,
      src: asset ? assetUrl(song.id, asset.id, { inline: true }) : null,
      loading: false,
    };
  } catch {
    state = { ...state, loading: false };
  }
  emit();
}

export function step(dir: 1 | -1) {
  const { song, queue } = state;
  if (!song || queue.length < 2) return;
  const i = queue.findIndex((s) => s.id === song.id);
  const next = queue[(i + dir + queue.length) % queue.length];
  if (next) playSong(next, queue);
}

export function closePlayer() {
  state = { song: null, src: null, loading: false, queue: [] };
  try {
    window.localStorage.removeItem(LS_KEY);
  } catch {
    /* ignore */
  }
  emit();
}
