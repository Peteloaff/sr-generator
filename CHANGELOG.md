# Changelog

## Music player, vocalists from a song, Jobs page removed — 2026-09-09

### Added
- **Now-playing bar** (`components/NowPlaying.tsx` + `lib/player.ts`) — a fixed
  player at the bottom. Hit ▶ on any finished song (Home or Songs page) and it
  loads there and keeps playing as you move around the app. Prev/next when a
  queue is set; the current song is remembered across a full reload
  (localStorage).
- **Train a vocalist from a full song.** `singer_song` sample type: on train,
  the vocal is separated (same multistem provider as players) and used.
  `SingerCard` gains an "upload a song" button; **`POST /singers/from-song`**
  (multipart file + name) creates the singer and trains it in one shot; the Band
  page has an "…or from a song" form. `tests/test_singer_from_song.py`
  (188 tests).

### Fixed
- **`musicgen._hat` returned a length-12 buffer when asked for < 12 samples**
  (`np.convolve` `same` mode grows the array), which crashed full-song
  generation when a hi-hat landed 1–11 samples from a section boundary — more
  likely since the Stage 14 swing offset. Guarded + the call site clips.

### Removed
- The **Jobs** page and its nav link (job status is surfaced inline where it
  matters; the `/jobs` API stays for polling).

## Per-singer volume & pan in the Vocal Director — 2026-09-08

Each singer in a vocal role now has a **vol** (−18…+6 dB) and **pan** (L↔R)
slider next to its take-allocation %. They commit on release and feed straight
into the render (`layering.py` already passed `gain_db` / `pan` through to the
take specs — this just exposes them). The Help page gained a "Vocal arrangement
& mix" step covering roles, ensembles, harmony intervals, and the mix controls.

## [Stage 19] Signature style presets + Help + band identity — 2026-09-08

### Added
- **`sr/common/player_presets.py`** — 45 built-in signature playing styles: every
  instrument (lead / rhythm guitar, bass, drums, keys) × 9 vibes (acoustic,
  clean, blues, indie, classic rock, hard rock, metal, **modern metal**, doom).
  Style archetypes, not anyone's recordings.
- **`GET /players/presets`**, **`POST /players/from-preset`** (drops in a
  ready-to-use player, consent + trained status set), **`POST
  /players/{id}/apply-preset`** (an existing player adopts a style).
- Web: a **Signature players** picker on the Band page; a **Help** page
  (`/help`, linked in the nav and from the Band page) with a 7-step walkthrough.
- **`BandIdentity`** on the Band page — rename the current band, spin up a new
  one, switch between them; makes it clear each band saves its own line-up.
- Responsive polish (help layout, chips, band controls on phones).
- `scripts/stage_gate.py 19`; `tests/test_player_presets.py` (185 tests).

## [Stage 18] Band lineup + one-click casting — 2026-09-08

Assemble singers + players into a band and cast them onto a song in one click.

### Added
- **`GET /bands/{id}/lineup`** — the whole roster: vocalists + players by
  instrument, with fill status.
- **`POST /songs/{id}/cast-band`** — puts the band's go-to player (most-trained,
  consenting) on every instrument slot, then runs the Stage 10 vocal arranger.
  Individual per-part / per-section casting still overrides it.
- Web: a **`/band` page** (unified "Your Band" — lineup summary + all singer &
  player cards) and a **"Cast the whole band"** button in the Cast step. Nav
  consolidated (`Singers` + `Players` → `Band`).
- `scripts/stage_gate.py 18`; `tests/test_band_casting.py`.

### Changed
- **Demucs installs on first use**, not bundled. The desktop app sets
  `SR_AUTO_INSTALL_SEPARATION=1`; `sr/common/deps.py` pip-installs `demucs` into
  `~/.sr-generator/pydeps` the first time a player is trained (needs a system
  Python). Falls back to a clear error / `bandsplit` otherwise.
  `tests/test_deps.py` (179 tests total).

## [Stage 17] Google Drive folder source — 2026-09-07

Pull reference songs and player training material from a Google Drive folder,
not just the local disk.

### Added
- **`sr/services/drive.py`** — no OAuth: share a Drive folder as "anyone with
  the link", set `SR_GOOGLE_API_KEY`, and it lists + downloads the audio via the
  public Drive v3 REST API (stdlib only). Recurses subfolders; filters to
  supported audio types; clear error when the key or a valid folder link is
  missing.
- **`POST /bands/{id}/references/import-drive`** — same `import_folder` job,
  Drive-backed (`source: "drive"`). `import_folder` refactored to a shared
  ingest loop over local-path *or* Drive.
- **`POST /players/{id}/samples/import-drive`** — pull a player's training songs
  from a Drive folder.
- Web: a "Google Drive folder link" input on the Band DNA page and on each
  `PlayerCard`.
- `scripts/stage_gate.py 17`; `tests/test_drive.py` (5 tests, 172 total).

## [Stage 16] Web UI for players, genre & casting — 2026-09-07

Stages 12-15 are now usable from the app.

### Added
- **Players page** (`/players`) + **`PlayerCard`** — add a player (name +
  instrument), upload songs / record a part, learn style, consent toggles, and a
  "tune by hand" panel (drive / brightness / busyness / attack / sustain /
  swing). Grouped by instrument. Nav gained a **Players** link.
- **`GeneratePanel`** gained a **genre / feel** picker (from `/genres`) and a
  "how far toward the genre" blend slider; both persist on the song and pass
  into generation.
- **`InstrumentCast`** in the Cast step — one row per instrument with a player
  dropdown (filtered to that instrument), a mute toggle, and a "tweak" panel
  (explore knob + the five dials: sparser↔busier, darker↔brighter,
  softer↔harder, laid-back↔pushed, straight↔swung). Warns when a chosen player
  hasn't granted generation consent.
- `lib/api.ts`: `Player` / `StyleModel` / `Genre` / `InstrumentSlot` types and
  the `/players`, `/genres`, `/songs/{id}/instruments` methods; `Song` gained
  `genre` / `style_blend`.
- Verified end to end in a browser against a live API: create player, cast on a
  song, regenerate a section -> the render's `cast` names the player and the
  four instrument stems come out.

## [Stage 15] Instrument casting — 2026-09-07

Cast a trained player on each instrument, per song or per section; generation is
conditioned on their learned style; every instrument comes out as its own stem.

### Added
- **`InstrumentSlot`** (`sr/models/instrument_slot.py`, migration
  `d4b8f1907e63`) — `(song_id, section_id?, role, player_id, muted, gain_db,
  explore, dials_json)`. A `section_id` of NULL is the whole-song default; a
  section-scoped slot overrides it.
- **`sr/services/casting.py`** — resolves section -> role -> player -> *effective*
  style profile: learned style, then the slot's **dials** (busier / brighter /
  harder / push / swing, each -1..1), then the **explore** knob (0 = faithful,
  1 = wander), then gain / mute. Consent-gated (`consent_generation`).
- **`musicgen`** now takes `players={role: profile}` and returns per-part stems
  (`drums` / `bass` / `rhythm` / `lead`) that sum exactly to the mix. Each part
  is shaped by its player: drummer busyness/swing/dynamics, bassist
  drive/register/sustain, guitarist drive/brightness, lead density/tone.
- **`generate_instrumental`** writes `stem_drums` / `stem_bass` / `stem_rhythm` /
  `stem_lead` section assets (labelled with the player's name) alongside the
  summed `instrumental_bed`; `fullsong` concatenates them into song-level stems.
- **`GET/PUT/DELETE /songs/{id}/instruments`**; `genre` / `style_blend` also on
  the per-section generate-instrumental request.
- Fixed an `_adsr` edge case where a release longer than the note zeroed the
  envelope (surfaced by busier lead lines).
- `scripts/stage_gate.py 15`; `tests/test_casting.py` (6 tests, 167 total).

## [Stage 14] Genre / song feel — 2026-09-07

Play a song as metal, sludge metal, doom, punk, acoustic, folk, synthwave... —
a band-level style, blended with the band's own DNA (not a replacement for it).

### Added
- **`sr/common/genre.py`** — 22 genre presets, each a bundle of tempo range,
  mode, string tuning, section-length scale, structure bias, energy range,
  swing, chord-progression bias, and an instrumental character (drive /
  distortion, brightness, drum busyness, note sustain, sub weight).
- **`Song.genre` + `Song.style_blend`** (0 = play like the band's DNA, 1 = fully
  adopt the genre; default 0.6). Migration `c3a9e5b71d42`.
- **`musicgen`** now responds to `distortion` (harder waveshaping), `sustain`
  (longer notes/pads), `sub_weight` (heavier low end + octave-down bass),
  `swing` (late off-beats), `tuning_semitones` (detune everything), and a
  `progressions` allow-list.
- **`songplan.plan_song(genre=...)`** applies the tempo range, minor/major key
  bias, section-length scale, structure and energy clamps.
- **`blend_character()`** (`sr/services/music.py`) interpolates the genre feel
  with the band adapter's character by `style_blend`.
- **`GET /genres`** + `/genres/{id}`; `genre` / `style_blend` on song
  create/update and the full-song generate request.
- `scripts/stage_gate.py 14`; `tests/test_genre.py` (6 tests, 161 total).

## [Stage 13] Player style learning — 2026-09-07

Upload songs a player performed on; separate their instrument; learn the style.

### Added
- **`DemucsStemProvider`** (`sr/providers/multistem_demucs.py`) — 6-way
  separation via `htdemucs_6s` (drums / bass / guitar / keys / other / vocal).
  Lazy import; `shifts=0` so it is reproducible. New `[separation]` extra pulls
  `demucs`; weights download once on first use. `SR_MULTISTEM_PROVIDER=demucs`
  (default) or `bandsplit` (`BandSplitStemProvider`, rough, no deps — used by CI
  and as a fallback).
- **`sr/common/playerstyle.py`** — `StyleProfile` (drive, brightness, register,
  attack, sustain, note density, busyness, dynamics, syncopation, swing, low-end,
  stereo width) + a deterministic `analyze(stem, role, bpm)` and `blend()`. These
  are *tendencies*, not a recording.
- **`PlayerStyleProvider`** ABC + `LocalDspPlayerStyleProvider`; new provider
  kinds `multistem` + `playerstyle` in the registry.
- **`train_player`** job (`sr/services/player.py`) — separates each
  `player_sample`, keeps the player's instrument stem (stored as a `player_stem`
  asset with lineage), blends the per-song profiles, writes it to the Player.
- **`/players/{id}/samples`** + **`/players/{id}/style-model`** (`get` /
  `train` / manual `patch`) — mirrors the singer voice-model routes.
- `audio_assets.player_id` (migration `b2f1a6d34c07`); consent gate
  (`require_player_training` / `_generation`); `scripts/stage_gate.py 13`;
  `tests/test_player_style.py` (7 tests, 155 total).

## [Stage 12] Instrumentalist players roster — 2026-09-07

First slice of the "AI band members" epic: instrumentalists alongside singers.
Upcoming stages add style-learning from uploaded songs (Demucs separation), per-
section instrument casting, and generation conditioned on each player's profile.

### Added
- **`Player` model** (`sr/models/player.py`) — the instrument-side analogue of
  `Singer`: `band_id`, `name`, `role` (`lead_guitar` / `rhythm_guitar` / `bass`
  / `drums` / `keys`), a learned `style_profile_json`, `training_status`, an
  `intensity` bias, and the same consent flags (`consent_training` /
  `_generation` / `_commercial`) enforced before any training or render.
- **`/players` CRUD router** — band-scoped list (optional `?role=` filter),
  create (unique name per band, 409 on dup, 422 on bad role), get, patch,
  delete. `Band.players` relationship cascades on band delete.
- `PlayerRole` enum; `player_sample` / `player_stem` asset types; `train_player`
  job type (handler lands in Stage 13). `/bands/{id}/stats` now reports
  `players`.
- Migration `a1c7f4e02b19`; `scripts/stage_gate.py 12`; `tests/test_players.py`
  (6 tests, 149 total).

## [UX] Guided song workflow, redesign, and in-browser voice recording — 2026-09-01

The web app was a working but utilitarian set of CRUD tables. This pass makes it
a product: a guided path from "create a song" to a finished track, a modern
visual design, and the ability to sing into the app and use your own voice.

### Added
- **New design system** (`apps/web/app/globals.css`): dark theme with a real
  palette, type scale, `.card`/`.btn`/`.chip`/`.pill` components, a sticky
  translucent app bar, and a `.stepnav` component. Every existing page inherits
  it with no markup changes (tables, forms, `.row`, `.pill`, `.ab`, etc. all
  restyled in place).
- **Home page rewrite** — a hero, a "Create a song" card (title + style chips +
  free-text prompt) that creates the song and drops straight into its workspace,
  a card grid of existing songs, and a "Your band" strip.
- **Song workspace reorganized into three guided steps** (`Story → Cast → Studio`,
  `apps/web/app/songs/[id]/page.tsx`): Story (style prompt, lyrics, optional
  cover-a-recording, manual sections behind an "advanced" toggle) → Cast (band
  roster, auto-cast suggestions, per-section Vocal Director, per-line overrides)
  → Studio (song master/mix/stems, per-section render + Stage 9 surgical
  regeneration + Stage 11 morph). `GeneratePanel` and `ArrangerPanel` split out
  of the old combined `ComposePanel`.
- **`MicRecorder`** (`apps/web/components/MicRecorder.tsx`) — records from the
  browser microphone (`MediaRecorder`, opus/webm), shows a live level meter and
  timer, lets you preview and redo before committing a take. Self-contained;
  degrades to a clear error if the mic is unavailable or permission is denied.
- **`SingerCard`** — a singer as one card: voice status, consent toggles, the
  recorder, a file-upload fallback, train/retrain, and a collapsible manual
  tuning panel. Used on `/singers` and in the Cast step. Singers page gained a
  one-click **"Add your voice"** action (creates a singer named "Me").
- Recording feeds the existing Stage 3 singer voice-model pipeline directly
  (`POST /singers/{id}/samples` → `train_singer`) — a recorded voice is a normal
  reusable `Singer`, assignable to any role in any song, same as an uploaded one.
- **Backend**: `.webm` / `.mp4` / `.mkv` added to `SUPPORTED_SUFFIXES` so
  browser recordings (opus-in-webm) ingest through the existing ffmpeg pipeline
  with no new code path. `test_browser_recording_webm_is_accepted`.
- 1 new test (138 total); ruff clean; web build clean.

### Changed
- `Song` gains `prompt`/`lyrics` and `Job` gains `result_json` in the web API
  client types (already present on the backend; the UI just hadn't typed them).
  `api.createSong` accepts optional `prompt`/`lyrics`/`bpm`/`key`/`seed`.
- Removed `ComposePanel.tsx` and `VoiceModel.tsx` (superseded by `GeneratePanel`
  + `ArrangerPanel` and by `SingerCard`).

---

## [Stage 11] — Experimental Vocal Morph — 2026-09-01

Automated singer-to-singer transitions, behind an experimental flag, preview-only.

### Added
- **`SR_EXPERIMENTAL_MORPH`** (default `false`). Every `/morphs` route and
  `/sections/{id}/morphs` returns **403** while it is off; `GET /experimental`
  is an unauthenticated probe so the UI can hide the lane.
- **`VocalMorph`** model + `POST /sections/{id}/morphs`, `GET`, `DELETE`.
- **`POST /morphs/{id}/preview`** → `morph_preview` job (`sr/services/morph.py`):
  resolves both singers' section vocals (reusing the render engine's
  `_base_vocal`), crossfades them with a `linear` / `equal_power` / `scurve`
  weight envelope over `[start_frac, end_frac]`, and writes a `morph_preview`
  `AudioAsset`. Deterministic from the section seed.
- **Quality flags**: envelope-correlation of the two performances
  (`poor_alignment`), seam energy jump (`energy_jump`), gross pre-gain level
  (`clipping`) → `score` + `usable`. `POST /morphs/{id}/commit` returns **409**
  for an unusable morph. A morph never enters a section mix in this stage.
- **Web**: "Vocal morph (experimental)" lane in the section panel, only rendered
  when `/experimental` reports the flag on.
- 4 new tests (137 total); `stage_gate.py 11`.

---

## [Stage 10] — Intelligent Vocal Arranger — 2026-09-01

Recommends a full vocal map from singer metadata and section energy; never
clobbers manual work.

### Added
- `Singer` gains `range_low_midi`, `range_high_midi`, `preferred_roles`,
  `energy_fit`, `arranger_json` (user-entered, not measured).
- **`sr/services/arranger.py`** — per section: energy from the instrumental bed's
  loudness (section-type fallback), lyric density, then scored lead / double /
  harmony / background / gang recommendations, each with a `confidence` and a
  `rationale`.
- **`GET /songs/{id}/arrangement/recommend`** (pure preview) and
  **`POST /songs/{id}/arrangement/apply`** — a section that already has roles, or
  is locked, is **skipped** and listed in `skipped` unless `overwrite: true`.
- **Web**: "Auto arranger" panel — recommendation table + apply with an explicit
  "replace existing roles" checkbox; singer arranger-metadata editor.
- 3 new tests; `stage_gate.py 10`.

---

## [Stage 9] — Surgical Regeneration — 2026-09-01

Change one section, one layer, or one singer without disturbing the rest.

### Added
- **`SongSection.locked`** + **`SectionRevision`** history (kind / roles snapshot
  / render job id / `is_current`), written on every regeneration.
- **`POST /sections/{id}/regenerate`** (`regenerate_section` job) — full section
  re-render; other sections are untouched because section renders only ever write
  their own section's assets.
- **`POST /roles/{id}/regenerate`** (`regenerate_role` job) — re-renders the
  section but perturbs only the target role's plan seed
  (`render_section` gained `role_seed_salt`); every other role's stem is
  byte-identical. Optional single-role **singer swap**
  (`swap_from_singer_id` / `swap_to_singer_id`, consent-checked).
- **`GET /sections/{id}/revisions`**, **`POST /sections/{id}/rollback`** (restores
  a revision's role snapshot), **`POST /sections/{id}/lock`**. Locked sections
  return **423** from every regen route and are skipped by the arranger.
- **Web**: "Surgical regeneration" controls (lock, regenerate section, regenerate
  one layer, rollback) in the section panel.
- 5 new tests; `stage_gate.py 9`.

---

## [Stage 8] — Full Song Generator — 2026-09-01

A prompt becomes a complete, editable project - never a single opaque file.

### Added
- **`sr/services/songplan.py`** — deterministic planner: prompt (+ optional
  lyrics, Band DNA, seed) → a structure template, per-section bars / seconds /
  energy / key, a lyric-line distribution (provided lyrics or a seeded scaffold),
  and a default vocal arrangement. `GET /songs/{id}/plan` dry-runs it.
- **`sr/common/guide.py`** — a deterministic monophonic guide melody per section
  (outlines the key, contour follows section energy), fed to the Stage 3
  voice-conversion path.
- **`generate_full_song` job** (`sr/services/fullsong.py`, `POST /songs/{id}/generate`)
  — builds the sections / roles / lyric lines, then for each section generates an
  instrumental bed (Stage 7) + guide + a full layering render (Stages 2–4), and
  concatenates the section renders into song-level `stem_instrumental` /
  `vocal_bus` / `song_mix` / `song_master` (`AssetType.SONG_MASTER` added).
  Reproducible from a seed.
- **Web**: "Full song generator" panel on the song page.
- 6 new tests (`test_songplan.py` + `test_stage8.py`); `stage_gate.py 8`.

### Changed
- `render_section` accepts `role_seed_salt` (used by Stage 9).
- `JobType` gains `generate_song` / `regenerate_section` / `regenerate_role` /
  `morph_preview`.

---

## [Stage 7] — Band-Specific Music Generation — 2026-08-31

The approved Band DNA now conditions a generated instrumental bed per section,
tempo/key-locked to the song, that band vocals render over. The generator is a
deterministic synth engine standing in for a real model — the contract, jobs and
UI don't change when you swap it.

### Added
- **`MusicGenerationProvider` contract** — `generate(prompt, params, seed, adapter)
  -> MusicGeneration` and optional `train_adapter(manifest, dna, params)
  -> BandAdapterSpec`. `LocalSynthMusicProvider` (default, `local_synth`):
  `sr/common/musicgen.py` — a deterministic NumPy engine (kick/snare/hat off the
  requested BPM, a diatonic chord progression in the requested key, sub bass, pad
  stack, arp, tonic drone; ADSR, swing hint). `HttpMusicProvider` (`http` —
  `POST {SR_MUSIC_HTTP_URL}/generate` → WAV, `POST /train-adapter` → JSON spec).
  `MockMusicProvider` (near-silent noise, tests).
- **`BandAdapter`** (`sr/models/band_adapter.py`, band-scoped, unique per name) —
  `POST /bands/{id}/adapters/train` → `train_band_adapter` job builds the strict
  training manifest + `band_dna` and distils them into `{character: {brightness,
  drum_busy, drive}, tempo_prior, key_prior, energy_profile, trained_from}`,
  stored with the `dataset_version` it came from. `GET /bands/{id}/adapters`,
  `GET/DELETE /adapters/{id}`.
- **`generate_instrumental` job** — `POST /songs/{id}/sections/{sid}/generate-instrumental`
  `{prompt, seed, adapter_id, bpm, key, duration}`. Resolves tempo/key
  (request override > song > adapter prior), renders a section-length bed,
  deletes the section's prior `instrumental_bed` and writes the new one, so the
  Stage 2/3 render mixes band vocals over it. `GET .../generations`. Every applied
  value + child seed is in the job metadata; same seed → byte-identical WAV.
- `AssetType.GENERATED_INSTRUMENTAL`; `JobType` `train_band_adapter` /
  `generate_music`. `sr/common/analysis.estimate_bpm` reused to verify tempo-lock.
- **Web**: Band DNA page trains / lists / deletes adapters (character vector +
  `dataset_version` shown); section panel has an adapter picker + "Generate
  instrumental" with an inline player.
- 10 new tests (118 total); `stage_gate.py 7`.

### Changed
- `SR_MUSIC_PROVIDER` default `mock` → `local_synth`; added `SR_MUSIC_HTTP_URL`.
- `MusicGenerationProvider.generate` signature changed (returns `MusicGeneration`);
  the mock-generation job writes its placeholder WAV directly rather than through
  the music provider.

---

## [Stage 6] — Band DNA Analysis — 2026-08-31

Point at a folder → a structured, quality-checked catalogue → a reproducible
training manifest. No fine-tuning yet.

### Added
- **Folder import**: `POST /bands/{id}/references/import-folder` `{path, recursive,
  auto_approve}` → `import_folder` job that ingests every audio file as a
  `BandReference` (content-hash dedup), then analyses each. Plus
  `scripts/import_catalogue.py`. Single upload: `POST /bands/{id}/references`.
- **`LocalMirAnalysisProvider`** (`sr/common/analysis.py`, NumPy): BPM (onset
  autocorrelation), key (chroma → Krumhansl), tuning (pitch-peak deviation from
  A=440), energy curve, loudness, section structure (novelty on frame features),
  a 34-d spectral embedding. `MockAnalysisProvider`, `HttpAnalysisProvider`
  (`SR_ANALYSIS_HTTP_URL`). `dsp.stft`/`istft` reused.
- `BandReference` gains `duration`, `sample_rate`, `channels`, `content_hash`
  (unique per band), `source_kind`, `quality_json`, `analysis_status/provider/version`.
- **`sr/services/quality.py`** — clipping / silence / too-short / near-mono /
  low-loudness flags → score + pass/fail. `PATCH /references/{id}` refuses
  `approved_for_training` until `analysis_status == "ready"`.
- **Training manifest** (`sr/services/manifest.py`): `GET /bands/{id}/training-manifest`
  — every approved reference must have `bpm`/`key`/`tuning`/`duration` + ready
  analysis, else **409** with the incomplete list. `dataset_version` = deterministic
  hash of the included set. `POST` snapshots to `models/band/{id}/manifest_vN.json`.
  `GET .../completeness`.
- **`GET /bands/{id}/dna`** (`sr/services/dna.py`) — BPM/key/tuning distributions,
  tag cloud, mean embedding, mean energy profile, structure style.
- **Web**: `/references` Band DNA page.
- 14 new tests (107 total); `stage_gate.py 6`.

---

## [Stage 5] — Stem Separation + Song Editing — 2026-08-31

Import a cover, replace the vocal, keep the melody.

### Added
- **`StemSeparationProvider`** contract `separate(source_path) -> StemSeparation`
  (raw stereo stems). `CenterSplitStemProvider` (default — `sr/common/separation.py`,
  soft-mask center-channel extraction: mid/side STFT → per-bin vocal mask,
  `instrumental = mix - vocal`), `MockStemProvider`, `HttpStemProvider`
  (`SR_STEM_HTTP_URL` → a Demucs-class service).
- **`POST /songs/{id}/separate`** → `separate_stems` job → song-level
  `stem_lead_vocal` + `stem_instrumental` as versioned `AudioAsset`s
  (`parent_asset_id` = the upload; re-separate bumps `version`).
  `GET /songs/{id}/stems`.
- **`POST /songs/{id}/sections/{sid}/use-derived-stems`** — slices the separated
  vocal → the section's `guide_vocal` and the instrumental → `instrumental_bed`,
  so the existing Stage 3 conversion + Stage 2 mix take over.
- **`assemble_song` job** (`sr/services/assembly.py`) — starts from the original
  recording and splices in each rendered section (`vocal_bus` over the derived
  instrumental, ~12 ms crossfades). Untouched time ranges are copied verbatim →
  **byte-identical outside the replaced windows**. Versioned `song_mix` asset.
  `POST /songs/{id}/assemble`, `GET /songs/{id}/mixes`.
- `dsp.stft` / `dsp.istft` (public); `AssetType.SONG_MIX`.
- **Web**: Cover Studio panel (Separate stems / Assemble full mix + stem players);
  per-section "Use separated stems" button.
- 6 new tests (98 total); `stage_gate.py 5`.

---

## [Stage 4] — Vocal-Stack Quality — 2026-08-31

Stacks now sound produced, not copied.

### Added
- **Harmony intervals**: `VocalAssignment.interval_semitones` — a harmony singer
  at `+3`/`+7`, an octave double at `-12`. Layered into the take pitch alongside
  detune + jitter; kept even in `flat` mode (it's arrangement, not production).
- **`sr/common/vocalfx.py`**: de-esser (dynamic HF duck), full-signal FFT EQ
  (two shelves + presence bell), soft-knee compressor, `stack_gain(n)=1/√n`
  compensation, and A/B metrics (`stereo_correlation`, `width_ratio`,
  `mono_compat`). A per-role chain lives in `VocalRole.processing_json` and runs
  on the summed role stem.
- **`VocalPreset`** (band-scoped): capture a section's roles (singers by name +
  weight + interval + mix + processing), apply to any section.
  `POST/GET/DELETE /vocal-presets`, `POST /vocal-presets/{id}/apply`.
- **A/B render**: `RenderRequest.mode` (`ensemble` default / `flat`).
  `POST /songs/{id}/sections/{sid}/ab` renders both and returns a verdict —
  ensemble measurably wider, less L-R correlated, no phase collapse.
- `GenerationJob.result_json` persists a job's result metadata (incl. A/B
  numbers).
- **Web**: interval field per harmony/double singer; per-role fx chain editor;
  ensemble size/width inline; "Save section as preset" / "Apply preset";
  "Render A/B" with the width/correlation table and both masters.
- 13 new tests (92 total); `stage_gate.py 4`.

### Fixed
- `plan_role_takes` local `flat` list shadowed the new `flat` parameter — would
  have disabled all humanisation. Renamed to `take_order`.

---

## [Stage 3] — Singing Voice Provider — 2026-08-31

A guide vocal is now converted into each singer's voice. The conversion is real
DSP (dependency-free); a neural model implements the same contract.

### Added
- **`VoiceProvider` contract** (`analyze(samples)` + `convert(guide, profile,
  seed)`). Implementations: `LocalDspVoiceProvider` (default — pitch to register,
  STFT formant warp, spectral tilt, breath, drive), `MockVoiceProvider` (fast
  detune, tests), `HttpVoiceProvider` (POSTs to `SR_VOICE_HTTP_URL` — a local or
  remote GPU model service).
- **`sr/common/voice.py`**: `estimate_f0`, `analyze` → `VoiceProfile`
  (median_f0 / formant / brightness / breathiness / roughness), `convert`.
- **Singer voice model**: `Singer.voice_profile_json`; `POST /singers/{id}/samples`,
  `train_singer` job (analyses samples → profile → `training_status=ready`),
  `GET/PATCH /singers/{id}/voice-model` (manual tuning).
- **Guide vocal**: `POST /songs/{id}/sections/{sid}/guide`. Render resolution
  order per singer: uploaded take → guide + ready voice model (converted, cached)
  → deterministic placeholder.
- **Consent enforcement** (`sr/services/consent.py`): render is **403** if any
  assigned singer lacks `consent_generation`; `train_singer` fails without
  `consent_training`. Enforced at the API and again in the job.
- **`RenderCache`** — voice conversions are filesystem-addressed (`cache/…`),
  written before the render commits, so a retry after a rollback reuses them.
- **Job progress** — `job.progress` advances through a render.
- **Web**: singer voice-model panel (samples, train, profile sliders); section
  guide-vocal upload; take breakdown shows `source: converted`.
- 15 new tests (79 total); `stage_gate.py 3`.

### Changed
- `VoiceProvider.render()` replaced by `analyze()` + `convert()`.
- `run_job` progress/cache use the handler's own session (SQLite single-writer
  cannot grant a concurrent write transaction).
- `render_voice` job type removed (voice rendering happens inside `render_section`).
- `dsp._resample` → `dsp.resample` (public). Default `SR_VOICE_PROVIDER=local_dsp`.

---

## [Stage 2] — Audio Layering Engine — 2026-08-31

The Vocal Director's definitions now render into real, humanized, mixed audio.
Still no AI models: source vocals are uploaded takes or deterministic
placeholders.

### Added
- **Micro-variation engine** (`sr/services/layering.py`): `plan_role_takes(role,
  seed)` → one `TakeSpec` per virtual performance, with largest-remainder
  allocation and bounded timing/pitch/formant/gain/pan variation from per-take
  child seeds, plus deterministic stereo spread from `role.width`.
- **`RenderTake` model**: every take's child seed and applied variation values,
  with source + output asset links — a render can be reconstructed take-for-take.
- **DSP** (`sr/common/dsp.py`, pure NumPy): gain, equal-power pan,
  sample-accurate timing offset, resample-based pitch shift, spectral-tilt
  formant, sum/normalize. **Synth** (`sr/common/synth.py`): distinct deterministic
  placeholder vocal per singer.
- **`render_section` job** (`sr/services/render.py`): take stems → role stems →
  grouped stems (`stem_lead_vocal` / `stem_background_vocal` / `stem_gang_vocal`)
  → `vocal_bus` → `mix` (+ optional instrumental) → `master`. Every artifact is an
  `AudioAsset` with parent/job lineage; the whole render is one transaction.
- **API**: `POST /songs/{id}/sections/{sid}/takes` (source take per singer),
  `.../instrumental`, `.../render`, `GET .../renders`, `GET .../renders/{job}/takes`,
  `GET /songs/{id}/assets/{aid}/download` (WAV export).
- `AudioAsset` gains `singer_id` and `label`.
- **Web**: per-section render panel — upload takes, "Render section", inline stem
  players + downloads, and the take-by-take variation breakdown.
- 16 new tests (64 total); `stage_gate.py 2`.

### Changed
- Job handlers now take `(job, db)`; `run_job` uses three transactions so a failed
  render still records its attempt + error.
- `derive_seed` masked to 63 bits (fits signed BIGINT / numpy int64 everywhere).
- A stale `X-Band-Id` header falls back to the default band (an explicit
  `?band_id=` still 404s).

---

## [Stage 1] — Singer Library + Song Workspace — 2026-08-31

Still no AI models — mock providers only. The app is now useful for directing
vocals on existing audio.

### Added
- **`Band` entity** — `Singer` / `Project` / `Song` / `BandReference` are scoped
  by `band_id`; default band auto-created; active band via `?band_id=`,
  `X-Band-Id` header, or default. Singer names unique per band. (`/bands` CRUD +
  `/bands/{id}/stats`.)
- **Audio pipeline** (`sr/common/audio.py`) using ffmpeg bundled with
  `imageio-ffmpeg`: probe duration/SR/channels, transcode to canonical WAV,
  downsampled waveform peaks. `POST /songs/{id}/audio` (wav/mp3/flac/m4a/ogg/…),
  `GET /songs/{id}/assets/{id}/waveform`.
- **Section editing**: `PATCH` section, `PUT /sections/reorder`.
- **Lyric-line editing**: `PATCH` line, `PUT /songs/{id}/lines` (rebuild from a
  text block).
- **Vocal Director API** (`sr/api/routers/vocal.py`): vocal role + assignment
  CRUD on sections and lines; `GET /roles/{id}/normalized` returns the
  100%-scaled split and the largest-remainder ensemble take counts
  (70/20/10 @ 10 → 7/2/1). Cross-band singer assignments rejected.
- **Project export / import** (`sr/services/project_io.py`): portable JSON
  snapshot (sections, lines, roles, weights, seeds, gains, pans, humanization),
  singers referenced by name. Importing into another band recreates placeholder
  singers (consent flags false).
- **Web workspace**: band switcher; song page with audio upload, SVG waveform +
  section overlays, section table (type/name/times/reorder), lyrics editor,
  per-section and per-line Vocal Director panels with live take counts; projects
  page with export download / import upload.
- Migrations squashed to one `initial schema (through stage 1)` revision
  (ADR-0008).
- 19 new tests (48 total); `stage_gate.py 1`.

### Changed
- `SingerCreate` accepts optional `band_id`; all list/create endpoints are
  band-scoped. Non-existent nested ids now return 404 (was 422 in one case).

---

## [Stage 0] — Foundation & Architecture — 2026-08-31

Initial skeleton. No AI models — mock providers only.

### Added
- FastAPI backend with CRUD for singers, projects, songs, sections, lyric lines,
  and jobs; `/health` and OpenAPI docs at `/docs`.
- SQLAlchemy 2.0 ORM + Alembic migration for all core entities: Singer, Project,
  Song, SongSection, LyricLine, VocalRole, VocalAssignment, BandReference,
  GenerationJob, AudioAsset.
- `LyricLine` entity and section/line vocal-role resolution
  (`sr/common/resolver.py`) — the per-line singer-assignment amendment.
- Job system: `JobQueue` abstraction with `eager` / `inline` / `rq` backends,
  shared `run_job` runner capturing seed, params, provider version, input asset
  ids, logs, error, attempts, timing, and output assets with lineage.
- Provider ABCs (music / voice / stem / analysis / mastering / transcription),
  mock implementations that emit real silent WAVs, and a config-driven registry.
- `sr/common/allocation.py` — deterministic largest-remainder allocation +
  percentage normalization (70/20/10 @ 10 → 7/2/1).
- `sr/common/seeds.py` — blake2b child-seed derivation + bounded jitter.
- `sr/common/storage.py` — local filesystem store with an S3-shaped interface.
- `sr/orchestrator/pipeline.py` — generation stage graph + dry-run planner.
- Next.js app: home/health, singers, songs, jobs pages talking to the API.
- Scripts: `setup.ps1`, `dev.ps1`, `worker.ps1`, `test.ps1`, `stage_gate.py`.
- Optional `docker-compose.yml` (Postgres + Redis + api + worker + web).
- Docs: README, ARCHITECTURE, ROADMAP, MODEL_SETUP, DATASET_GUIDE, TEST_PLAN,
  DECISIONS, CHANGELOG.
- 29 automated tests (ruff clean).

### Stage 0 exit criteria — all PASS
- Stack boots locally · CRUD for singers/projects/songs · mock generation job
  queued → completed with lineage · test suite passes.
