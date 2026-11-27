#!/usr/bin/env python3
"""Renderizado del dossier HTML (Jinja2) y PDF (WeasyPrint)."""
import json
import os
import shutil
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config_loader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")


def _env():
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_report(settings, meta, items, site_dir, log=print):
    """Genera index.html + metadata.json + dossier.pdf del informe y actualiza /latest."""
    for idx, it in enumerate(items, start=1):
        it["idx"] = idx

    counts = {
        "ROJO": sum(1 for i in items if i.get("color") == "ROJO"),
        "AMARILLO": sum(1 for i in items if i.get("color") == "AMARILLO"),
        "VERDE": sum(1 for i in items if i.get("color") == "VERDE"),
        "TOTAL": len(items),
    }

    created = datetime.strptime(meta["created"], "%Y-%m-%d %H:%M")
    report_id = f"{meta['tipo'].lower()}-{created.strftime('%H%M')}"
    rel_dir = os.path.join(
        "reports",
        created.strftime("%Y"),
        created.strftime("%m"),
        created.strftime("%d"),
        report_id,
    )
    abs_dir = os.path.join(site_dir, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    sources = config_loader.load_sources()
    enabled = settings.get("enabled_sources") or [s["nombre"] for s in sources]
    active_sources = [s for s in sources if s["nombre"] in enabled]

    template = _env().get_template("dossier.html.j2")
    html = template.render(
        meta=meta,
        items=items,
        counts=counts,
        sources=active_sources,
        total_sources=len(active_sources),
        generated=meta["created"],
        pages_url=settings.get("pages_url", ""),
    )

    index_path = os.path.join(abs_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    with open(os.path.join(abs_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                **meta,
                "counts": counts,
                "noticias": [
                    {
                        "titulo": i.get("titulo"),
                        "medio": i.get("medio"),
                        "fecha": i.get("fecha"),
                        "color": i.get("color"),
                        "prioridad": i.get("prioridad"),
                        "url": i.get("url"),
                    }
                    for i in items
                ],
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    pdf_ok = _render_pdf(html, os.path.join(abs_dir, "dossier.pdf"), log)

    # Copia como informe "actual" en /latest.
    latest_dir = os.path.join(site_dir, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    shutil.copyfile(index_path, os.path.join(latest_dir, "index.html"))
    pdf_path = os.path.join(abs_dir, "dossier.pdf")
    if pdf_ok:
        shutil.copyfile(pdf_path, os.path.join(latest_dir, "dossier.pdf"))

    rel = rel_dir.replace(os.sep, "/")
    log(f"  [renderer] Dossier generado en {rel}/")
    return {
        "id": report_id,
        "dir": abs_dir,
        "url_html": f"{rel}/index.html",
        "url_pdf": f"{rel}/dossier.pdf" if pdf_ok else "",
        "pdf_path": pdf_path if pdf_ok else "",
        "counts": counts,
    }


def _render_pdf(html, pdf_path, log):
    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(pdf_path)
        log("  [renderer] PDF generado (dossier.pdf).")
        return True
    except Exception as exc:
        log(f"  [renderer] Aviso: no se pudo generar el PDF: {exc}")
        return False
