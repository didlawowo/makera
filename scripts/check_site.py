"""Contrôler les fichiers, liens et valeurs techniques du site sans réseau."""

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lxml import html

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def main():
    report = json.loads((ROOT / "report.json").read_text())
    errors, anchors = [], []
    documents = {}
    for file in SITE.rglob("*.html"):
        tree = html.fromstring(file.read_bytes())
        documents[file.resolve()] = tree
    for file, tree in documents.items():
        for attribute in ("href", "src"):
            for value in tree.xpath(f"//@{attribute}"):
                parts = urlsplit(value)
                if parts.scheme or parts.netloc:
                    continue
                target = (file.parent / unquote(parts.path)).resolve() if parts.path else file
                if not target.is_relative_to(SITE.resolve()):
                    errors.append(f"Hors site: {file.name}: {value}")
                elif not target.is_file():
                    errors.append(f"Fichier manquant: {file.name}: {value}")
                elif parts.fragment and target in documents:
                    ids = documents[target].xpath("//@id")
                    if unquote(parts.fragment) not in ids:
                        anchors.append(f"Ancre source absente: {file.name}: {value}")
    for page in report["pages"]:
        name = Path(page["local_html"]).name
        en = documents[(SITE / "en" / name).resolve()]
        fr = documents[(SITE / "fr" / name).resolve()]
        for selector in ("//article//pre", "//article//code"):
            if [node.text_content() for node in en.xpath(selector)] != [node.text_content() for node in fr.xpath(selector)]:
                errors.append(f"Code modifié dans {page['url']}")
        for selector in ("//article//img", "//article//table", "//article//tr", "//article//td", "//article//th"):
            if len(en.xpath(selector)) != len(fr.xpath(selector)):
                errors.append(f"Structure modifiée ({selector}): {page['url']}")
    result = {"html_files": len(documents), "errors": errors, "source_anchor_warnings": anchors}
    (ROOT / "site-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(documents)} documents vérifiés ; {len(errors)} erreurs ; {len(anchors)} ancres source à revoir.")
    if errors:
        print("\n".join(errors[:20]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
