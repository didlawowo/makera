"""Découper les lots restants en unités courtes et assembler leurs traductions."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "translation"


def main():
    (ROOT / "work/input").mkdir(parents=True, exist_ok=True)
    (ROOT / "work/output").mkdir(parents=True, exist_ok=True)
    pending = []
    for source in sorted((ROOT / "input").glob("*.json")):
        if (ROOT / "output" / source.name).exists():
            continue
        items = json.loads(source.read_text())
        chunks, chunk, size = [], [], 0
        for item in items:
            if chunk and (len(chunk) >= 65 or size + len(item["text"]) > 5500):
                chunks.append(chunk)
                chunk, size = [], 0
            chunk.append(item)
            size += len(item["text"])
        if chunk:
            chunks.append(chunk)
        combined = {}
        complete = True
        for i, chunk in enumerate(chunks, 1):
            name = source.stem + f"-{i:02}.json"
            (ROOT / "work/input" / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=2) + "\n")
            target = ROOT / "work/output" / name
            if target.exists():
                values = json.loads(target.read_text())
                if set(values) != {item["id"] for item in chunk} or not all(isinstance(value, str) and value.strip() for value in values.values()):
                    raise ValueError(f"Invalid output: {name}")
                combined.update(values)
            else:
                complete = False
                pending.append(name)
        if complete:
            (ROOT / "output" / source.name).write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n")
            print(f"Assemblé {source.name}: {len(combined)} textes")
    (ROOT / "work/pending.json").write_text(json.dumps(pending, indent=2) + "\n")
    print(f"{len(pending)} petits lots restants")


if __name__ == "__main__":
    main()
