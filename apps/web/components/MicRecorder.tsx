"use client";

import { useEffect, useRef, useState } from "react";

type Phase = "idle" | "recording" | "recorded";

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"]) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

function extFor(mime: string): string {
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

export default function MicRecorder({
  onRecorded,
  label = "Record voice",
  hint,
}: {
  onRecorded: (file: File) => Promise<void> | void;
  label?: string;
  hint?: string;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const blobRef = useRef<{ blob: Blob; ext: string } | null>(null);

  useEffect(() => {
    return () => {
      stopMeter();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      if (tickRef.current) clearInterval(tickRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopMeter = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
  };

  const start = async () => {
    setErr(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setErr("This browser has no microphone access.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      // level meter
      const ac = new AudioContext();
      const src = ac.createMediaStreamSource(stream);
      const analyser = ac.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const loop = () => {
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
        setLevel(Math.min(1, peak / 90));
        rafRef.current = requestAnimationFrame(loop);
      };
      loop();

      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = () => {
        const type = rec.mimeType || mime || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        blobRef.current = { blob, ext: extFor(type) };
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(blob));
        setPhase("recorded");
      };
      recRef.current = rec;
      rec.start();
      setPhase("recording");
      setSeconds(0);
      tickRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setErr(
        String(e).includes("NotAllowed")
          ? "Microphone permission was denied."
          : `Could not start recording: ${e}`,
      );
    }
  };

  const stop = () => {
    recRef.current?.stop();
    if (tickRef.current) clearInterval(tickRef.current);
    stopMeter();
    setLevel(0);
    streamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const reset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    blobRef.current = null;
    setPhase("idle");
    setSeconds(0);
  };

  const save = async () => {
    if (!blobRef.current) return;
    setSaving(true);
    setErr(null);
    try {
      const { blob, ext } = blobRef.current;
      await onRecorded(new File([blob], `recording.${ext}`, { type: blob.type }));
      reset();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  const mmss = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <div className="stack" style={{ gap: "0.5rem" }}>
      <div className="recorder">
        {phase === "idle" && (
          <>
            <span className="rec-dot" />
            <button className="sm" onClick={start}>
              ● {label}
            </button>
          </>
        )}
        {phase === "recording" && (
          <>
            <span className="rec-dot live" />
            <span className="muted">{mmss}</span>
            <span
              style={{
                width: 60,
                height: 6,
                borderRadius: 999,
                background: "var(--line)",
                overflow: "hidden",
              }}
            >
              <i
                style={{
                  display: "block",
                  height: "100%",
                  width: `${level * 100}%`,
                  background: "var(--accent)",
                }}
              />
            </span>
            <button className="sm primary" onClick={stop}>
              ■ Stop
            </button>
          </>
        )}
        {phase === "recorded" && (
          <>
            {previewUrl && <audio controls src={previewUrl} style={{ maxWidth: 180 }} />}
            <button className="sm primary" onClick={save} disabled={saving}>
              {saving ? "saving…" : "Use this take"}
            </button>
            <button className="sm ghost" onClick={reset} disabled={saving}>
              redo
            </button>
          </>
        )}
      </div>
      {hint && phase === "idle" && <span className="faint" style={{ fontSize: "0.82rem" }}>{hint}</span>}
      {err && <span className="danger" style={{ fontSize: "0.85rem" }}>{err}</span>}
    </div>
  );
}
