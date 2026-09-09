"""Enregistrer une relecture humaine/principale pour des écarts numériques précis."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "translation"


def signature(item):
    return hashlib.sha256((item["source"] + "\0" + item["translation"]).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="+")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    audit = json.loads((ROOT / "audit.json").read_text())
    items = {item["id"]: item for item in audit["numeric_review"]}
    path = ROOT / "numeric-reviewed.json"
    reviewed = json.loads(path.read_text()) if path.exists() else {}
    for key in args.ids:
        if key not in items:
            raise ValueError(f"Écart non présent dans l'audit : {key}")
        reviewed[key] = {"signature": signature(items[key]), "reason": args.reason}
    path.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(args.ids)} relectures enregistrées, liées aux textes exacts.")


if __name__ == "__main__":
    main()
