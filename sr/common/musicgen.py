"""Deterministic instrumental synthesis (pure NumPy).

Not a music model - a small arranger + synth that renders drums / bass / chords /
arp in a requested key and tempo, shaped by a "band character" vector distilled
from the Band DNA (Stage 6). Same (seed, params, character) -> identical audio.
A real model (ACE-Step / MusicGen / ...) implements the same
``MusicGenerationProvider`` contract.
"""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR
from sr.common.seeds import bounded_jitter, derive_seed

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# scale degrees (semitones) for a triad on each diatonic degree
_MAJOR_PROG = {"I-V-vi-IV": [0, 7, 9, 5], "I-IV-V": [0, 5, 7], "vi-IV-I-V": [9, 5, 0, 7]}
_MINOR_PROG = {"i-VI-III-VII": [0, 8, 3, 10], "i-iv-v": [0, 5, 7], "i-VII-VI-VII": [0, 10, 8, 10]}


def _tonic_semitone(key: str) -> tuple[int, str]:
    parts = (key or "C major").split()
    name = parts[0] if parts else "C"
    mode = parts[1].lower() if len(parts) > 1 else "major"
    idx = _NOTES.index(name) if name in _NOTES else 0
    return idx, ("minor" if mode.startswith("min") else "major")


def _adsr(n: int, a: float, d: float, s: float, r: float, sr: int = SR) -> np.ndarray:
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    ai = min(int(a * sr), n)
    di = min(int(d * sr), n - ai)
    ri = min(int(r * sr), n)
    env = np.full(n, s, dtype=np.float32)
    if ai:
        env[:ai] = np.linspace(0.0, 1.0, ai)
    if di:
        env[ai : ai + di] = np.linspace(1.0, s, di)
    if ri:
        env[n - ri :] = np.linspace(env[n - ri], 0.0, ri)
    return env


def _osc(freq: float, n: int, kind: str, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    ph = 2 * np.pi * freq * t
    if kind == "sine":
        return np.sin(ph)
    if kind == "saw":
        return 2.0 * (t * freq - np.floor(0.5 + t * freq))
    if kind == "square":
        return np.sign(np.sin(ph))
    return np.sin(ph)


def _note_hz(semitone_from_c: int, octave: int = 4) -> float:
    return 440.0 * 2 ** ((semitone_from_c + 12 * (octave - 4) - 9) / 12.0)


def _kick(n: int, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    f = 110 * np.exp(-t * 30) + 45
    return (np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 9)).astype(np.float32)


def _snare(n: int, seed: int, sr: int = SR) -> np.ndarray:
    rng = np.random.default_rng(seed & ((1 << 63) - 1))
    t = np.arange(n) / sr
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 22)
    noise = rng.standard_normal(n).astype(np.float32) * np.exp(-t * 16)
    return (0.5 * tone + 0.8 * noise).astype(np.float32)


def _hat(n: int, seed: int, sr: int = SR) -> np.ndarray:
    rng = np.random.default_rng(seed & ((1 << 63) - 1))
    t = np.arange(n) / sr
    x = rng.standard_normal(n).astype(np.float32)
    x = x - np.convolve(x, np.ones(12) / 12, mode="same")  # crude highpass
    return (x * np.exp(-t * 45)).astype(np.float32)


def generate(
    *,
    bpm: float,
    key: str,
    seconds: float,
    seed: int,
    character: dict | None = None,
    energy_curve: list[float] | None = None,
    sr: int = SR,
) -> dict:
    ch = character or {}
    brightness = float(ch.get("brightness", 0.0))
    drive = float(ch.get("drive", 0.2))
    drum_busy = float(np.clip(ch.get("drum_busy", 0.5), 0.0, 1.0))
    bpm = float(np.clip(bpm or 120.0, 60.0, 200.0))
    n = max(1, int(seconds * sr))
    tonic, mode = _tonic_semitone(key)

    progs = _MINOR_PROG if mode == "minor" else _MAJOR_PROG
    prog_name = sorted(progs)[derive_seed(seed, "prog") % len(progs)]
    # start and end on the tonic so the key reads clearly
    degrees = [0, *progs[prog_name], 0]

    beat = 60.0 / bpm
    spb = int(beat * sr)
    bars = max(1, int(np.ceil(seconds / (beat * 4))))

    # tonic pedal - a quiet low drone the whole way through anchors the key
    tonic_hz = _note_hz(tonic % 12, 2)
    pedal = (_osc(tonic_hz, n, "sine") * 0.12).astype(np.float32)

    drums = np.zeros(n, dtype=np.float32)
    bass = np.zeros(n, dtype=np.float32)
    chords = np.zeros(n, dtype=np.float32)
    arp = np.zeros(n, dtype=np.float32)

    for bar in range(bars):
        deg = degrees[bar % len(degrees)]
        root = (tonic + deg) % 12
        third = root + (3 if mode == "minor" else 4)
        fifth = root + 7
        bar_start = bar * spb * 4

        for b in range(4):
            s = bar_start + b * spb
            if s >= n:
                break
            e = min(n, s + spb)
            seg = e - s
            # kick on 1 & 3, snare on 2 & 4
            if b in (0, 2) or (b == 3 and drum_busy > 0.6 and (bar % 2)):
                k = _kick(min(seg, int(0.35 * sr)))
                drums[s : s + len(k)] += k * 0.9
            if b in (1, 3):
                sn = _snare(min(seg, int(0.25 * sr)), derive_seed(seed, "sn", bar, b))
                drums[s : s + len(sn)] += sn * 0.55
            # hats: 8ths, more with busyness
            steps = 2 if drum_busy > 0.35 else 1
            for h in range(steps):
                hs = s + h * (spb // 2)
                if hs >= n:
                    break
                ht = _hat(min(n - hs, int(0.08 * sr)), derive_seed(seed, "hh", bar, b, h))
                drums[hs : hs + len(ht)] += ht * (0.18 + 0.12 * drum_busy)

            # bass: root, walk to fifth on beat 4
            bnote = fifth if b == 3 else root
            bf = _note_hz(bnote % 12, 2)
            benv = _adsr(seg, 0.005, 0.05, 0.7, 0.06)
            bwave = 0.7 * _osc(bf, seg, "sine") + 0.3 * _osc(bf, seg, "saw")
            bass[s:e] += (bwave * benv * 0.5).astype(np.float32)

        # chord pad for the whole bar
        ce = min(n, bar_start + spb * 4)
        cseg = ce - bar_start
        if cseg > 0:
            penv = _adsr(cseg, 0.06, 0.2, 0.55, 0.25)
            stack = np.zeros(cseg, dtype=np.float32)
            for note in (root, third, fifth, root + 12):
                f = _note_hz(note % 12, 4 if note < 12 else 5)
                stack += _osc(f, cseg, "saw") * 0.25
            # brightness -> simple high-frequency emphasis
            if abs(brightness) > 1e-3:
                d = np.zeros_like(stack)
                d[1:] = stack[1:] - stack[:-1]
                stack = stack + np.clip(brightness, -1, 1) * 0.4 * d
            chords[bar_start:ce] += (stack * penv * 0.22).astype(np.float32)

            # arp: eighth-notes through the triad
            arp_notes = [root, third, fifth, root + 12]
            step = spb // 2
            for i in range(cseg // step):
                a0 = bar_start + i * step
                aseg = min(step, n - a0)
                if aseg <= 0:
                    break
                f = _note_hz(arp_notes[i % 4] % 12, 5)
                aenv = _adsr(aseg, 0.003, 0.04, 0.3, 0.05)
                arp[a0 : a0 + aseg] += (_osc(f, aseg, "square") * aenv * 0.09).astype(np.float32)

    # section energy envelope (from the band's mean energy profile)
    if energy_curve:
        ec = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(energy_curve)), energy_curve)
        ec = 0.55 + 0.45 * np.clip(ec, 0.0, 1.5)
    else:
        ec = np.ones(n, dtype=np.float32)

    def _fit(x):
        return (x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))).astype(np.float32)

    drums, bass, chords, arp = map(_fit, (drums, bass, chords, arp))
    bass = bass + _fit(pedal)
    mono = (drums + bass * ec + chords * ec + arp * ec).astype(np.float32)
    if drive > 1e-3:
        mono = ((1 - drive) * mono + drive * np.tanh(3 * mono) / np.tanh(3)).astype(np.float32)
    peak = float(np.max(np.abs(mono))) or 1.0
    mono = mono * (0.9 / peak)

    # gentle stereo: chords/arp spread, drums/bass centred
    spread = 0.15
    left = drums + bass + (chords + arp) * (1 - spread)
    right = drums + bass + (chords + arp) * (1 + spread)
    st = np.stack([_fit(left), _fit(right)], axis=1) * ec[:, None]
    if drive > 1e-3:
        st = ((1 - drive) * st + drive * np.tanh(3 * st) / np.tanh(3)).astype(np.float32)
    stp = float(np.max(np.abs(st))) or 1.0
    stereo = (st * (0.9 / stp)).astype(np.float32)

    return {
        "audio": stereo,
        "sample_rate": sr,
        "metadata": {
            "bpm": round(bpm, 1),
            "key": f"{_NOTES[tonic]} {mode}",
            "progression": prog_name,
            "bars": bars,
            "character": {"brightness": brightness, "drive": drive, "drum_busy": drum_busy},
            "seed": seed,
            "swing_hint_ms": round(bounded_jitter(derive_seed(seed, "swing"), 0, 12), 2),
        },
    }
