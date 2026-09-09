#!/usr/bin/env bash
set -euo pipefail

export_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export_urls="${export_root}/urls.txt"

if [[ ! -s "$export_urls" ]]; then
  printf 'Liste des pages absente ou vide : %s\n' "$export_urls" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  printf 'uv est nécessaire pour lancer cet export.\n' >&2
  exit 1
fi

uv tool run --from trafilatura==2.2.0 python "${export_root}/scripts/wiki_export.py" export
