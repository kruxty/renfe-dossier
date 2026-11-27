#!/usr/bin/env python3
"""Gestión del histórico, metadatos, deduplicación e índice de búsqueda en el sitio."""
import json
import os
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
MAX_SEEN = 20000
MAX_SEARCH_INDEX = 3000


def _path(site_dir, *parts):
    return os.path.join(site_dir, "data", *parts)


def load_json(site_dir, name, default):
    path = _path(site_dir, name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    return default


def save_json(site_dir, name, data):
    path = _path(site_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


# ---------------------------------------------------------------- deduplicación
def load_seen(site_dir):
    return load_json(site_dir, "seen.json", {"urls": [], "titulos": []})


def is_seen(seen, item):
    return item.get("url") in seen.get("urls", []) or _norm(item.get("titulo")) in seen.get(
        "titulos", []
    )


def mark_seen(site_dir, seen, items):
    urls = list(seen.get("urls", []))
    titulos = list(seen.get("titulos", []))
    for it in items:
        if it.get("url"):
            urls.append(it["url"])
        t = _norm(it.get("titulo"))
        if t:
            titulos.append(t)
    save_json(
        site_dir,
        "seen.json",
        {"urls": urls[-MAX_SEEN:], "titulos": titulos[-MAX_SEEN:]},
    )


# ---------------------------------------------------------------- histórico
def load_reports(site_dir):
    return load_json(site_dir, "reports.json", [])


def report_exists(site_dir, tipo, date_to):
    target = date_to.strftime("%Y-%m-%d %H:%M")
    return any(
        r.get("tipo") == tipo and r.get("date_to") == target
        for r in load_reports(site_dir)
    )


def _next_run(now, scheduled_time):
    hh, mm = map(int, scheduled_time.split(":"))
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.strftime("%Y-%m-%d %H:%M")


def register_report(site_dir, settings, meta, report, items, repo_url, log=print):
    """Actualiza reports.json, status.json, search_index.json y settings públicos."""
    reports = load_reports(site_dir)
    counts = report["counts"]
    entry = {
        "id": report["id"],
        "tipo": meta["tipo"],
        "created": meta["created"],
        "date_from": meta["date_from"],
        "date_to": meta["date_to"],
        "total": counts["TOTAL"],
        "rojo": counts["ROJO"],
        "amarillo": counts["AMARILLO"],
        "verde": counts["VERDE"],
        "url_html": report["url_html"],
        "url_pdf": report["url_pdf"],
    }
    reports.insert(0, entry)
    save_json(site_dir, "reports.json", reports)

    now = datetime.now(TZ).replace(second=0, microsecond=0)
    status = {
        "scheduled_time": settings.get("scheduled_time", "07:05"),
        "last_run": {
            "tipo": meta["tipo"],
            "created": meta["created"],
            "total": counts["TOTAL"],
            "rojo": counts["ROJO"],
            "amarillo": counts["AMARILLO"],
            "verde": counts["VERDE"],
            "url": report["url_html"],
        },
        "next_run": _next_run(now, settings.get("scheduled_time", "07:05")),
        "total_reports": len(reports),
        "repo_url": repo_url,
        "pages_url": settings.get("pages_url", ""),
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
    }
    save_json(site_dir, "status.json", status)

    # Índice de búsqueda global (todas las noticias de todos los informes).
    index = load_json(site_dir, "search_index.json", [])
    for it in items:
        index.insert(
            0,
            {
                "titular": it.get("titulo", ""),
                "medio": it.get("medio", ""),
                "fecha": it.get("fecha", "") or meta["created"],
                "color": it.get("color", ""),
                "prioridad": it.get("prioridad", 0),
                "resumen": it.get("resumen_ejecutivo", "") or it.get("resumen", ""),
                "url_noticia": it.get("url", ""),
                "url_informe": report["url_html"],
                "informe": f"{meta['tipo']} · {meta['created']}",
            },
        )
    save_json(site_dir, "search_index.json", index[:MAX_SEARCH_INDEX])

    # Settings públicos (sin claves) para el panel de configuración.
    import config_loader

    save_json(site_dir, "settings.json", config_loader.public_settings(settings))
    log(f"  [history] Informe registrado ({len(reports)} en total).")
