#!/usr/bin/env python3
"""Carga de configuración del proyecto (config/settings.json)."""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
SETTINGS_PATH = os.path.join(ROOT_DIR, "config", "settings.json")
SOURCES_PATH = os.path.join(ROOT_DIR, "config", "sources.json")

DEFAULTS = {
    "scheduled_time": "07:05",
    "admin_email": "",
    "gemini_api_key": "",
    "enabled_sources": [],
    "keywords": ["Renfe", "AVE", "Cercanías", "Adif", "Ferrocarril"],
    "max_news_per_report": 40,
    "pages_url": "",
    "email_subject": "[DOSSIER PRESIDENCIA RENFE]",
    "email_enabled": True,
}


def load_settings():
    """Carga settings.json aplicando valores por defecto y variables de entorno."""
    settings = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            try:
                settings.update(json.load(fh))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"[config] settings.json inválido: {exc}")

    # La clave puede venir del fichero (admin) o del secreto GEMINI_API_KEY de GitHub.
    if not settings.get("gemini_api_key"):
        settings["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")

    # URL pública de GitHub Pages (para el botón del email).
    if not settings.get("pages_url"):
        settings["pages_url"] = _derive_pages_url()

    return settings


def load_sources():
    """Carga el listado de fuentes monitorizadas."""
    with open(SOURCES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _derive_pages_url():
    """Deriva https://<owner>.github.io/<repo>/ a partir de GITHUB_REPOSITORY."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return ""


def public_settings(settings):
    """Copia de settings segura para publicar en Pages (sin claves)."""
    pub = {k: v for k, v in settings.items() if k != "gemini_api_key"}
    return pub
