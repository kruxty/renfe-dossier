# RENFE DOSSIER PRESIDENCIA

Generación automática, todos los días, de un **dossier ejecutivo de medios** para
Presidencia de Renfe. Funciona íntegramente con **GitHub Actions + GitHub Pages**:
sin servidores propios, sin Azure OpenAI. La clasificación la realiza la **API de Gemini**.

Genera: dossier **HTML ejecutivo**, **PDF** (WeasyPrint), **histórico** de informes,
**correo electrónico** automático y **dashboard administrativo**.

---

## 1. Arquitectura

| Componente | Tecnología |
|---|---|
| Orquestación y scraping | Python 3.12 · Requests · Feedparser · BeautifulSoup |
| Clasificación y resúmenes | Gemini API (`gemini-2.5-flash`) con fallback heurístico |
| Plantillas | Jinja2 (dossier HTML + email HTML) |
| PDF | WeasyPrint |
| Ejecución | GitHub Actions (cron cada 15 min + ejecución manual) |
| Publicación | GitHub Pages (rama `gh-pages`) |
| Dashboard | HTML5 + CSS3 + JavaScript puro (sin frameworks) |

```
┌─ GitHub Actions ──────────────────────────────────────────────┐
│  fetcher.py   → 47 fuentes RSS/Google News                    │
│  classifier.py → Gemini (color ROJO/AMARILLO/VERDE + prioridad)│
│  renderer.py  → dossier HTML + PDF + metadata.json            │
│  history.py   → histórico, deduplicación, índice de búsqueda  │
│  emailer.py   → correo corporativo con PDF adjunto            │
└───────────────┬───────────────────────────────────────────────┘
                ▼  (commit a la rama gh-pages)
┌─ GitHub Pages ────────────────────────────────────────────────┐
│  /                     Dashboard administrativo               │
│  /latest/index.html    Último dossier                         │
│  /reports/YYYY/MM/DD/  Histórico (index.html + dossier.pdf    │
│                        + metadata.json)                       │
│  /data/*.json          Estado, histórico, índice de búsqueda  │
└───────────────────────────────────────────────────────────────┘
```

## 2. Tipos de informe

| Tipo | Disparo | Periodo |
|---|---|---|
| **PROGRAMADO** | Diario a la hora configurada (por defecto **07:05**, hora de Madrid) | Desde las 07:05 del día anterior hasta las 07:05 del día actual |
| **MANUAL** | Botón del dashboard → *Run workflow* en Actions | Desde las 07:05 del día actual hasta la hora de ejecución |

> El informe manual **nunca repite** noticias ya incluidas en informes anteriores
> (deduplicación persistente en `data/seen.json` de la rama `gh-pages`).

Metadatos de cada informe (`metadata.json`):

```json
{
  "tipo": "PROGRAMADO",
  "created": "2026-11-27 07:05",
  "date_from": "2026-11-26 07:05",
  "date_to": "2026-11-27 07:05"
}
```

## 3. Puesta en marcha

### 3.1 Subir el proyecto

1. Crea un repositorio en GitHub (público o privado con Pages habilitado).
2. Copia todo el contenido de este proyecto y haz push a la rama `main`.

### 3.2 Activar GitHub Pages

`Settings → Pages → Build and deployment → Deploy from a branch → gh-pages / (root)`.
La rama `gh-pages` la crea automáticamente el primer workflow. La web quedará en
`https://<usuario>.github.io/<repo>/`.

### 3.3 Configurar secretos (Actions)

`Settings → Secrets and variables → Actions → New repository secret`:

| Secreto | Obligatorio | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | Recomendado | Clave de Gemini API (Google AI Studio). Sin ella se usa clasificación heurística. |
| `SMTP_HOST` | Para email | Servidor SMTP (p. ej. `smtp.gmail.com`). |
| `SMTP_PORT` | Para email | Puerto (por defecto 587). |
| `SMTP_USER` | Para email | Usuario/cuenta de correo. |
| `SMTP_PASSWORD` | Para email | Contraseña o *app password* (en Gmail: contraseña de aplicación). |
| `EMAIL_FROM` | Opcional | Remitente (por defecto `SMTP_USER`). |
| `EMAIL_TO` | Para email | Destinatarios separados por comas (por defecto `admin_email`). |

### 3.4 Configuración (`config/settings.json`)

```json
{
  "scheduled_time": "07:05",
  "admin_email": "presidencia@example.com",
  "gemini_api_key": "",
  "enabled_sources": []
}
```

- **`scheduled_time`**: hora diaria del informe (Europe/Madrid). *Solo el administrador
  debe cambiarla.* El workflow corre cada 15 minutos y ejecuta el informe cuando la
  hora coincide: no hace falta tocar el fichero del workflow.
- **`enabled_sources`**: vacío = todas las fuentes de `config/sources.json`.
  Para limitar, lista los nombres exactos, p. ej. `["El País", "Expansión"]`.
- **`keywords`**, **`max_news_per_report`**, **`email_subject`**: ajustables.

## 4. Uso del dashboard

Abierto en GitHub Pages, el panel permite:

1. **Generar informe ahora** → abre Actions; pulsa **Run workflow** (informe MANUAL).
2. **Consultar el histórico** con filtro por fecha y tipo.
3. **Buscar informes y noticias** por titular, medio, fecha y texto libre.
4. Ver **próxima ejecución**, **última ejecución**, **hora programada** y
   **número total de informes**.
5. Ver la **configuración** vigente (con enlace directo para editar `settings.json`).

## 5. Clasificación IA (Gemini)

- 🔴 **ROJO**: accidentes, investigaciones, crisis, ciberataques, descarrilamientos,
  huelgas, sanciones, incidentes graves.
- 🟡 **AMARILLO**: competencia, retrasos, infraestructuras, reclamaciones, regulación.
- 🟢 **VERDE**: innovación, resultados, premios, nuevos servicios, sostenibilidad, acuerdos.

Cada noticia recibe además una **prioridad de 1 a 100** y se ordena por
**color → prioridad descendente**. Cada ficha incluye resumen ejecutivo e impactos
reputacional, operativo y político.

## 6. Correo electrónico

Asunto: `[DOSSIER PRESIDENCIA RENFE] <TIPO> · <fecha>` — plantilla corporativa con el
resumen ejecutivo (🔴/🟡/🟢), el **Top 5** de noticias, botón **Abrir Dossier HTML**
y el **PDF adjunto**.

## 7. Ejecución local (opcional)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="..."   # opcional
python scripts/main.py --mode manual
# El sitio se genera en ./site (o en $SITE_DIR)
```

## 8. Estructura del repositorio

```
├── .github/workflows/dossier.yml   # Workflow (cron 15 min + manual)
├── config/
│   ├── settings.json               # Configuración administrable
│   └── sources.json                # 47 fuentes monitorizadas
├── scripts/
│   ├── main.py                     # Orquestador (scheduled / manual)
│   ├── config_loader.py            # Carga de settings y fuentes
│   ├── fetcher.py                  # RSS + Google News + filtro temporal
│   ├── classifier.py               # Gemini + fallback heurístico
│   ├── renderer.py                 # Jinja2 + WeasyPrint
│   ├── history.py                  # Histórico, dedupe, índice de búsqueda
│   └── emailer.py                  # Correo SMTP con PDF adjunto
├── templates/
│   ├── dossier.html.j2             # Dossier ejecutivo (HTML/PDF)
│   └── email.html.j2               # Plantilla corporativa de correo
├── web/                            # Dashboard (se publica en gh-pages)
│   ├── index.html
│   ├── css/dashboard.css
│   └── js/dashboard.js
└── requirements.txt
```

---

*Generado automáticamente mediante IA · Uso interno Presidencia RENFE.*
