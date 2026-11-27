/* Panel Administrativo · Dossier Presidencia RENFE */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const DOT = { ROJO: "🔴", AMARILLO: "🟡", VERDE: "🟢" };

async function fetchJSON(url, fallback) {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return fallback;
    return await r.json();
  } catch {
    return fallback;
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* ------------------------------ Tabs ------------------------------ */
$$(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
  })
);

/* ------------------------------ Estado ------------------------------ */
let REPORTS = [];
let SEARCH_INDEX = [];

async function init() {
  const [status, reports, index, settings] = await Promise.all([
    fetchJSON("data/status.json", null),
    fetchJSON("data/reports.json", []),
    fetchJSON("data/search_index.json", []),
    fetchJSON("data/settings.json", {}),
  ]);
  REPORTS = reports || [];
  SEARCH_INDEX = index || [];

  renderStatus(status);
  renderRecientes();
  renderHistorico();
  renderBuscador();
  renderConfig(settings || {}, status);
}

function renderStatus(status) {
  if (!status) {
    $("#kpi-hora").textContent = "07:05";
    $("#kpi-ultima").textContent = "Sin ejecuciones";
    $("#kpi-proxima").textContent = "—";
    $("#kpi-total").textContent = "0";
    $("#hint-generar").textContent =
      "Aún no hay datos: el primer informe se generará en la próxima ejecución programada.";
    return;
  }
  $("#kpi-hora").textContent = status.scheduled_time || "—";
  const last = status.last_run;
  if (last) {
    $("#kpi-ultima").textContent = last.created || "—";
    $("#kpi-ultima-detalle").textContent =
      `${last.tipo} · ${last.total} noticias`;
    $("#kpi-rojo").textContent = last.rojo ?? "—";
    $("#kpi-amarillo").textContent = last.amarillo ?? "—";
    $("#kpi-verde").textContent = last.verde ?? "—";
    if (last.url) $("#btn-ultimo").href = last.url;
  }
  $("#kpi-proxima").textContent = status.next_run || "—";
  $("#kpi-total").textContent = status.total_reports ?? REPORTS.length;
  $("#footer-updated").textContent = "Actualizado: " + (status.generated_at || "—");

  if (status.repo_url) {
    $("#btn-generar").href =
      status.repo_url + "/actions/workflows/dossier.yml";
    $("#hint-generar").textContent =
      "Abrirá GitHub Actions: pulse «Run workflow» para lanzar el informe manual.";
    $("#link-settings").href =
      status.repo_url + "/edit/main/config/settings.json";
  }
}

/* ------------------------------ Tablas ------------------------------ */
function filaInforme(r, conEnlaces) {
  const td = (c) => `<td>${c}</td>`;
  let cols =
    td(`<span class="pill ${esc(r.tipo)}">${esc(r.tipo)}</span>`) +
    td(esc(r.created)) +
    td(`${esc(r.date_from)} → ${esc(r.date_to)}`) +
    td(r.rojo) + td(r.amarillo) + td(r.verde) + td(`<strong>${r.total}</strong>`);
  if (conEnlaces) {
    cols += td(`<a href="${esc(r.url_html)}" target="_blank">HTML</a>`);
    cols += td(r.url_pdf ? `<a href="${esc(r.url_pdf)}" target="_blank">PDF</a>` : "—");
  } else {
    cols += td(`<a href="${esc(r.url_html)}" target="_blank">Abrir</a>`);
  }
  return `<tr>${cols}</tr>`;
}

function renderRecientes() {
  const tbody = $("#tabla-recientes tbody");
  const rows = REPORTS.slice(0, 10).map((r) => filaInforme(r, false)).join("");
  tbody.innerHTML = rows || `<tr><td colspan="8" class="empty">Todavía no hay informes.</td></tr>`;
}

function renderHistorico() {
  const fecha = $("#hist-fecha").value;
  const tipo = $("#hist-tipo").value;
  const filtrados = REPORTS.filter((r) => {
    if (fecha && !(r.created || "").startsWith(fecha)) return false;
    if (tipo && r.tipo !== tipo) return false;
    return true;
  });
  const tbody = $("#tabla-historico tbody");
  tbody.innerHTML =
    filtrados.map((r) => filaInforme(r, true)).join("") ||
    `<tr><td colspan="9" class="empty">Sin resultados.</td></tr>`;
}

["hist-fecha", "hist-tipo"].forEach((id) =>
  document.addEventListener("input", (e) => {
    if (e.target.id === id) renderHistorico();
  })
);
document.addEventListener("click", (e) => {
  if (e.target.id === "hist-limpiar") {
    $("#hist-fecha").value = "";
    $("#hist-tipo").value = "";
    renderHistorico();
  }
});

/* ------------------------------ Buscador ------------------------------ */
function renderBuscador() {
  const texto = ($("#buscar-texto").value || "").toLowerCase().trim();
  const fecha = $("#buscar-fecha").value;
  const color = $("#buscar-color").value;

  const res = SEARCH_INDEX.filter((n) => {
    if (color && n.color !== color) return false;
    if (fecha && !(n.fecha || "").startsWith(fecha)) return false;
    if (texto) {
      const hay = `${n.titular} ${n.medio} ${n.resumen}`.toLowerCase();
      if (!hay.includes(texto)) return false;
    }
    return true;
  }).slice(0, 100);

  $("#buscar-count").textContent = `${res.length} resultado(s)`;
  $("#resultados").innerHTML =
    res
      .map(
        (n) => `
      <div class="result ${esc(n.color)}">
        <h4>${DOT[n.color] || "⚪"} <a href="${esc(n.url_noticia)}" target="_blank" rel="noopener">${esc(n.titular)}</a></h4>
        <div class="r-meta">${esc(n.medio)} · ${esc(n.fecha)} · Prioridad ${n.prioridad}/100</div>
        <div class="r-resumen">${esc(n.resumen)}</div>
        <div class="r-informe">Informe: <a href="${esc(n.url_informe)}" target="_blank">${esc(n.informe)}</a></div>
      </div>`
      )
      .join("") ||
    `<div class="empty">Sin resultados. Pruebe con otros términos.</div>`;
}

["buscar-texto", "buscar-fecha", "buscar-color"].forEach((id) =>
  document.addEventListener("input", (e) => {
    if (e.target.id === id) renderBuscador();
  })
);
document.addEventListener("click", (e) => {
  if (e.target.id === "buscar-limpiar") {
    $("#buscar-texto").value = "";
    $("#buscar-fecha").value = "";
    $("#buscar-color").value = "";
    renderBuscador();
  }
});

/* ------------------------------ Configuración ------------------------------ */
function renderConfig(settings, status) {
  const filas = [
    ["Hora programada (Europe/Madrid)", settings.scheduled_time || (status && status.scheduled_time) || "07:05"],
    ["Email administrador", settings.admin_email || "—"],
    ["Asunto del correo", settings.email_subject || "[DOSSIER PRESIDENCIA RENFE]"],
    ["Envío de correo", settings.email_enabled === false ? "Desactivado" : "Activado"],
    ["Máx. noticias por informe", settings.max_news_per_report ?? 40],
    ["Palabras clave", (settings.keywords || []).join(", ")],
    ["Fuentes habilitadas",
      (settings.enabled_sources && settings.enabled_sources.length)
        ? settings.enabled_sources.join(", ")
        : "Todas"],
    ["URL pública (GitHub Pages)", (status && status.pages_url) || settings.pages_url || "—"],
    ["Clave Gemini API", "•••••••• (configurada en secreto o en settings.json)"],
  ];
  $("#tabla-config tbody").innerHTML = filas
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`)
    .join("");
}

init();
