"""Contrôles hors ligne de l'export et de sa reprise."""

import base64
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from wiki_export import article_url, load_sources, parse_page, requested_urls, save_report


def fixture(path="carvera/manual", content="<p>TBA</p>"):
    sidebar = base64.b64encode(json.dumps([
        {"y": "page", "t": "/en/Z1/Manual"}
    ]).encode()).decode()
    return (f'<html><meta charset="utf-8"><page locale="en" path="{path}" '
            f'title="Manual" sidebar="{sidebar}"><template slot="contents">'
            f'{content}</template></page></html>').encode()


class ExportTests(unittest.TestCase):
    def test_normalizes_old_urls_and_rejects_assets_external_and_editor(self):
        self.assertEqual(article_url("/carvera/manual#tools"),
                         "https://wiki.makera.com/en/carvera/manual")
        for value in ("/clamp.step", "/en/image.png", "https://other.test/en/manual",
                      "/e/en/Air/Manual", "/https://wiki.makera.com/en/home", "/fr/home",
                      "javascript:alert(1)"):
            with self.subTest(value=value):
                self.assertIsNone(article_url(value))

    def test_keeps_short_pages_and_discovers_hidden_sidebar(self):
        page = parse_page(fixture())
        self.assertEqual(page["characters"], 3)
        self.assertIn("<p>TBA</p>", page["html"])
        self.assertIn("https://wiki.makera.com/en/Z1/Manual", page["links"])

    def test_preserves_all_table_content_and_links(self):
        page = parse_page(fixture(content='<h2>Étape</h2><table><tr><td>9000 rpm</td>'
            '<td><p>First</p><p>Second</p></td></tr></table>'
            '<a href="/en/Air/Manual">Air</a><a href="#same">same</a>'))
        for text in ("Étape", "9000 rpm", "First", "Second"):
            self.assertIn(text, page["html"])
        self.assertIn("https://wiki.makera.com/en/Air/Manual", page["links"])
        self.assertNotIn(page["url"], page["links"])

    def test_rejects_sitemap_and_error_responses(self):
        for raw in (b'<urlset><url><loc>https://wiki.makera.com/home</loc></url></urlset>',
                    b'<html><h1>404 Not found</h1></html>'):
            with self.assertRaises(ValueError):
                parse_page(raw)

    def test_recovers_gzip_deduplicates_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sources").mkdir()
            (root / "source-cache").mkdir()
            raw = fixture(content='<p onclick="bad()">TBA</p><script>bad()</script>')
            source = root / "sources" / "original.html.gz"
            source.write_bytes(gzip.compress(raw))
            original_bytes = source.read_bytes()
            (root / "source-cache" / "copy.html").write_bytes(raw)
            (root / "urls.txt").write_text("https://wiki.makera.com/carvera/manual\n")
            pages, invalid = load_sources(root)
            self.assertEqual(len(pages), 1)
            self.assertEqual(invalid, [])
            report = save_report(root, pages, requested_urls(root, pages), {}, invalid)
            self.assertEqual(report["saved"], 1)
            self.assertEqual(report["pending"], ["https://wiki.makera.com/en/Z1/Manual"])
            exported = (root / report["pages"][0]["local_html"]).read_text()
            self.assertIn("TBA", exported)
            self.assertNotIn("onclick", exported)
            self.assertNotIn("<script", exported)
            self.assertEqual(source.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
