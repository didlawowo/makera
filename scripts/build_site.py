"""Assembler un site statique bilingue à partir de l'archive et des traductions Luna."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from lxml import etree
from lxml import html as lhtml

from prepare_translation import strings, text_id
from review_numbers import signature
from wiki_export import article_url

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
GROUPS = {
    "general": ("Bien démarrer", "Les bases de la CNC, la sécurité et les réglages essentiels."),
    "carvera": ("Carvera", "Installation, usinage, entretien et dépannage de votre Carvera."),
    "Air": ("Carvera Air", "Prendre en main la Carvera Air et la garder en bon état."),
    "Z1": ("Makera Z1", "Démarrage, accessoires et maintenance de la Z1."),
    "software": ("Logiciels & FAO", "Makera CAM et les logiciels de conception et de fabrication."),
    "Cyclone": ("Collecteur Cyclone", "Utilisation et entretien du système d’aspiration."),
    "Makera-Accessories": ("Accessoires", "Palpeur 3D, gravure et équipements complémentaires."),
    "knowledge-sharing": ("Communauté", "Les ressources et astuces partagées par les utilisateurs."),
}


def read_translations(allow_partial=False):
    expected, translations, problems = {}, {}, []
    for source in sorted((ROOT / "translation/input").glob("*.json")):
        items = json.loads(source.read_text())
        expected.update({item["id"]: item["text"] for item in items})
        target = ROOT / "translation/output" / source.name
        if not target.exists():
            continue
        values = json.loads(target.read_text())
        wanted = {item["id"] for item in items}
        if set(values) != wanted:
            problems.append({"chunk": source.name, "missing": sorted(wanted - values.keys()),
                             "extra": sorted(values.keys() - wanted)})
        for key, value in values.items():
            if not isinstance(value, str) or not value.strip():
                problems.append({"chunk": source.name, "id": key, "error": "Traduction vide/invalide"})
            else:
                translations[key] = value
    corrections = ROOT / "translation/corrections.json"
    if corrections.exists():
        translations.update(json.loads(corrections.read_text()))
    missing = sorted(expected.keys() - translations.keys())
    numeric = []
    reviewed_path = ROOT / "translation/numeric-reviewed.json"
    reviewed = json.loads(reviewed_path.read_text()) if reviewed_path.exists() else {}
    approved = 0
    for key, value in translations.items():
        if key not in expected:
            continue
        source = expected[key]
        pattern = r"\d+(?:[.,]\d+)*"
        if Counter(re.findall(pattern, source)) != Counter(re.findall(pattern, value)):
            difference = {"id": key, "source": source, "translation": value}
            if reviewed.get(key, {}).get("signature") == signature(difference):
                approved += 1
            else:
                numeric.append(difference)
        if len(source) > 100 and len(value) < len(source) * 0.48:
            problems.append({"id": key, "error": "Traduction anormalement courte"})
    audit = {"expected": len(expected), "translated": len(translations),
             "missing": missing, "problems": problems, "numeric_review": numeric,
             "numeric_approved": approved}
    (ROOT / "translation/audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(f"Traduction : {len(translations)}/{len(expected)} textes, "
          f"{len(problems)} erreurs, {len(numeric)} écarts numériques à contrôler.", flush=True)
    if problems or ((missing or numeric) and not allow_partial):
        raise ValueError("Traduction incomplète ou invalide : voir translation/audit.json")
    return translations, audit


def translate_tree(tree, translations):
    for node, attr, value in list(strings(tree)):
        translated = translations.get(text_id(value.strip()))
        if translated is None:
            continue
        prefix = value[:len(value) - len(value.lstrip())]
        suffix = value[len(value.rstrip()):]
        value = prefix + translated + suffix
        if attr in {"text", "tail"}:
            setattr(node, attr, value)
        else:
            node.set(attr, value)


def group_for(url):
    root = urlsplit(url).path.split("/")[2]
    return root if root in GROUPS else "general"


def slug(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def render_content(page, language, translations, known, assets):
    tree = lhtml.fromstring((ROOT / page["local_html"]).read_bytes())
    article = tree.xpath("//article")[0]
    if language == "fr":
        translate_tree(article, translations)
    etree.strip_elements(article, "script", "style", "form", with_tail=False)
    for node in list(article.iter()):
        if not isinstance(node.tag, str):
            continue
        for attr in list(node.attrib):
            if attr.lower().startswith("on") or attr in {"style", "srcset", "width", "height"}:
                del node.attrib[attr]
        if node.tag in {"iframe", "oembed", "embed", "object"}:
            url = node.get("src") or node.get("url") or node.get("data")
            if url and urlsplit(url).scheme in {"http", "https"}:
                replacement = lhtml.Element("a", href=url, attrib={"class": "video-link"})
                replacement.text = "▶ Ouvrir la vidéo ou le document" if language == "fr" else "▶ Open video or document"
                replacement.tail = node.tail
                node.getparent().replace(node, replacement)
            else:
                node.drop_tree()
            continue
        if node.tag == "a":
            href = node.get("href", "")
            if href.startswith("#"):
                continue
            parts = urlsplit(href)
            if parts.scheme and parts.scheme not in {"https", "http", "mailto"}:
                node.attrib.pop("href", None)
                continue
            target = article_url(href, page["url"])
            if target:
                if target in known:
                    anchor = unquote(parts.fragment)
                    if anchor not in known[target]:
                        normalized = re.sub(r"\s+", "-", anchor.lower()).replace("toolchange", "tool-change")
                        anchor = normalized if normalized in known[target] else ""
                    node.set("href", slug(target) + ".html" + ("#" + anchor if anchor else ""))
                else:
                    node.set("href", "../unavailable.html#" + slug(target))
                    node.set("class", (node.get("class", "") + " unavailable-link").strip())
            elif parts.scheme in {"https", "http"}:
                node.set("target", "_blank")
                node.set("rel", "noopener noreferrer")
        if node.tag == "img":
            src = node.get("src", "")
            if src in assets:
                node.set("src", "../" + assets[src])
            node.set("loading", "lazy")
            node.set("decoding", "async")
    toc = []
    used = {node.get("id") for node in article.iter() if node.get("id")}
    for index, heading in enumerate(article.xpath(".//h1|.//h2|.//h3")):
        for anchor in heading.xpath('.//a[contains(@class,"toc-anchor")]'):
            anchor.drop_tree()
        heading_id = heading.get("id")
        if not heading_id:
            heading_id = f"section-{index}"
            while heading_id in used:
                heading_id += "-x"
            heading.set("id", heading_id)
            used.add(heading_id)
        title = heading.text_content().strip()
        if title:
            toc.append((heading_id, title, heading.tag))
    return etree.tostring(article, encoding="unicode", method="html"), toc, article.text_content()


def shell(title, body, pages, active=None, prefix="", language="fr", toc=None):
    esc = html.escape
    navigation = []
    for key, (label, _) in GROUPS.items():
        links = []
        for page in pages:
            if page["group"] != key:
                continue
            current = ' aria-current="page"' if page["url"] == active else ""
            links.append(f'<a href="{prefix}fr/{page["slug"]}.html"{current}>{esc(page["title"])}</a>')
        if links:
            expanded = " open" if active is None or any(p["url"] == active and p["group"] == key for p in pages) else ""
            navigation.append(f'<details{expanded}><summary>{esc(label)} <span>{len(links)}</span></summary>' + "".join(links) + '</details>')
    contents = ""
    if toc:
        contents = '<aside class="toc"><p>Sur cette page</p>' + "".join(
            f'<a class="{level}" href="#{esc(anchor, quote=True)}">{esc(label)}</a>'
            for anchor, label, level in toc) + '</aside>'
    return f'''<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Makera en français</title><meta name="description" content="Documentation Makera en français : CNC Carvera, Carvera Air, Z1 et Makera CAM.">
<link rel="stylesheet" href="{prefix}assets/style.css"><script defer src="{prefix}assets/search-data.js"></script><script defer src="{prefix}assets/app.js"></script></head>
<body data-prefix="{prefix}"><a class="skip-link" href="#main">Aller au contenu</a>
<aside class="sidebar" id="sidebar"><a class="brand" href="{prefix}index.html"><span class="brand-mark">M<span>↗</span></span><span>MAKERA<small>LE WIKI EN FRANÇAIS</small></span></a>
<a class="home-link" href="{prefix}index.html">⌂ &nbsp; Accueil</a><p class="nav-label">EXPLORER LA DOCUMENTATION</p><nav aria-label="Documentation">{''.join(navigation)}</nav>
<div class="sidebar-foot"><span class="status-dot"></span> Votre bibliothèque locale<a href="{prefix}unavailable.html">État de la copie & sources</a></div></aside>
<div class="workspace"><header class="topbar"><button class="menu-button" id="menu-toggle" aria-controls="sidebar" aria-expanded="false" aria-label="Ouvrir le menu">☰</button>
<span class="top-label">L’ATELIER / DOCUMENTATION</span><div class="search-wrap"><label class="sr-only" for="search">Rechercher dans les 91 pages</label><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Chercher un outil, un réglage, une procédure…" autocomplete="off"><kbd>/</kbd></div><span class="language-badge">FR</span></header>
<section class="search-results" id="search-results" hidden aria-label="Résultats de recherche"><div class="search-heading"><h2 id="search-status" aria-live="polite">Résultats</h2><button id="search-close">Fermer ×</button></div><div id="search-items"></div></section>
<main id="main" class="main">{body}</main><footer class="footer">Traduction française par Luna · Copie personnelle du wiki Makera.<br>Le texte des captures reste dans sa langue d’origine. Les vidéos et documents externes s’ouvrent en ligne.</footer></div>{contents}</body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    translations, audit = read_translations(args.allow_partial)
    report = json.loads((ROOT / "report.json").read_text())
    asset_report = ROOT / "assets-report.json"
    assets = json.loads(asset_report.read_text()).get("saved", {}) if asset_report.exists() else {}
    SITE.mkdir(exist_ok=True)
    for language in ("fr", "en"):
        (SITE / language).mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)
    pages = [dict(page, title=translations.get(text_id(page["title"]), page["title"]),
                  group=group_for(page["url"]), slug=slug(page["url"])) for page in report["pages"]]
    known = {page["url"]: set(lhtml.fromstring((ROOT / page["local_html"]).read_bytes()).xpath("//@id"))
             for page in pages}
    search = []
    for source, page in zip(report["pages"], pages):
        for language in ("fr", "en"):
            content, toc, plain = render_content(source, language, translations, known, assets)
            title = page["title"] if language == "fr" else source["title"]
            group = GROUPS[page["group"]][0]
            switch = ('<span aria-current="true">Français</span>' if language == "fr" else f'<a href="../fr/{page["slug"]}.html">Français</a>')
            switch += (f'<a href="../en/{page["slug"]}.html">English</a>' if language == "fr" else '<span aria-current="true">English</span>')
            body = f'<div class="breadcrumbs"><a href="../index.html">Accueil</a><span>/</span>{html.escape(group)}</div><div class="article-head"><span class="eyebrow">{html.escape(group)}</span><h1>{html.escape(title)}</h1><div class="article-meta"><span>{"Traduction Luna" if language == "fr" else "Version originale"}</span><span>·</span><a href="{html.escape(page["url"], quote=True)}" target="_blank" rel="noopener noreferrer">Voir sur le wiki Makera ↗</a><div class="language-switch">{switch}</div></div></div><div class="article-body">{content}</div><a class="back-top" href="#main">↑ Revenir en haut</a>'
            (SITE / language / (page["slug"] + ".html")).write_text(shell(title, body, pages, page["url"], "../", language, toc))
            if language == "fr":
                search.append({"title": title, "group": group, "url": "fr/" + page["slug"] + ".html",
                               "text": re.sub(r"\s+", " ", plain).strip()})
    cards = []
    for index, (key, (label, description)) in enumerate(GROUPS.items(), 1):
        members = [page for page in pages if page["group"] == key]
        if not members:
            continue
        preferred = {"general": "/GettingStarted", "carvera": "/carvera/manual", "Air": "/Air/Manual", "Z1": "/Z1/Manual", "software": "/software/MakeraCAM_userguide", "Cyclone": "/Cyclone/CycloneManual"}.get(key)
        first = next((page for page in members if preferred and page["url"].endswith(preferred)), members[0])
        cards.append(f'<a class="category-card" href="fr/{first["slug"]}.html"><span class="card-number">0{index}</span><span class="card-arrow">↗</span><h3>{html.escape(label)}</h3><p>{html.escape(description)}</p><span class="card-count">{len(members)} pages</span></a>')
    started = next(page for page in pages if page["url"].endswith("/GettingStarted"))
    safe = next(page for page in pages if page["url"].endswith("/Safety"))
    hero = f'<section class="hero"><div class="hero-copy"><span class="eyebrow"><span class="status-dot"></span> VOTRE DOCUMENTATION, À PORTÉE DE MAIN</span><h1>Le wiki Makera,<br><em>en français.</em></h1><p>Du premier copeau aux réglages avancés : retrouvez les guides de vos machines, les tutoriels et les réponses utiles à l’atelier.</p><div class="hero-actions"><a class="button primary" href="fr/{started["slug"]}.html">Bien démarrer <span>→</span></a><a class="button secondary" href="fr/{safe["slug"]}.html">Consignes de sécurité ↗</a></div></div><div class="hero-art" aria-hidden="true"><div class="art-grid"></div><div class="tool-head"></div><div class="tool-shaft"></div><div class="tool-tip"></div><div class="stock-layer layer-back"></div><div class="stock-layer layer-front"><div class="cut-path"></div></div><span class="axis axis-z">Z ↑</span><span class="axis axis-x">X →</span><span class="art-caption">CONCEVOIR. USINER. APPRENDRE.</span></div></section><div class="stats"><div><strong>{len(pages)}</strong><span>pages en français</span></div><div><strong>{len(cards):02}</strong><span>rubriques à explorer</span></div><div><strong>FR / EN</strong><span>les deux versions à portée de clic</span></div></div><section class="categories"><div class="section-heading"><div><span class="eyebrow">TROUVER LE BON GUIDE</span><h2>Votre machine. Votre prochain projet.</h2></div><span class="section-note">Tout le wiki dans un seul endroit.</span></div><div class="category-grid">{"".join(cards)}</div></section><div class="edition-note"><span>↳</span><p>Cette bibliothèque contient les <strong>{len(pages)} pages accessibles</strong> de l’export. <a href="unavailable.html">{len(report["pending"])} anciens liens introuvables</a> sont répertoriés à part.</p></div>'
    if audit["missing"]:
        hero = '<p class="preview-warning">Aperçu de construction : la traduction est encore incomplète.</p>' + hero
    (SITE / "index.html").write_text(shell("Accueil", hero, pages))
    unavailable = '<span class="eyebrow">ÉTAT DE LA COPIE</span><h1>Les sources et les liens introuvables</h1><p>Les pages ci-dessous renvoyaient une erreur 404 lors de l’export. Aucun texte n’a été inventé pour les remplacer.</p><ul class="unavailable-list">' + "".join(f'<li id="{slug(url)}"><span class="error-badge">404</span><a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(urlsplit(url).path)}</a></li>' for url in report["pending"]) + '</ul><p>Source : <a href="https://wiki.makera.com/en/GettingStarted">Wiki officiel Makera</a>. Les pages anglaises d’origine sont consultables à côté de chaque traduction. Les noms de produits et les valeurs techniques sont conservés.</p>'
    (SITE / "unavailable.html").write_text(shell("Sources et liens introuvables", unavailable, pages))
    (SITE / "assets/search-data.js").write_text("window.MAKERA_PAGES=" + json.dumps(search, ensure_ascii=False).replace("<", "\\u003c") + ";\n")
    summary = {"pages_fr": len(pages), "pages_en": len(pages), "illustrations_locales": len(assets),
               "missing_links": report["pending"], "translation": audit,
               "generated_at": datetime.now().astimezone().isoformat()}
    (ROOT / "site-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(f"Site construit : {len(pages)} pages françaises + {len(pages)} originales ; {len(assets)} illustrations locales.")


if __name__ == "__main__":
    main()
