"""Télécharger les illustrations référencées par l'archive locale fournie."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote, urlsplit, urlunsplit

from lxml import html

ROOT = Path(__file__).resolve().parent.parent


def download(url):
    parts = urlsplit(url)
    suffix = Path(parts.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".bmp"}:
        suffix = ".img"
    name = hashlib.sha256(url.encode()).hexdigest()[:24] + suffix
    destination = ROOT / "site" / "assets" / "media" / name
    if destination.is_file() and destination.stat().st_size:
        return url, "assets/media/" + name, None
    temporary = destination.with_suffix(suffix + ".part")
    encoded = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%:@"),
                         quote(parts.query, safe="=&%+"), ""))
    try:
        result = subprocess.run(["curl", "--silent", "--show-error", "--fail", "--location",
            "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "3",
            "--connect-timeout", "10", "--max-time", "40", "--retry", "1",
            "--max-filesize", "25000000", "--output", str(temporary), encoded],
            capture_output=True, text=True, timeout=100, check=False)
        if result.returncode:
            return url, None, result.stderr[-250:]
        data = temporary.read_bytes()
        if not data or data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            return url, None, "Réponse vide ou HTML au lieu d'une image"
        temporary.replace(destination)
        return url, "assets/media/" + name, None
    except (OSError, subprocess.TimeoutExpired) as error:
        return url, None, str(error)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    directory = ROOT / "site" / "assets" / "media"
    directory.mkdir(parents=True, exist_ok=True)
    report = json.loads((ROOT / "report.json").read_text())
    urls = set()
    for page in report["pages"]:
        tree = html.fromstring((ROOT / page["local_html"]).read_bytes())
        urls.update(url for url in tree.xpath("//img/@src")
                    if urlsplit(url).scheme == "https")
    success, errors = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(download, url) for url in sorted(urls)]
        for i, future in enumerate(as_completed(futures), 1):
            url, local, error = future.result()
            if local:
                success[url] = local
            else:
                errors[url] = error
            if i % 25 == 0 or i == len(urls):
                print(f"Illustrations : {i}/{len(urls)} traitées, {len(errors)} erreurs", flush=True)
    (ROOT / "assets-report.json").write_text(json.dumps(
        {"saved": success, "errors": errors}, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(success)} illustrations locales ; {len(errors)} restent en ligne.")


if __name__ == "__main__":
    main()
