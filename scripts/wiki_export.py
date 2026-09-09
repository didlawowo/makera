"""Export reprenable du wiki ; `status` traite uniquement les fichiers locaux."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from lxml import etree
from lxml import html as lhtml

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://wiki.makera.com"


def article_url(value: str, base: str = BASE + "/en/home") -> str | None:
    parts = urlsplit(urljoin(base, value))
    if parts.scheme not in {"http", "https"} or parts.netloc != "wiki.makera.com":
        return None
    path = unquote(parts.path).rstrip("/")
    if not path:
        path = "/en/home"
    if path.startswith(("/_", "/login", "/logout", "/graphql", "/e/")) or ":" in path:
        return None
    if Path(path).suffix or ".." in path.split("/"):
        return None
    if not path.startswith("/en/"):
        # Only English wiki pages; other locale prefixes are not article roots.
        if len(path.split("/")[1]) == 2:
            return None
        path = "/en" + path
    return urlunsplit(("https", "wiki.makera.com", quote(path, safe="/()-_"), "", ""))


def parse_page(raw: bytes) -> dict:
    document = lhtml.fromstring(raw)
    pages = document.xpath("//page[@path]")
    templates = document.xpath('//template[@slot="contents"]')
    if not pages or not templates:
        raise ValueError("Pas une page Wiki.js avec un contenu exportable")
    page = pages[0]
    if page.get("locale", "en") != "en":
        raise ValueError("Page hors de la version anglaise")
    url = article_url("/en/" + page.get("path", ""))
    if not url:
        raise ValueError("Adresse de page invalide")
    content = templates[0]
    links = set()
    for href in content.xpath(".//a/@href"):
        if href.startswith("#"):
            continue
        target = article_url(href, url)
        if target:
            links.add(target)
    sidebar = page.get("sidebar")
    if sidebar:
        try:
            for item in json.loads(base64.b64decode(sidebar)):
                if item.get("y") == "page" and item.get("t"):
                    target = article_url(item["t"], url)
                    if target:
                        links.add(target)
        except (ValueError, TypeError, KeyError):
            pass
    # The complete article remains available, including very short index pages.
    fragment = (html.escape(content.text or "") + "".join(
        etree.tostring(child, encoding="unicode", method="html") for child in content
    ))
    return {"url": url, "title": page.get("title", url), "html": fragment,
            "links": sorted(links), "characters": len(content.text_content().strip())}


def load_sources(root: Path) -> tuple[dict, list]:
    pages = {}
    invalid = []
    files = sorted((root / "sources").glob("*.html.gz"))
    files += sorted((root / "source-cache").glob("*.html"))
    for source in files:
        try:
            raw = gzip.decompress(source.read_bytes()) if source.suffix == ".gz" else source.read_bytes()
            page = parse_page(raw)
            page["source"] = str(source.relative_to(root))
            pages[page["url"]] = page
        except (OSError, ValueError, etree.ParserError) as error:
            invalid.append({"file": str(source.relative_to(root)), "error": str(error)})
    return pages, invalid


def requested_urls(root: Path, pages: dict) -> set[str]:
    urls = set()
    for line in (root / "urls.txt").read_text().splitlines():
        url = article_url(line.strip())
        if url:
            urls.add(url)
    for page in pages.values():
        urls.update(page["links"])
    return urls | set(pages)


def save_report(root: Path, pages: dict, requested: set, errors: dict, invalid: list) -> dict:
    output = root / "originals"
    output.mkdir(exist_ok=True)
    entries = []
    for url, page in sorted(pages.items()):
        name = hashlib.sha256(url.encode()).hexdigest()[:20] + ".html"
        # Keep original HTML available for translation, without executing wiki scripts.
        tree = lhtml.fragment_fromstring(page["html"], create_parent="article")
        etree.strip_elements(tree, "script", "style", with_tail=False)
        for node in tree.iter():
            for attr in list(node.attrib):
                if attr.lower().startswith("on"):
                    del node.attrib[attr]
            for attr in ("href", "src"):
                value = node.get(attr)
                if value and not value.startswith("#"):
                    resolved = urljoin(url, value)
                    if urlsplit(resolved).scheme in {"http", "https", "mailto"}:
                        node.set(attr, resolved)
                    else:
                        del node.attrib[attr]
        body = etree.tostring(tree, encoding="unicode", method="html")
        title = html.escape(page["title"])
        (output / name).write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
                                  + '<meta name="viewport" content="width=device-width">'
                                  + f'<title>{title}</title><h1>{title}</h1>{body}</html>')
        entries.append({key: page[key] for key in ("url", "title", "source", "characters")}
                       | {"local_html": "originals/" + name})
    pending = sorted(requested - pages.keys())
    report = {"saved": len(pages), "discovered": len(requested), "pending": pending,
              "errors": {url: error for url, error in errors.items() if url in pending},
              "invalid_sources": invalid, "pages": entries}
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    items = "".join(f'<li><a href="{entry["local_html"]}">{html.escape(entry["title"])}</a></li>'
                    for entry in entries)
    (root / "index-originals.html").write_text('<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<title>Makera — export anglais</title><h1>Makera — export anglais</h1>'
        f'<p>{len(pages)} pages sauvegardées ; {len(pending)} adresses restent à vérifier.</p>'
        '<p>Les images et vidéos utilisent encore leurs adresses en ligne.</p><ul>' + items + '</ul></html>')
    print(f"{len(pages)} pages HTML sauvegardées / {len(requested)} adresses recensées ; "
          f"{len(pending)} restantes.", flush=True)
    return report


def download(url: str, path: Path) -> tuple[int, str]:
    # Finite retries for transient connection/HTTP failures, without retrying 404s.
    result = subprocess.run(["curl", "--silent", "--show-error", "--location",
        "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "3",
        "--connect-timeout", "15", "--max-time", "60", "--retry", "2",
        "--retry-delay", "3", "--retry-max-time", "150", "--retry-connrefused",
        "--retry-all-errors",
        "--output", str(path), "--write-out", "%{http_code}", url],
        capture_output=True, text=True, timeout=210, check=False)
    if result.returncode:
        return 0, result.stderr.strip()[-600:]
    return int(result.stdout[-3:]), ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "export"))
    args = parser.parse_args()
    pages, invalid = load_sources(ROOT)
    requested = requested_urls(ROOT, pages)
    errors = {}
    previous = ROOT / "report.json"
    if previous.exists():
        errors = json.loads(previous.read_text()).get("errors", {})
    report = save_report(ROOT, pages, requested, errors, invalid)
    if args.mode == "status":
        return 0
    retry_missing = os.environ.get("RETRY_MISSING", "0")
    if retry_missing not in {"0", "1"}:
        parser.error("RETRY_MISSING doit valoir 0 ou 1")
    cache = ROOT / "source-cache"
    cache.mkdir(exist_ok=True)
    attempted = set()
    if retry_missing == "0":
        attempted.update(url for url, error in errors.items() if error.get("status") in {404, 410})
    interrupted = False
    try:
        while True:
            remaining = sorted(requested - pages.keys() - attempted)
            if not remaining:
                break
            if len(attempted) >= 500:
                print("Limite de 500 adresses atteinte ; voir report.json.", flush=True)
                break
            url = remaining[0]
            attempted.add(url)
            print(f"Téléchargement : {url}", flush=True)
            temporary = cache / (hashlib.sha256(url.encode()).hexdigest() + ".part")
            try:
                status, message = download(url, temporary)
                if status != 200:
                    errors[url] = {"status": status, "message": message or f"HTTP {status}"}
                    print(f"  Échec conservé dans le bilan : {status} {message}", flush=True)
                else:
                    page = parse_page(temporary.read_bytes())
                    if page["url"] != url:
                        raise ValueError(f"Redirection vers une autre page : {page['url']}")
                    destination = temporary.with_suffix(".html")
                    temporary.replace(destination)
                    page["source"] = str(destination.relative_to(ROOT))
                    pages[url] = page
                    requested.update(page["links"])
                    errors.pop(url, None)
            except (OSError, ValueError, etree.ParserError, subprocess.TimeoutExpired) as error:
                errors[url] = {"status": 0, "message": str(error)}
                print(f"  Échec conservé dans le bilan : {error}", flush=True)
            finally:
                temporary.unlink(missing_ok=True)
            report = save_report(ROOT, pages, requested, errors, invalid)
            time.sleep(2)
    except KeyboardInterrupt:
        interrupted = True
        print("Interrompu : les pages déjà sauvegardées seront réutilisées.", flush=True)
    report = save_report(ROOT, pages, requested, errors, invalid)
    if interrupted:
        return 130
    if report["pending"]:
        unavailable = [url for url in report["pending"]
                       if errors.get(url, {}).get("status") in {404, 410}]
        unresolved = len(report["pending"]) - len(unavailable)
        print(f"Bilan : {len(unavailable)} liens introuvables (404/410), "
              f"{unresolved} autres pages à reprendre ; détails dans report.json.")
        return 1 if unresolved else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
