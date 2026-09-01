"""Stage 8 - full song generator.

Executes a deterministic song plan against the existing section + Vocal Director
machinery: build the structure, arrange singers, generate a per-section
instrumental bed and guide melody, render each section with the layering engine,
then concatenate the section renders into song-level stems + a master.

The output is a full editable project, never a single opaque file: every section,
role, take, stem and the song master are individual AudioAssets with lineage, and
any one section can be regenerated on its own afterwards (Stage 9).
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.common import dsp, guide
from sr.common.seeds import derive_seed
from sr.common.storage import get_storage
from sr.models.audio_asset import AudioAsset
from sr.models.band import Band
from sr.models.band_adapter import BandAdapter
from sr.models.generation_job import GenerationJob
from sr.models.singer import Singer
from sr.models.song import LyricLine, Song, SongSection
from sr.models.vocal import VocalAssignment, VocalRole
from sr.providers.base import ProviderResult
from sr.services import songplan
from sr.services.dna import band_dna
from sr.services.music import generate_instrumental
from sr.services.render import render_section
from sr.worker.progress import report as report_progress

PLANNER = "song-planner"
PLANNER_VERSION = "songgen-0.8.0"
_XFADE = 0.012

_ROLE_FIELDS = (
    "role_type", "ensemble_size", "width",
    "humanize_timing_ms", "humanize_pitch_cents", "humanize_formant",
)
_ASSIGN_FIELDS = (
    "singer_id", "weight_percent", "gain_db", "pan",
    "interval_semitones", "pitch_offset_semitones", "timing_offset_ms", "formant_shift",
)


def _clear_structure(db: Session, song: Song) -> None:
    for line in list(song.lyric_lines):
        db.delete(line)
    for section in list(song.sections):
        db.delete(section)
    db.flush()


def _write_guide(
    db: Session, song: Song, section: SongSection, *, key: str, bpm: float,
    seconds: float, seed: int, energy: float, job_id: str,
) -> AudioAsset:
    storage = get_storage()
    mono = guide.generate_guide(
        key=key, bpm=bpm, seconds=seconds, seed=seed, energy=energy
    )
    stereo = np.stack([mono, mono], axis=1).astype(np.float32)
    base = f"references/{song.band_id}/{song.id}/{section.id}/guide"
    key_path = f"{base}/canonical.wav"
    dsp.save_wav(storage.path_for(key_path), stereo, dsp.SR)
    for old in db.scalars(
        select(AudioAsset).where(
            AudioAsset.section_id == section.id, AudioAsset.asset_type == "guide_vocal"
        )
    ):
        db.delete(old)
    db.flush()
    asset = AudioAsset(
        song_id=song.id, section_id=section.id, generation_job_id=job_id,
        asset_type="guide_vocal", file_path=key_path, label="generated guide melody",
        sample_rate=dsp.SR, channels=2, duration=round(len(mono) / dsp.SR, 3),
    )
    db.add(asset)
    db.flush()
    return asset


def _section_piece(
    db: Session, job_id: str, section_id: str, asset_type: str, n: int
) -> np.ndarray:
    asset = db.scalar(
        select(AudioAsset).where(
            AudioAsset.generation_job_id == job_id,
            AudioAsset.section_id == section_id,
            AudioAsset.asset_type == asset_type,
        )
    )
    if asset is None:
        return np.zeros((n, 2), dtype=np.float32)
    return dsp.fit_length(dsp.load_stereo(get_storage().path_for(asset.file_path)), n)


def _concat(pieces: list[np.ndarray]) -> np.ndarray:
    if not pieces:
        return np.zeros((1, 2), dtype=np.float32)
    xf = int(_XFADE * dsp.SR)
    out = pieces[0]
    for piece in pieces[1:]:
        if xf and out.shape[0] >= xf and piece.shape[0] >= xf:
            ramp = np.linspace(0.0, 1.0, xf, dtype=np.float32)[:, None]
            head = out[-xf:] * (1 - ramp) + piece[:xf] * ramp
            out = np.concatenate([out[:-xf], head, piece[xf:]], axis=0)
        else:
            out = np.concatenate([out, piece], axis=0)
    return out.astype(np.float32)


def generate_full_song(
    db: Session, job: GenerationJob, *, song_id: str, seed: int, params: dict
) -> ProviderResult:
    song = db.get(Song, song_id)
    if song is None:
        raise LookupError(f"song {song_id} not found")

    prompt = str(params.get("prompt") or song.prompt or song.title)
    lyrics = params.get("lyrics") if params.get("lyrics") is not None else song.lyrics
    adapter_id = params.get("adapter_id")
    if adapter_id:
        adapter = db.get(BandAdapter, adapter_id)
        if adapter is None or adapter.band_id != song.band_id:
            raise ValueError("adapter not found for this band")

    dna = band_dna(db, db.get(Band, song.band_id))
    plan = songplan.plan_song(
        prompt=prompt, lyrics=lyrics, bpm=song.bpm, seed=seed, dna=dna,
        section_seconds=params.get("section_seconds"),
        structure=params.get("structure"),
    )

    report_progress(db, job, 0.05, f"planned {len(plan['sections'])} sections")
    if params.get("replace", True):
        _clear_structure(db, song)

    song.prompt = prompt
    song.lyrics = lyrics
    song.bpm = plan["bpm"]
    song.key = plan["key"]
    song.seed = seed
    song.duration = plan["duration"]
    song.status = "generating"
    db.flush()

    singers = list(db.scalars(select(Singer).where(Singer.band_id == song.band_id)))
    section_rows: list[SongSection] = []
    for idx, sec in enumerate(plan["sections"]):
        row = SongSection(
            song_id=song_id, section_type=sec["type"], name=sec.get("name"),
            start_time=sec["start"], end_time=sec["end"], order_index=idx,
            generation_seed=derive_seed(seed, "section", idx),
        )
        db.add(row)
        db.flush()
        section_rows.append(row)
        for rspec in songplan.default_arrangement(sec, singers, idx, seed):
            role = VocalRole(
                section_id=row.id,
                **{f: rspec[f] for f in _ROLE_FIELDS if f in rspec},
            )
            for a in rspec.get("assignments", []):
                role.assignments.append(
                    VocalAssignment(**{f: a[f] for f in _ASSIGN_FIELDS if f in a})
                )
            db.add(role)
    db.flush()

    for ln in plan["lyric_lines"]:
        db.add(LyricLine(
            song_id=song_id,
            section_id=section_rows[ln["section"]].id if ln["section"] is not None else None,
            order_index=ln["order"], text=ln["text"],
        ))
    db.flush()

    rendered: list[str] = []
    errors: list[str] = []
    for idx, (row, sec) in enumerate(zip(section_rows, plan["sections"], strict=True)):
        frac = 0.1 + 0.7 * idx / len(section_rows)
        report_progress(db, job, frac, f"section {idx + 1}/{len(section_rows)} ({sec['type']})")
        seconds = sec["seconds"]

        generate_instrumental(
            db, job, section_id=row.id, seed=derive_seed(seed, "instr", idx),
            params={
                "adapter_id": adapter_id, "duration": seconds,
                "prompt": f"{sec['type']} - {prompt}",
                "energy_curve": [max(0.2, sec["energy"] - 0.15), sec["energy"], sec["energy"]],
            },
        )
        _write_guide(
            db, song, row, key=song.key, bpm=song.bpm, seconds=seconds,
            seed=derive_seed(seed, "guide", idx), energy=sec["energy"], job_id=job.id,
        )

        if any(r.assignments for r in row.vocal_roles):
            try:
                render_section(
                    db, job, section_id=row.id,
                    seed=derive_seed(seed, "render", idx),
                    params={"duration": seconds},
                )
                rendered.append(row.id)
            except Exception as exc:  # noqa: BLE001 - one bad section must not kill the song
                errors.append(f"{sec['type']} #{idx}: {exc}")

    if not rendered and not errors:
        # no consenting singers anywhere - still a valid instrumental project
        pass

    report_progress(db, job, 0.85, "assembling song stems")
    storage = get_storage()
    base = f"songs/{song_id[:8]}/{job.id[:8]}"
    mix_pieces, vox_pieces, instr_pieces = [], [], []
    for row, sec in zip(section_rows, plan["sections"], strict=True):
        n = max(1, int(sec["seconds"] * dsp.SR))
        instr = _section_piece(db, job.id, row.id, "instrumental_bed", n)
        # instrumental_bed asset stores its file under .../instrumental/canonical.wav
        instr_pieces.append(instr)
        vox = _section_piece(db, job.id, row.id, "vocal_bus", n)
        vox_pieces.append(vox)
        mix = _section_piece(db, job.id, row.id, "mix", n)
        if not mix.any():
            mix = instr
        mix_pieces.append(mix)

    def _emit(
        asset_type: str, audio: np.ndarray, label: str, *, master: bool = False
    ) -> AudioAsset:
        arr = audio
        if master:
            arr, _ = dsp.peak_normalize(arr, ceiling=0.95)
        key = f"{base}/{asset_type}.wav"
        dsp.save_wav(storage.path_for(key), arr, dsp.SR)
        a = AudioAsset(
            song_id=song_id, generation_job_id=job.id, asset_type=asset_type,
            file_path=key, label=label, sample_rate=dsp.SR, channels=2,
            duration=round(arr.shape[0] / dsp.SR, 3),
        )
        db.add(a)
        db.flush()
        return a

    song_instr = _concat(instr_pieces)
    song_vox = _concat(vox_pieces)
    song_mix = _concat(mix_pieces)
    _emit("stem_instrumental", song_instr, "full-song instrumental")
    _emit("vocal_bus", song_vox, "full-song vocals")
    mix_asset = _emit("song_mix", song_mix, f"full-song mix ({len(plan['sections'])} sections)")
    master_asset = _emit("song_master", song_mix, "full-song master", master=True)
    mix_asset.parent_asset_id = master_asset.id

    song.status = "ready"
    song.duration = round(song_mix.shape[0] / dsp.SR, 3)
    db.flush()

    return ProviderResult(
        provider=PLANNER,
        provider_version=PLANNER_VERSION,
        outputs=[],
        metadata={
            "song_id": song_id, "seed": seed, "plan": plan,
            "sections_created": len(section_rows),
            "sections_rendered": len(rendered),
            "section_errors": errors,
            "song_mix_asset_id": mix_asset.id,
            "song_master_asset_id": master_asset.id,
            "lyrics_source": plan["lyrics_source"],
        },
        logs=[
            f"planned {len(section_rows)} sections ({'-'.join(plan['template'])})",
            f"rendered {len(rendered)} section(s), {len(errors)} error(s)",
            f"song master -> {master_asset.file_path}",
            *(f"  ! {e}" for e in errors),
        ],
    )
