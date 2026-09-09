"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import Link from "next/link";
import { closePlayer, playerStore, restorePlayer, step } from "@/lib/player";

export default function NowPlaying() {
  const s = useSyncExternalStore(playerStore.subscribe, playerStore.get, playerStore.get);
  const audio = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    restorePlayer();
  }, []);

  useEffect(() => {
    if (s.src && audio.current) {
      audio.current.load();
      audio.current.play().catch(() => {});
    }
  }, [s.src]);

  if (!s.song) return null;
  const multi = s.queue.length > 1;

  return (
    <div className="now-playing">
      <div className="np-title">
        <Link href={`/song?id=${s.song.id}`}>{s.song.title}</Link>
        <span className="faint">
          {s.loading
            ? "loading…"
            : s.src
              ? s.song.genre
                ? s.song.genre.replace(/_/g, " ")
                : "now playing"
              : "not generated yet"}
        </span>
      </div>

      <div className="np-controls">
        {multi && (
          <button className="np-btn" title="previous" onClick={() => step(-1)}>
            ⏮
          </button>
        )}
        <audio
          ref={audio}
          src={s.src ?? undefined}
          controls
          preload="none"
          onEnded={() => step(1)}
        />
        {multi && (
          <button className="np-btn" title="next" onClick={() => step(1)}>
            ⏭
          </button>
        )}
        <button className="np-btn" title="close" onClick={closePlayer}>
          ✕
        </button>
      </div>
    </div>
  );
}
