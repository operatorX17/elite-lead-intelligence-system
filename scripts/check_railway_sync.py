#!/usr/bin/env python3
"""Fail if .railway-backend-deploy/src has drifted from src/.

The Railway deployment ships from `.railway-backend-deploy/`, but the canonical
code lives under `src/`. Whenever a fix is made in one tree but not the other,
the deployed backend silently runs a stale copy and we hit ghost bugs like
`name 'rating' is not defined` long after the fix is "merged".

This script:
  * compares every Python file under both trees,
  * exits 0 if they are byte-identical,
  * exits 1 and prints a unified diff if any file has drifted,
  * exits 2 if a file exists in one tree but not the other.

Use it as a pre-commit hook, a `make sync-check` target, and a CI gate.
Run `python scripts/check_railway_sync.py --fix` to copy `src/` over
`.railway-backend-deploy/src/` and resync the deploy tree in one shot.
"""
from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TREE = REPO_ROOT / "src"
DEPLOY_TREE = REPO_ROOT / ".railway-backend-deploy" / "src"


def gather(root: Path) -> dict[Path, Path]:
    return {p.relative_to(root): p for p in root.rglob("*.py")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Sync .railway-backend-deploy/src from src/ instead of failing.",
    )
    args = parser.parse_args()

    if not SOURCE_TREE.exists() or not DEPLOY_TREE.exists():
        print(f"missing tree: source={SOURCE_TREE.exists()} deploy={DEPLOY_TREE.exists()}", file=sys.stderr)
        return 2

    source_files = gather(SOURCE_TREE)
    deploy_files = gather(DEPLOY_TREE)

    drift: list[str] = []
    missing_in_deploy = sorted(set(source_files) - set(deploy_files))
    missing_in_source = sorted(set(deploy_files) - set(source_files))

    for rel in sorted(set(source_files) & set(deploy_files)):
        a = source_files[rel].read_bytes()
        b = deploy_files[rel].read_bytes()
        if a != b:
            drift.append(str(rel))

    if args.fix:
        if missing_in_source:
            for rel in missing_in_source:
                target = DEPLOY_TREE / rel
                print(f"removing extra deploy file: {rel}")
                target.unlink()
        for rel in missing_in_deploy:
            src = source_files[rel]
            dst = DEPLOY_TREE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"added: {rel}")
        for rel in drift:
            shutil.copy2(source_files[rel], deploy_files[rel])
            print(f"synced: {rel}")
        print("railway deploy tree resynced from src/")
        return 0

    if not drift and not missing_in_deploy and not missing_in_source:
        print("OK: src/ and .railway-backend-deploy/src/ are in sync")
        return 0

    if missing_in_deploy:
        print("Files present in src/ but missing from .railway-backend-deploy/src/:", file=sys.stderr)
        for rel in missing_in_deploy:
            print(f"  - {rel}", file=sys.stderr)
    if missing_in_source:
        print("Files present in .railway-backend-deploy/src/ but missing from src/:", file=sys.stderr)
        for rel in missing_in_source:
            print(f"  - {rel}", file=sys.stderr)
    if drift:
        print("Drifted files (deploy tree differs from src/):", file=sys.stderr)
        for rel in drift:
            print(f"  - {rel}", file=sys.stderr)
            a = (SOURCE_TREE / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            b = (DEPLOY_TREE / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            diff = list(difflib.unified_diff(a, b, fromfile=f"src/{rel}", tofile=f".railway-backend-deploy/src/{rel}", lineterm=""))
            for line in diff[:200]:
                print(line, file=sys.stderr)
            if len(diff) > 200:
                print(f"  ... (diff truncated, {len(diff)} total lines)", file=sys.stderr)

    print("\nFix it: python scripts/check_railway_sync.py --fix", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
