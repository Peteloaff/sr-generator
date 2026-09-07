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
    # release may not eat into the attack, or it would ramp down from ~0
    ri = min(int(r * sr), max(1, n - ai))
    env = np.full(n, s, dtype=np.float32)
    if ai:
        env[:ai] = np.linspace(0.0, 1.0, ai)
    if di:
        env[ai : ai + di] = np.linspace(1.0, s, di)
    if ri:
        env[n - ri :] = np.linspace(float(env[n - ri]), 0.0, ri)
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
    players: dict[str, dict] | None = None,
    sr: int = SR,
) -> dict:
    ch = character or {}
    players = players or {}
    brightness = float(ch.get("brightness", 0.0))
    drive = float(ch.get("drive", 0.2))
    drum_busy = float(np.clip(ch.get("drum_busy", 0.5), 0.0, 1.0))
    # Genre-feel knobs (Stage 14). All optional; 0 => previous behaviour.
    distortion = float(np.clip(ch.get("distortion", 0.0), 0.0, 1.0))
    sustain = float(np.clip(ch.get("sustain", 0.5), 0.0, 1.0))
    sub_weight = float(np.clip(ch.get("sub_weight", 0.35), 0.0, 1.0))
    swing = float(np.clip(ch.get("swing", 0.0), 0.0, 0.6))
    detune = float(ch.get("tuning_semitones", 0.0))
    drive = float(np.clip(drive + 0.5 * distortion, 0.0, 1.0))
    bpm = float(np.clip(bpm or 120.0, 40.0, 240.0))
    n = max(1, int(seconds * sr))
    tonic, mode = _tonic_semitone(key)

    def note_hz(semitone_from_c: int, octave: int = 4) -> float:
        return _note_hz(semitone_from_c, octave) * 2.0 ** (detune / 12.0)

    progs = _MINOR_PROG if mode == "minor" else _MAJOR_PROG
    allowed = [p for p in (ch.get("progressions") or []) if p in progs]
    if allowed:
        progs = {p: progs[p] for p in allowed}
    prog_name = sorted(progs)[derive_seed(seed, "prog") % len(progs)]
    # start and end on the tonic so the key reads clearly
    degrees = [0, *progs[prog_name], 0]

    beat = 60.0 / bpm
    spb = int(beat * sr)
    bars = max(1, int(np.ceil(seconds / (beat * 4))))

    # tonic pedal - a low drone the whole way through anchors the key; sub_weight
    # and low tunings make it heavier (doom / sludge).
    tonic_hz = note_hz(tonic % 12, 2)
    pedal_gain = 0.08 + 0.16 * sub_weight
    pedal = (_osc(tonic_hz, n, "sine") * pedal_gain).astype(np.float32)

    # --- per-part overrides from the assigned players' learned styles ---------
    drum_p = players.get("drums") or {}
    bass_p = players.get("bass") or {}
    rhythm_p = players.get("rhythm_guitar") or players.get("keys") or {}
    lead_p = players.get("lead_guitar") or players.get("keys") or {}
    if drum_p:
        drum_busy = float(np.clip(drum_p.get("busyness", drum_busy), 0.0, 1.0))
        swing = float(np.clip(max(swing, float(drum_p.get("swing", 0.0))), 0.0, 0.6))
    drum_dyn = float(np.clip(drum_p.get("dynamics", 0.35), 0.0, 1.0))
    bass_drive = float(np.clip(bass_p.get("drive", drive), 0.0, 1.0))
    bass_sustain = float(np.clip(bass_p.get("sustain", sustain), 0.0, 1.0))
    bass_oct = -1 if float(bass_p.get("register_hz", 120.0)) < 85.0 else 0
    rhythm_bright = float(np.clip(rhythm_p.get("brightness", brightness), -1.0, 1.0))
    rhythm_drive = float(np.clip(rhythm_p.get("drive", drive), 0.0, 1.0))
    rhythm_sustain = float(np.clip(rhythm_p.get("sustain", sustain), 0.0, 1.0))
    lead_bright = float(np.clip(lead_p.get("brightness", brightness), -1.0, 1.0))
    lead_busy = float(np.clip(lead_p.get("busyness", 0.5), 0.0, 1.0))

    swing_shift = int(swing * (spb // 2) * 0.5)

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
                vel = 1.0 + drum_dyn * bounded_jitter(
                    derive_seed(seed, "vel", bar, b), -0.35, 0.15
                )
                drums[s : s + len(sn)] += sn * 0.55 * float(vel)
            # hats: 8ths, more with busyness; the off-beat is nudged late by swing
            steps = 2 if drum_busy > 0.35 else 1
            for h in range(steps):
                hs = s + h * (spb // 2) + (swing_shift if h == 1 else 0)
                if hs >= n:
                    break
                ht = _hat(min(n - hs, int(0.08 * sr)), derive_seed(seed, "hh", bar, b, h))
                drums[hs : hs + len(ht)] += ht * (0.18 + 0.12 * drum_busy)

            # bass: root, walk to fifth on beat 4. sustain lengthens the note;
            # sub_weight adds an octave-down layer.
            bnote = fifth if b == 3 else root
            bf = note_hz(bnote % 12, 2 + bass_oct)
            benv = _adsr(seg, 0.005, 0.05, 0.7, 0.05 + 0.5 * bass_sustain)
            bwave = 0.7 * _osc(bf, seg, "sine") + 0.3 * _osc(bf, seg, "saw")
            if sub_weight > 0.5:
                bwave = bwave + (sub_weight - 0.5) * _osc(bf * 0.5, seg, "sine")
            bass[s:e] += (bwave * benv * 0.5).astype(np.float32)

        # chord pad for the whole bar
        ce = min(n, bar_start + spb * 4)
        cseg = ce - bar_start
        if cseg > 0:
            penv = _adsr(cseg, 0.06, 0.2, 0.4 + 0.4 * rhythm_sustain, 0.2 + 0.7 * rhythm_sustain)
            stack = np.zeros(cseg, dtype=np.float32)
            for note in (root, third, fifth, root + 12):
                f = note_hz(note % 12, 4 if note < 12 else 5)
                stack += _osc(f, cseg, "saw") * 0.25
            # brightness -> simple high-frequency emphasis
            if abs(rhythm_bright) > 1e-3:
                d = np.zeros_like(stack)
                d[1:] = stack[1:] - stack[:-1]
                stack = stack + np.clip(rhythm_bright, -1, 1) * 0.4 * d
            chords[bar_start:ce] += (stack * penv * 0.22).astype(np.float32)

            # lead line: arpeggio through the triad; a busier player plays 16ths
            arp_notes = [root, third, fifth, root + 12]
            step = spb // 4 if lead_busy > 0.6 else spb // 2
            step = max(1, step)
            for i in range(cseg // step):
                a0 = bar_start + i * step + (swing_shift if i % 2 else 0)
                aseg = min(step, n - a0)
                if aseg <= 0:
                    break
                f = note_hz(arp_notes[i % 4] % 12, 5)
                aenv = _adsr(aseg, 0.003, 0.04, 0.25 + 0.4 * sustain, 0.04 + 0.2 * sustain)
                wave = _osc(f, aseg, "square")
                if lead_bright < -0.1:
                    wave = _osc(f, aseg, "sine")
                arp[a0 : a0 + aseg] += (wave * aenv * 0.09).astype(np.float32)

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

    def _ws(x: np.ndarray, d: float) -> np.ndarray:
        if d <= 1e-3:
            return x.astype(np.float32)
        sh = 3.0 + 7.0 * (d if d < 1.0 else 1.0) + 4.0 * distortion
        return ((1 - d) * x + d * np.tanh(sh * x) / np.tanh(sh)).astype(np.float32)

    # per-instrument drive from the assigned players (bass / rhythm), song drive
    # everywhere else
    bass = _ws(bass, bass_drive)
    chords = _ws(chords, rhythm_drive)
    drums = _ws(drums, drive * 0.5)
    arp = _ws(arp, drive)

    # place each part in the field, apply the section energy envelope
    def _stereo(x: np.ndarray, pan: float) -> np.ndarray:
        lg, rg = np.sqrt(0.5 - pan / 2), np.sqrt(0.5 + pan / 2)
        return (np.stack([x * lg, x * rg], axis=1) * ec[:, None]).astype(np.float32)

    def _pg(*roles: str) -> float:
        for r in roles:
            p = players.get(r)
            if p is not None:
                return 0.0 if p.get("mute") else float(10.0 ** (p.get("gain_db", 0.0) / 20.0))
        return 1.0

    parts = {
        "drums": _stereo(drums, 0.0) * _pg("drums"),
        "bass": _stereo(bass, 0.0) * _pg("bass"),
        "rhythm": _stereo(chords, -0.18) * _pg("rhythm_guitar", "keys"),
        "lead": _stereo(arp, 0.18) * _pg("lead_guitar", "keys"),
    }
    mixed = sum(parts.values())
    gain = 0.9 / (float(np.max(np.abs(mixed))) or 1.0)
    stereo = (mixed * gain).astype(np.float32)
    stems = {k: (v * gain).astype(np.float32) for k, v in parts.items()}

    return {
        "audio": stereo,
        "stems": stems,
        "sample_rate": sr,
        "metadata": {
            "bpm": round(bpm, 1),
            "players": sorted(players),
            "key": f"{_NOTES[tonic]} {mode}",
            "progression": prog_name,
            "bars": bars,
            "character": {
                "brightness": brightness, "drive": round(drive, 3),
                "drum_busy": drum_busy, "distortion": distortion,
                "sustain": sustain, "sub_weight": sub_weight,
                "swing": swing, "tuning_semitones": detune,
            },
            "seed": seed,
            "swing_hint_ms": round(bounded_jitter(derive_seed(seed, "swing"), 0, 12), 2),
        },
    }
