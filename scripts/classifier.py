#!/usr/bin/env python3
"""Clasificación y priorización de noticias con Gemini API (con fallback heurístico)."""
import json
import re

import requests

MODEL = "gemini-2.5-flash"
BATCH_SIZE = 12
COLORES = ("ROJO", "AMARILLO", "VERDE")

PALABRAS_ROJO = [
    "accidente", "accidentado", "investigación", "investigan", "crisis",
    "ciberataque", "descarril", "huelga", "sanción", "sancionan",
    "incidente grave", "muerte", "muerto", "fallec", "herido", "colisión",
    "atropello", "caos", "evacuad", "incendio", "agresión", "detenid",
]
PALABRAS_AMARILLO = [
    "competencia", "retraso", "infraestructura", "reclamación", "reclaman",
    "regulación", "regulador", "avería", "demora", "supresión", "suprim",
    "queja", "multa", "cnmc", "liberalización", "ouigo", "iryo", "obras",
    "interrupción", "suspens",
]
PALABRAS_VERDE = [
    "innovación", "innovador", "resultados", "premio", "nuevo servicio",
    "sostenib", "acuerdo", "récord", "inversión", "mejora", "ampliación",
    "crece", "crecimiento", "alianza", "contrato", "modernización", "hidrógeno",
]

PROMPT_TEMPLATE = """Eres el analista senior de medios de la Presidencia de Renfe.
Analiza las siguientes noticias y clasifícalas.

CRITERIOS DE CLASIFICACIÓN:
- ROJO: accidentes, investigaciones, crisis, ciberataques, descarrilamientos, huelgas, sanciones, incidentes graves.
- AMARILLO: competencia, retrasos, infraestructuras, reclamaciones, regulación.
- VERDE: innovación, resultados, premios, nuevos servicios, sostenibilidad, acuerdos.

Para CADA noticia devuelve un objeto JSON con EXACTAMENTE estos campos:
- "id": el id numérico de la noticia (sin comillas).
- "color": "ROJO", "AMARILLO" o "VERDE".
- "prioridad": entero entre 1 y 100 (100 = máxima relevancia para Presidencia).
- "resumen_ejecutivo": 2-3 frases claras y directas, en español.
- "impacto_reputacional": 1 frase.
- "impacto_operativo": 1 frase.
- "impacto_politico": 1 frase.

Responde ÚNICAMENTE con un array JSON válido, sin texto adicional ni markdown.

NOTICIAS:
{noticias}
"""


def _fallback_one(item):
    """Clasificación heurística por palabras clave cuando Gemini no está disponible."""
    text = (item.get("titulo", "") + " " + item.get("resumen", "")).lower()
    rojo = sum(1 for w in PALABRAS_ROJO if w in text)
    amarillo = sum(1 for w in PALABRAS_AMARILLO if w in text)
    verde = sum(1 for w in PALABRAS_VERDE if w in text)

    if rojo > 0:
        color, prioridad = "ROJO", min(95, 70 + rojo * 5)
    elif amarillo > 0:
        color, prioridad = "AMARILLO", min(69, 40 + amarillo * 5)
    else:
        color, prioridad = "VERDE", min(39, 15 + verde * 5)

    resumen = item.get("resumen") or item.get("titulo", "")
    item.update(
        {
            "color": color,
            "prioridad": prioridad,
            "resumen_ejecutivo": resumen[:400],
            "impacto_reputacional": "Valoración automática pendiente de revisión.",
            "impacto_operativo": "Valoración automática pendiente de revisión.",
            "impacto_politico": "Valoración automática pendiente de revisión.",
        }
    )
    return item


def _gemini_call(prompt, api_key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json_array(text):
    """Extrae el primer array JSON de la respuesta del modelo."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("La respuesta no contiene un array JSON")
    return json.loads(text[start : end + 1])


def _apply_result(item, result):
    color = str(result.get("color", "")).upper().strip()
    if color not in COLORES:
        return False
    try:
        prioridad = max(1, min(100, int(result.get("prioridad", 50))))
    except (TypeError, ValueError):
        prioridad = 50
    item.update(
        {
            "color": color,
            "prioridad": prioridad,
            "resumen_ejecutivo": str(result.get("resumen_ejecutivo", "")).strip()
            or item.get("resumen", "")[:400],
            "impacto_reputacional": str(result.get("impacto_reputacional", "")).strip(),
            "impacto_operativo": str(result.get("impacto_operativo", "")).strip(),
            "impacto_politico": str(result.get("impacto_politico", "")).strip(),
        }
    )
    return True


def classify(items, settings, log=print):
    """Clasifica todas las noticias. Usa Gemini si hay clave; si falla, fallback."""
    api_key = settings.get("gemini_api_key", "")
    if not items:
        return items
    if not api_key:
        log("  [classifier] Sin GEMINI_API_KEY: clasificación heurística.")
        return [_fallback_one(it) for it in items]

    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        noticias_txt = "\n".join(
            f"{n}. id={n} | medio={it['medio']} | titular={it['titulo']} | "
            f"resumen={it.get('resumen', '')[:350]}"
            for n, it in enumerate(batch)
        )
        prompt = PROMPT_TEMPLATE.replace("{noticias}", noticias_txt)
        try:
            raw = _gemini_call(prompt, api_key)
            results = {int(r["id"]): r for r in _parse_json_array(raw) if "id" in r}
        except Exception as exc:
            log(f"  [classifier] Gemini falló en lote {start // BATCH_SIZE + 1}: {exc}")
            results = {}

        for n, it in enumerate(batch):
            if n in results and _apply_result(it, results[n]):
                continue
            _fallback_one(it)

    log(f"  [classifier] {len(items)} noticias clasificadas.")
    return items
