"""Servir la bibliothèque sur ce Mac, à l'adresse 127.0.0.1 uniquement."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Le port doit être compris entre 1024 et 65535")
    site = Path(__file__).resolve().parent.parent / "site"
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Wiki Makera : http://127.0.0.1:{args.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
