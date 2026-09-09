"""Préparer les textes à traduire sans modifier la structure HTML originale."""

import hashlib
import json
from pathlib import Path
import re

from lxml import html

ROOT = Path(__file__).resolve().parent.parent


def text_id(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def translatable(value):
    value = value.strip()
    return bool(value and re.search(r"[A-Za-z]{2}", value)
                and not re.fullmatch(r"(?:https?://|mailto:|www\.)\S+", value)
                and not re.fullmatch(r"[\d\s.,×x/*+−\-°%()]+(?:mm|min|rpm|in|Hz|V|A|W|kg|s|m|mm/min)?", value))


def strings(tree):
    for node in tree.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag not in {"script", "style", "code", "pre"} and not any(
            parent.tag in {"script", "style", "code", "pre"} for parent in node.iterancestors()
        ):
            if node.text and translatable(node.text):
                yield node, "text", node.text
            for key in ("alt", "title"):
                if node.get(key) and translatable(node.get(key)):
                    yield node, key, node.get(key)
        if node.tail and translatable(node.tail) and not any(
            parent.tag in {"script", "style", "code", "pre"} for parent in node.iterancestors()
        ):
            yield node, "tail", node.tail


def main():
    report = json.loads((ROOT / "report.json").read_text())
    items = {}
    for page in report["pages"]:
        tree = html.fromstring((ROOT / page["local_html"]).read_bytes())
        for _, _, value in strings(tree):
            value = value.strip()
            key = text_id(value)
            if key not in items:
                items[key] = {"id": key, "text": value, "page": page["url"]}
    directory = ROOT / "translation" / "input"
    directory.mkdir(parents=True, exist_ok=True)
    (ROOT / "translation" / "output").mkdir(exist_ok=True)
    chunks, chunk, size = [], [], 0
    for item in items.values():
        if chunk and size + len(item["text"]) > 14500:
            chunks.append(chunk)
            chunk, size = [], 0
        chunk.append(item)
        size += len(item["text"])
    if chunk:
        chunks.append(chunk)
    for index, values in enumerate(chunks, 1):
        (directory / f"{index:03}.json").write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"pages": len(report["pages"]), "unique_texts": len(items),
                      "characters": sum(len(item["text"]) for item in items.values()),
                      "chunks": len(chunks)}, indent=2))


if __name__ == "__main__":
    main()
