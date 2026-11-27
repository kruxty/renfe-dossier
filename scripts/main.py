#!/usr/bin/env python3
"""RENFE DOSSIER PRESIDENCIA — Orquestador principal.

Modos:
  --mode scheduled   Informe programado diario (ventana [hora-1día, hora]).
  --mode manual      Informe bajo demanda (ventana [hora programada, ahora]),
                     excluyendo cualquier noticia ya publicada antes.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import classifier
import config_loader
import emailer
import fetcher
import history
import renderer

TZ = ZoneInfo("Europe/Madrid")
SITE_DIR = os.environ.get("SITE_DIR", os.path.join(ROOT_DIR, "site"))
REPO_URL = os.environ.get("REPO_URL", "")
VENTANA_MINUTOS = 15  # el workflow se ejecuta cada 15 minutos


def log(msg):
    print(f"[dossier] {msg}", flush=True)


def _scheduled_datetime(now, scheduled_time):
    hh, mm = map(int, scheduled_time.split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)


def main():
    parser = argparse.ArgumentParser(description="Generador del Dossier Presidencia RENFE")
    parser.add_argument("--mode", choices=["scheduled", "manual"], default="scheduled")
    args = parser.parse_args()
    tipo = "PROGRAMADO" if args.mode == "scheduled" else "MANUAL"

    settings = config_loader.load_settings()
    now = datetime.now(TZ).replace(second=0, microsecond=0)
    target = _scheduled_datetime(now, settings.get("scheduled_time", "07:05"))

    if args.mode == "scheduled":
        # El workflow corre cada 15 min: solo generamos en la ventana de la hora configurada.
        if not (target <= now < target + timedelta(minutes=VENTANA_MINUTOS)):
            log(
                f"Fuera de ventana (programado {settings.get('scheduled_time')}, "
                f"ahora {now.strftime('%H:%M')} Madrid). Sin ejecución."
            )
            return 0
        date_to = target
        date_from = target - timedelta(days=1)
        if history.report_exists(SITE_DIR, "PROGRAMADO", date_to):
            log("Ya existe un informe PROGRAMADO para este periodo. Sin ejecución.")
            return 0
    else:
        date_to = now
        date_from = target if target <= now else target - timedelta(days=1)

    log(f"Modo {tipo} | Periodo: {date_from:%Y-%m-%d %H:%M} -> {date_to:%Y-%m-%d %H:%M}")

    seen = history.load_seen(SITE_DIR)
    items = fetcher.fetch_all(settings, date_from, date_to, log)
    log(f"Noticias candidatas: {len(items)}")

    if args.mode == "manual":
        antes = len(items)
        items = [it for it in items if not history.is_seen(seen, it)]
        log(f"Excluidas {antes - len(items)} noticias ya publicadas en informes anteriores.")
        if not items:
            log("No hay noticias nuevas desde el último informe. No se genera informe manual.")
            return 0

    items = fetcher.dedupe(items)
    items = classifier.classify(items, settings, log)

    orden = {"ROJO": 0, "AMARILLO": 1, "VERDE": 2}
    items.sort(key=lambda i: (orden.get(i.get("color", "VERDE"), 3), -int(i.get("prioridad", 0))))

    meta = {
        "tipo": tipo,
        "created": now.strftime("%Y-%m-%d %H:%M"),
        "date_from": date_from.strftime("%Y-%m-%d %H:%M"),
        "date_to": date_to.strftime("%Y-%m-%d %H:%M"),
    }

    report = renderer.render_report(settings, meta, items, SITE_DIR, log)
    history.register_report(SITE_DIR, settings, meta, report, items, REPO_URL, log)
    history.mark_seen(SITE_DIR, seen, items)
    emailer.send_report(settings, meta, report, items, log)

    log(f"Informe generado: {report['url_html']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
