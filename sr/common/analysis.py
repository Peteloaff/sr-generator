"""Reference-song analysis (pure NumPy, deterministic).

BPM, key, tuning, an energy curve, loudness, a rough section structure, and a
compact spectral embedding - enough to build a structured Band DNA catalogue.
Estimators are simple and approximate; a real MIR stack (librosa / a model)
implements the same ``AudioAnalysisProvider`` contract.
"""

from __future__ import annotations

import numpy as np

from sr.common.dsp import SR, stft

_WIN, _HOP = 2048, 512
_PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler key profiles
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _onset_env(mag: np.ndarray) -> np.ndarray:
    flux = np.diff(mag, axis=0, prepend=mag[:1])
    flux = np.maximum(flux, 0.0).sum(axis=1)
    if flux.max() > 0:
        flux = flux / flux.max()
    k = np.hanning(9)
    return np.convolve(flux, k / k.sum(), mode="same")


def estimate_bpm(mono: np.ndarray, sr: int = SR) -> float:
    mag = np.abs(stft(mono, _WIN, _HOP))
    if mag.shape[0] < 16:
        return 0.0
    env = _onset_env(mag)
    env = np.maximum(env - env.mean(), 0.0)
    ac = np.correlate(env, env, "full")[len(env) - 1 :]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    fps = sr / _HOP
    lo, hi = int(fps * 60 / 200), int(fps * 60 / 60)  # 60..200 BPM
    seg = ac[lo:hi]
    if seg.size == 0:
        return 0.0
    lag = lo + int(np.argmax(seg))
    bpm = 60.0 * fps / lag
    while bpm < 70:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    return round(float(bpm), 1)


def _chroma(mono: np.ndarray, sr: int) -> np.ndarray:
    spec = np.abs(stft(mono, _WIN, _HOP))
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    mask = freqs > 40.0
    freqs, spec = freqs[mask], spec[:, mask]
    midi = 69 + 12 * np.log2(np.maximum(freqs, 1e-6) / 440.0)
    pc = np.mod(np.round(midi).astype(int), 12)
    chroma = np.zeros(12, dtype=np.float64)
    energy = spec.mean(axis=0)
    for c in range(12):
        chroma[c] = energy[pc == c].sum()
    return chroma / (chroma.sum() + 1e-9)


def estimate_key(mono: np.ndarray, sr: int = SR) -> dict:
    chroma = _chroma(mono, sr)
    best = (-2.0, "C", "major")
    for tonic in range(12):
        rot = np.roll(chroma, -tonic)
        for mode, profile in (("major", _MAJOR), ("minor", _MINOR)):
            r = float(np.corrcoef(rot, profile)[0, 1])
            if r > best[0]:
                best = (r, _PITCH_CLASSES[tonic], mode)
    return {"key": f"{best[1]} {best[2]}", "tonic": best[1], "mode": best[2],
            "confidence": round(best[0], 3)}


def estimate_tuning(mono: np.ndarray, sr: int = SR) -> dict:
    spec = np.abs(stft(mono, _WIN, _HOP)).mean(axis=0)
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    band = (freqs > 100) & (freqs < 2000)
    f, s = freqs[band], spec[band]
    if s.sum() <= 0:
        return {"ref_hz": 440.0, "cents": 0.0, "label": "A=440 (standard)"}
    sel = s > np.percentile(s, 98)
    peaks, weights = f[sel], s[sel]
    if peaks.size < 3:
        return {"ref_hz": 440.0, "cents": 0.0, "label": "A=440 (standard)"}
    midi = 69 + 12 * np.log2(peaks / 440.0)
    dev = (midi - np.round(midi)) * 100.0  # cents from the nearest ET note
    near = np.abs(dev) < 45.0
    if near.sum() < 3:
        return {"ref_hz": 440.0, "cents": 0.0, "label": "A=440 (standard)"}
    cents = float(np.average(dev[near], weights=weights[near]))
    ref = 440.0 * 2 ** (cents / 1200.0)
    if abs(cents) < 15:
        label = "A=440 (standard)"
    elif cents <= -85:
        label = "~half-step down"
    elif cents < 0:
        label = f"flat of A=440 ({cents:.0f} cents, A~{ref:.0f}Hz)"
    else:
        label = f"sharp of A=440 (+{cents:.0f} cents, A~{ref:.0f}Hz)"
    return {"ref_hz": round(ref, 1), "cents": round(cents, 1), "label": label}


def energy_curve(mono: np.ndarray, sr: int = SR, points: int = 64) -> list[float]:
    if mono.size == 0:
        return []
    win = max(1, mono.size // points)
    trimmed = mono[: win * points]
    rms = np.sqrt((trimmed.reshape(points, -1) ** 2).mean(axis=1))
    peak = rms.max()
    return [round(float(v / peak), 4) for v in rms] if peak > 0 else [0.0] * points


def loudness_dbfs(mono: np.ndarray) -> float:
    if mono.size == 0:
        return -120.0
    return round(20.0 * float(np.log10(max(np.sqrt(np.mean(mono**2)), 1e-6))), 2)


def _frame_features(mono: np.ndarray, sr: int) -> np.ndarray:
    hop = _HOP * 8  # ~10 fps
    mag = np.abs(stft(mono, _WIN, hop))
    if mag.shape[0] == 0:
        return np.zeros((0, 16))
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    edges = np.logspace(np.log10(40), np.log10(sr / 2), 17)
    feats = np.stack(
        [mag[:, (freqs >= edges[i]) & (freqs < edges[i + 1])].mean(axis=1) for i in range(16)],
        axis=1,
    )
    feats = np.log1p(feats)
    return feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)


def structure(mono: np.ndarray, sr: int = SR) -> dict:
    feats = _frame_features(mono, sr)
    seconds = mono.size / sr
    if feats.shape[0] < 8:
        return {"sections": [{"start": 0.0, "end": round(seconds, 2), "label": "A"}], "count": 1}
    fps = feats.shape[0] / seconds
    novelty = np.linalg.norm(np.diff(feats, axis=0), axis=1)
    novelty = np.convolve(novelty, np.hanning(7) / np.hanning(7).sum(), mode="same")
    thr = novelty.mean() + novelty.std()
    bounds = [0]
    for i in range(2, len(novelty) - 2):
        if novelty[i] > thr and novelty[i] >= novelty[i - 1] and novelty[i] > novelty[i + 1]:
            if i - bounds[-1] > fps * 6:  # min 6s section
                bounds.append(i)
    bounds.append(len(feats))

    sigs: list[np.ndarray] = []
    labels: list[str] = []
    for a, b in zip(bounds[:-1], bounds[1:], strict=False):
        sig = feats[a:b].mean(axis=0)
        lab = None
        for j, prev in enumerate(sigs):
            cos = float(np.dot(sig, prev) / (np.linalg.norm(sig) * np.linalg.norm(prev) + 1e-9))
            if cos > 0.97:
                lab = labels[j]
                break
        if lab is None:
            lab = chr(ord("A") + len({*labels}))
        sigs.append(sig)
        labels.append(lab)
    sections = [
        {"start": round(a / fps, 2), "end": round(b / fps, 2), "label": lab}
        for a, b, lab in zip(bounds[:-1], bounds[1:], labels, strict=False)
    ]
    return {"sections": sections, "count": len(sections),
            "unique": sorted({s["label"] for s in sections})}


def embedding(mono: np.ndarray, sr: int = SR) -> list[float]:
    feats = _frame_features(mono, sr)
    if feats.shape[0] == 0:
        return [0.0] * 34
    vec = np.concatenate([feats.mean(axis=0), feats.std(axis=0)])
    spec = np.abs(stft(mono, _WIN, _HOP)).mean(axis=0)
    freqs = np.fft.rfftfreq(_WIN, 1.0 / sr)
    centroid = float((spec * freqs).sum() / (spec.sum() + 1e-9)) / (sr / 2)
    zcr = float(np.mean(np.abs(np.diff(np.sign(mono))) > 0))
    return [round(float(v), 4) for v in [*vec, centroid, zcr]]


def analyze(mono: np.ndarray, sr: int = SR) -> dict:
    return {
        "bpm": estimate_bpm(mono, sr),
        "key": estimate_key(mono, sr),
        "tuning": estimate_tuning(mono, sr),
        "loudness_dbfs": loudness_dbfs(mono),
        "energy_curve": energy_curve(mono, sr),
        "structure": structure(mono, sr),
        "embedding": embedding(mono, sr),
        "duration": round(mono.size / sr, 3),
    }
