#!/usr/bin/env python3
"""Recolección de noticias desde feeds RSS y Google News."""
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

import config_loader

TZ = ZoneInfo("Europe/Madrid")
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; RenfeDossierBot/1.0; +https://github.com)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
MAX_ENTRIES_PER_FEED = 60
# Margen de tolerancia: algunos medios publican con fechas imprecisas.
TOLERANCIA_FIN = timedelta(hours=2)


def google_news_feed(query):
    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=es&gl=ES&ceid=ES:es"
    )


def clean_html(text):
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def parse_date(entry):
    """Devuelve datetime aware en hora de Madrid o None."""
    for attr in ("published_parsed", "updated_parsed"):
        st = getattr(entry, attr, None)
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=ZoneInfo("UTC"))
                return dt.astimezone(TZ)
            except Exception:
                continue
    return None


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def build_keyword_patterns(keywords):
    """Patrones con límite de palabra para evitar falsos positivos (p. ej. AVE/aves)."""
    patterns = []
    for kw in keywords:
        kw_n = _norm(kw)
        if not kw_n:
            continue
        patterns.append(re.compile(r"(?<!\w)" + re.escape(kw_n) + r"(?!\w)"))
    return patterns


def matches_keywords(text, patterns):
    text_n = _norm(text)
    return any(p.search(text_n) for p in patterns)


def _entry_id(link, title):
    return hashlib.sha1((link + "|" + title).encode("utf-8")).hexdigest()[:16]


def fetch_all(settings, date_from, date_to, log=print):
    """Recorre todas las fuentes y devuelve noticias filtradas por ventana temporal."""
    sources = config_loader.load_sources()
    enabled = settings.get("enabled_sources") or [s["nombre"] for s in sources]
    keywords = settings.get("keywords", [])
    patterns = build_keyword_patterns(keywords)

    feeds = []
    for s in sources:
        if s["nombre"] not in enabled:
            continue
        if s.get("url"):
            feeds.append((s["nombre"], s["categoria"], s["url"], False))
        if s.get("google_query"):
            feeds.append((s["nombre"], s["categoria"], google_news_feed(s["google_query"]), True))

    # Red de seguridad: una búsqueda de Google News por palabra clave.
    for kw in keywords:
        feeds.append((f"Google News · {kw}", "BUSCADOR", google_news_feed(f'"{kw}"'), True))

    items = []
    seen_urls = set()
    for nombre, categoria, feed_url, scoped in feeds:
        try:
            resp = requests.get(feed_url, headers=UA, timeout=25)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as exc:
            log(f"  [fetch] Aviso: {nombre}: {exc}")
            continue

        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            link = (getattr(entry, "link", "") or "").strip()
            title = clean_html(getattr(entry, "title", "") or "")
            if not link or not title or link in seen_urls:
                continue
            summary = clean_html(
                getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            )
            dt = parse_date(entry)
            if dt is not None and not (date_from - TOLERANCIA_FIN <= dt < date_to + TOLERANCIA_FIN):
                continue
            if not scoped and not matches_keywords(f"{title} {summary}", patterns):
                continue

            seen_urls.add(link)
            items.append(
                {
                    "id": _entry_id(link, title),
                    "titulo": title,
                    "medio": nombre,
                    "categoria": categoria,
                    "url": link,
                    "fecha": dt.strftime("%Y-%m-%d %H:%M") if dt else "",
                    "resumen": summary[:900],
                }
            )

    items.sort(key=lambda i: i.get("fecha") or "", reverse=True)
    cap = int(settings.get("max_news_per_report", 40))
    if len(items) > cap:
        log(f"  [fetch] Recorte a {cap} noticias (de {len(items)}).")
        items = items[:cap]
    return items


def dedupe(items):
    """Elimina duplicados por titular normalizado (misma noticia en varios medios/agregadores)."""
    seen_titles = set()
    out = []
    for it in items:
        key = _norm(it.get("titulo", ""))[:120]
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(it)
    return out
