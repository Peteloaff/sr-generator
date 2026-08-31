"""Import a folder of audio as Band DNA reference songs, and analyse them.

  python scripts/import_catalogue.py "D:/music/my band" [--band SLUG] [--flat] [--approve]

Runs in-process against SR_DATABASE_URL / SR_STORAGE_ROOT (your .env). No server
needed. Prints a summary and the training-manifest completeness report.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--band", default="default", help="band slug (default: 'default')")
    ap.add_argument("--flat", action="store_true", help="do not recurse into subfolders")
    ap.add_argument("--approve", action="store_true", help="auto-approve clean tracks for training")
    args = ap.parse_args()

    from sqlalchemy import select

    from sr.bootstrap import ensure_default_band
    from sr.db import session_scope
    from sr.models.band import Band
    from sr.models.generation_job import GenerationJob
    from sr.services.manifest import completeness_report
    from sr.services.references import import_folder

    with session_scope() as db:
        ensure_default_band(db)
        band = db.scalar(select(Band).where(Band.slug == args.band)) or ensure_default_band(db)
        job = GenerationJob(job_type="import_folder", provider="catalogue-import", status="running")
        db.add(job)
        db.flush()
        summary = import_folder(
            db, job, band_id=band.id,
            params={
                "path": args.folder,
                "recursive": not args.flat,
                "auto_approve": args.approve,
            },
        )
        job.status = "succeeded"
        report = completeness_report(db, band)

    print(f"\nband: {band.name} ({band.slug})")
    print(f"scanned {summary['scanned']}  created {summary['created']}  "
          f"duplicates {summary['skipped_duplicates']}  failed {summary['failed']}")
    if report:
        print(f"\n{len(report)} approved reference(s) still missing metadata:")
        for r in report:
            print(f"  - {r['title']}: {', '.join(r['missing'])}")
    print("\nnext: review + approve in the app, then POST /bands/<id>/training-manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
