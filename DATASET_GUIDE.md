# Dataset & Consent Guide

Nothing here is used for training in Stage 0. This documents the requirements
that Stages 1, 3, and 6 will enforce.

## Singer voice samples (Stage 3+)

Per authorized singer:

- Dry, close-mic, mono, 24-bit / 44.1 kHz or better.
- Clean and (if applicable) scream samples kept **separate**.
- Varied pitch across the singer's comfortable range; varied dynamics.
- No effects, no bleed, no other voices.
- Consistent mic/room where possible.
- Target quantity is provider-dependent; record more than you think you need.

**Never** combine multiple singers into one model. One model per identity.

## Reference / catalogue songs (Band DNA — Stage 6)

Per `BandReference`:

- Prefer **stems** (cleaner instrumental examples); full mixes are still useful
  for structure and sonic reference.
- Fill in BPM, key, time signature, tuning, structure, instrumentation, tags.
- `approved_for_training` defaults **false**. An upload is reference data until a
  human explicitly approves it as training data.
- Poor-quality material stays out of training even if approved — quality checks
  gate the dataset manifest.

## Consent & governance (enforced from Stage 1 data, Stage 3 behaviour)

Each `Singer` carries:

| Flag | Blocks when false |
|---|---|
| `consent_training` | any training job for that singer |
| `consent_generation` | any voice render as that singer |
| `consent_commercial` | commercial-use export paths |
| `consent_version` | — (records which authorization applies) |
| `consent_source_ref` | — (pointer to the signed document) |

- Generation can be disabled for a singer **without deleting** historical
  project data (`training_status = disabled`).
- Every training/generation job records the singer's consent state at run time.

## Dataset manifests (Stage 6)

Each training run produces a reproducible manifest: dataset version, included
asset ids + versions, provider + version, preprocessing parameters, and a
content hash. Rollback = re-run from a prior manifest.
