// Notificación no bloqueante (reemplaza alert() para avisos que no requieren
// interacción del usuario, como el fin de una sincronización automática).
// Nombre distinto a propósito: fbb-app.js ya define su propio showToast()
// (global, para el módulo FBB DATA) y se carga después de este archivo, así
// que un showToast() aquí quedaría tapado por el suyo.
function showSyncToast(message, type = "success", duration = 6000) {
    let container = document.getElementById("sync-toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "sync-toast-container";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "error" ? "⚠️" : "✅";
    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg"></span><button class="toast-close" aria-label="Cerrar">×</button>`;
    toast.querySelector(".toast-msg").textContent = message;
    const remove = () => {
        toast.classList.add("toast-hide");
        setTimeout(() => toast.remove(), 250);
    };
    toast.querySelector(".toast-close").addEventListener("click", remove);
    container.appendChild(toast);
    setTimeout(remove, duration);
}

// Variables Globales
let workOrders = [];
let filteredOrders = [];
let currentPage = 1;
const rowsPerPage = 10;

// Variables de Gráficos (ChartJS instances)
let slaChartInstance = null;
let branchChartInstance = null;
let reasonsChartInstance = null;

// Elementos del DOM
const btnSync = document.getElementById("btn-sync");
const currentTimeBadge = document.getElementById("current-time-badge");
const tableBody = document.getElementById("table-body");
const tableSearch = document.getElementById("table-search");
const filterType = document.getElementById("filter-type");
const filterCD = document.getElementById("filter-cd");
const btnExportTable = document.getElementById("btn-export-table");

// Paginación
const btnPrev = document.getElementById("btn-prev");
const btnNext = document.getElementById("btn-next");
const pagStart = document.getElementById("pag-start");
const pagEnd = document.getElementById("pag-end");
const pagTotal = document.getElementById("pag-total");

// Modal
const detailModal = document.getElementById("detail-modal");
const btnModalClose = document.getElementById("modal-close");

// Inicialización de la Aplicación
document.addEventListener("DOMContentLoaded", () => {
    initApp();
    setupEventListeners();
});

async function initApp() {
    updateTimeBadge();
    setInterval(updateTimeBadge, 1000);

    // Cargar datos iniciales
    fetchStats();
    fetchNimsReport();
    fetchBranchSlaReport();
    fetchTopologyAlarms();
    fetchAlarmScanStatus();
    _pollOltLoopStatus();
    setInterval(fetchTopologyAlarms, 60000);
    setInterval(fetchAlarmScanStatus, 60000);
    setInterval(_pollOltLoopStatus, 30000);

    // Los bucles automáticos de server.py (_auto_excel_sync_loop / _auto_deploy_pending_loop)
    // pueden arrancar un sync o una actualización de despliegues sin que el usuario toque
    // ningún botón -sin esto, el cronómetro/estado solo aparecían si el usuario disparaba
    // la acción él mismo o recargaba la página a mitad de una corrida. Se revisa cada 10s
    // si hay algo corriendo que esta pestaña todavía no esté siguiendo.
    setInterval(_watchAutoTriggeredSync, 10000);
    setInterval(_watchAutoTriggeredDeploy, 10000);

    // El filtro de mes(es) de tipificación se llena a partir de las WOs cargadas,
    // así que se espera a que terminen de llegar antes de poblarlo y disparar el reporte
    await fetchWorkOrders();
    populateTypificationMonthFilter();
    fetchTypificationReport();
}

function updateTimeBadge() {
    const now = new Date();
    // Forzar el formato local legible
    const options = { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric',
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        hour12: false
    };
    currentTimeBadge.textContent = now.toLocaleString('es-PE', options);
}

// Configurar los Listeners de Eventos
const PAGE_TITLES = {
    dashboard: ["Averías Pendientes — Avance SLA y Tipificación", "Monitoreo en tiempo real de órdenes de trabajo de GNOC desde Junio 2026"],
    "deploy-pending": ["Despliegues Pendientes", "WO de instalación pendientes por branch — datos de deploy ant (Tableau Deploy WO Pending)"],
    orders: ["Órdenes de Trabajo", "Listado completo de work orders GNOC con filtros y exportación"],
    nims: ["Averías por Caja (NIMS)", "Reporte de órdenes agrupadas por topología de red (Sitio/XB/HB/Caja)"],
    topology: ["Inspector de Topología", "Validación en vivo GPON + BRAS por Site/OLT/HUBBOX"],
    olt: ["Auditoría OLT", "Estado de ONUs, puertos caídos y cortes masivos detectados en tiempo real"],
    kpi: ["Reporte KPI", "WO Incident Report — calculado en vivo desde las WOs de GNOC ya descargadas"],
    "daily-report": ["Reporte Diario", "Instalaciones diarias/semanales, averías pendientes y cierres por branch — GNOC + FBB DATA"],
    credentials: ["Credenciales", "Usuario y contraseña de los portales que usa la sincronización (GNOC, Tableau, CNOC)"],
    "fbb-dashboard": ["Panel de Control", "Visualización general de la red de banda ancha fija."],
    "fbb-zones": ["Zonas Activas", "Administración y estado de las zonas FBB a nivel nacional."],
    "fbb-boxes": ["Lista de Cajas", "Catálogo de cajas de distribución y mapeo de coordenadas."],
    "fbb-staff": ["Personal (Staff)", "Administración del personal asignado a zonas y OLTs."],
    "fbb-partner-capacity": ["Capacidad de Partners", "Resumen y análisis de carga de los socios y equipos asignados."],
    "fbb-incidents": ["Incidentes y Averías", "Reporte detallado de volumen de averías y clientes afectados."],
    "fbb-deployments": ["Despliegues y SLA", "Análisis de eficiencia de partners, branch y capacidad operativa de los equipos de despliegue."]
};

// Página de Credenciales: cargar estado actual y guardar cambios
async function fetchCredentials() {
    try {
        const response = await fetch("/api/settings/credentials");
        const data = await response.json();
        document.querySelectorAll(".cred-card").forEach(card => {
            const system = card.dataset.system;
            const info = data[system];
            if (!info) return;
            card.querySelector(".cred-username").textContent = info.username || "(sin configurar)";
            const passEl = card.querySelector(".cred-pass-status");
            if (info.has_password) {
                passEl.textContent = "✓ Configurada";
                passEl.className = "cred-pass-status ok";
            } else {
                passEl.textContent = "✗ No configurada";
                passEl.className = "cred-pass-status missing";
            }
        });
    } catch (err) {
        console.error("Error al cargar credenciales:", err);
    }
}

async function saveCredentials(card) {
    const system = card.dataset.system;
    const username = card.querySelector(".cred-username-input").value.trim();
    const password = card.querySelector(".cred-password-input").value;
    const feedback = card.querySelector(".cred-feedback");
    const btn = card.querySelector(".cred-save-btn");

    if (!username && !password) {
        feedback.textContent = "Ingresa un usuario y/o contraseña nuevos.";
        feedback.className = "cred-feedback error";
        return;
    }

    btn.disabled = true;
    feedback.textContent = "";
    feedback.className = "cred-feedback";

    try {
        const response = await fetch("/api/settings/credentials", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ system, username, password })
        });
        const result = await response.json();
        feedback.textContent = result.message;
        feedback.className = `cred-feedback ${result.success ? "success" : "error"}`;
        if (result.success) {
            card.querySelector(".cred-username-input").value = "";
            card.querySelector(".cred-password-input").value = "";
            await fetchCredentials();
        }
        const banner = document.getElementById("cred-sync-blocked-banner");
        if (banner) banner.style.display = (!result.success && (result.message || "").includes("sincronización activa")) ? "flex" : "none";
    } catch (err) {
        feedback.textContent = "Error de conexión al guardar.";
        feedback.className = "cred-feedback error";
    } finally {
        btn.disabled = false;
    }
}

// Línea "Última actualización" del header: cada página muestra la suya (Excel sync para
// la mayoría, último escaneo continuo para Auditoría OLT), en vez de un solo timestamp
// genérico que confundía (ej. mostrar la hora del sync de Excel estando en Auditoría OLT,
// que es un proceso totalmente aparte).
let _lastExcelSyncText = "Cargando...";
function _setHeaderLastUpdate(iconClass, label, valueText) {
    const info = document.getElementById("last-sync-info");
    if (!info) return;
    info.innerHTML = `<i class="${iconClass}"></i> ${label}: <span id="last-sync-value">${valueText}</span>`;
}

function switchPage(pageKey) {
    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.toggle("active", item.dataset.page === pageKey);
    });
    document.querySelectorAll(".page-section").forEach(section => {
        section.classList.toggle("active", section.id === `page-${pageKey}`);
    });
    const titles = PAGE_TITLES[pageKey];
    if (titles) {
        document.getElementById("page-title").textContent = titles[0];
        document.getElementById("page-subtitle").textContent = titles[1];
    }
    window.scrollTo(0, 0);

    if (pageKey === "olt") {
        _setHeaderLastUpdate("fa-solid fa-tower-broadcast", "Último escaneo OLT", "Cargando...");
    } else {
        _setHeaderLastUpdate("fa-regular fa-clock", "Última sincronización", _lastExcelSyncText);
    }

    // "Sincronizar Excel" (botón, cronómetro, rango de meses) es información de Averías
    // Pendientes específicamente -antes aparecía en TODAS las páginas por vivir en el
    // header global, lo que confundía (ej. su alerta de error aparecía en Despliegues
    // Pendientes sin tener nada que ver). Cada pestaña debe mostrar solo lo suyo.
    const enDashboard = pageKey === "dashboard";
    const btnSyncEl = document.getElementById("btn-sync");
    const rangePickerEl = document.querySelector(".sync-range-picker");
    if (btnSyncEl) btnSyncEl.style.display = enDashboard ? "" : "none";
    if (rangePickerEl) rangePickerEl.style.display = enDashboard ? "" : "none";

    // sync-timer-badge tiene su PROPIA lógica de visibilidad (se muestra/oculta según si
    // hay una sincronización en curso, ver startSyncTimer/stopSyncTimer) -no se puede
    // pisar con un simple "" al volver a la página o aparecería vacío aunque no haya
    // ningún sync activo. Se recuerda el estado real que tenía antes de ocultarlo.
    const timerBadgeEl = document.getElementById("sync-timer-badge");
    if (timerBadgeEl) {
        if (enDashboard) {
            if (timerBadgeEl.dataset.hiddenForNav === "1") {
                timerBadgeEl.style.display = timerBadgeEl.dataset.prevDisplay || "none";
                delete timerBadgeEl.dataset.hiddenForNav;
            }
        } else if (timerBadgeEl.style.display !== "none") {
            timerBadgeEl.dataset.prevDisplay = timerBadgeEl.style.display;
            timerBadgeEl.dataset.hiddenForNav = "1";
            timerBadgeEl.style.display = "none";
        }
    }

    if (pageKey === "credentials") {
        fetchCredentials();
    }

    if (pageKey === "olt") {
        _oltPageActive = true;
        _checkEmsStatus();
        _pollOltLoopStatus();
        _loadOltCortes();
        _loadOltResumen();
        if (_oltAutoRefresh) clearInterval(_oltAutoRefresh);
        _oltAutoRefresh = setInterval(() => {
            if (_oltPageActive) {
                _pollOltLoopStatus();
                _loadOltCortes();
                _loadOltResumen();
            }
        }, 15000);
    } else {
        _oltPageActive = false;
        if (_oltAutoRefresh) {
            clearInterval(_oltAutoRefresh);
            _oltAutoRefresh = null;
        }
    }
}

const ALARM_SEVERITY_LABEL = {
    critical: '<span class="badge red">🔴 Crítica</span>',
    media: '<span class="badge orange">🟠 Media</span>',
    caja: '<span class="badge yellow">🟡 Caja</span>'
};

async function fetchTopologyAlarms() {
    const tbody = document.getElementById("alarms-table-body");
    if (!tbody) return;
    const severity = document.getElementById("alarm-severity-filter")?.value || "";
    const branch = document.getElementById("alarm-branch-filter")?.value || "";
    const site = document.getElementById("alarm-site-filter")?.value.trim() || "";
    try {
        const response = await fetch(`/api/topology/alarms?severity=${encodeURIComponent(severity)}&branch=${encodeURIComponent(branch)}&site=${encodeURIComponent(site)}&limit=200`);
        const data = await response.json();
        if (!data.success) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error: ${data.error}</td></tr>`;
            return;
        }
        if (data.alarms.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Sin alarmas registradas (o aún no corrió el primer escaneo).</td></tr>';
            return;
        }
        tbody.innerHTML = data.alarms.map(a => {
            // El box_code completo es "SITE-XB0N-HB0N-CODIGO"; se extrae el OLT (N de XB0N)
            // para poder re-escanear esa OLT completa al hacer click en la alarma.
            const xbMatch = a.box_code.match(/-XB0(\d)-/);
            const olt = xbMatch ? xbMatch[1] : "1";
            return `
            <tr class="clickable-row" style="cursor:pointer;" onclick="openAlarmDetail('${a.site}', '${olt}', '${(a.branch || '').replace(/'/g, "")}')">
                <td>${a.scan_time}</td>
                <td>${ALARM_SEVERITY_LABEL[a.severity] || a.severity}</td>
                <td>${a.branch || "-"}</td>
                <td>${a.site}</td>
                <td style="font-family:monospace;">${a.box_code}</td>
                <td>${a.act}/${a.online}/${a.not_online}</td>
                <td>${a.message}</td>
            </tr>
        `;
        }).join("");
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error de conexión: ${err}</td></tr>`;
    }
}

let alarmModalInterval = null;

// Abre el modal de detalle de alarma y dispara un escaneo en vivo de toda la OLT
// (las 4 HB) para que el usuario vea el panorama completo del site, no solo la
// caja puntual que generó la alarma.
window.openAlarmDetail = function(site, olt, branch) {
    const modal = document.getElementById("alarm-detail-modal");
    if (!modal) return;

    document.getElementById("alarm-modal-title").textContent = `SITE ${site} | OLT ${olt}`;
    document.getElementById("alarm-modal-branch").textContent = branch || "Sin identificar";
    document.getElementById("alarm-modal-total-act").textContent = "-";
    document.getElementById("alarm-modal-total-online").textContent = "-";
    document.getElementById("alarm-modal-total-offline").textContent = "-";
    document.getElementById("alarm-modal-total-never").textContent = "-";
    document.getElementById("alarm-modal-grid").innerHTML = "";
    const loading = document.getElementById("alarm-modal-loading");
    loading.style.display = "block";
    loading.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Escaneando toda la OLT en vivo (puede tardar varios minutos)...';

    modal.classList.add("active");
    if (alarmModalInterval) clearInterval(alarmModalInterval);

    fetch(`/api/topology/scan/start?site=${encodeURIComponent(site)}&olt=${encodeURIComponent(olt)}&hubbox=Todas`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                loading.innerHTML = `<span class="text-danger">Error: ${data.error}</span>`;
                return;
            }
            alarmModalInterval = setInterval(async () => {
                try {
                    const response = await fetch("/api/topology/scan/status");
                    const status = await response.json();
                    if (status.state === "running" && status.total > 0) {
                        loading.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Consultando BRAS en vivo... (${status.checked}/${status.total} cuentas)`;
                    } else if (status.state === "done") {
                        clearInterval(alarmModalInterval);
                        loading.style.display = "none";
                        document.getElementById("alarm-modal-total-act").textContent = status.result.totals.act;
                        document.getElementById("alarm-modal-total-online").textContent = status.result.totals.online;
                        document.getElementById("alarm-modal-total-offline").textContent = status.result.totals.not_online;
                        document.getElementById("alarm-modal-total-never").textContent = status.result.totals.nunca_online;
                        document.getElementById("alarm-modal-grid").innerHTML = buildTopologyGridHtml(status.result);
                    } else if (status.state === "error") {
                        clearInterval(alarmModalInterval);
                        loading.innerHTML = `<span class="text-danger">Error: ${status.error}</span>`;
                    }
                } catch (err) {
                    console.error("Error consultando estado del escaneo (modal de alarma):", err);
                }
            }, 2000);
        })
        .catch(err => {
            loading.innerHTML = `<span class="text-danger">Error de conexión: ${err}</span>`;
        });
};

async function fetchAlarmScanStatus() {
    const el = document.getElementById("alarm-scan-status-text");
    if (!el) return;
    try {
        const response = await fetch("/api/topology/alarms/status");
        const s = await response.json();
        if (s.state === "running") {
            el.textContent = `Escaneando ahora mismo... ${s.checked}/${s.total} cajas muestreadas.`;
        } else if (s.last_run) {
            const durMin = s.last_duration_sec ? Math.round(s.last_duration_sec / 60) : "?";
            el.textContent = `Último escaneo completo: ${s.last_run} (tardó ~${durMin} min). Próximo apenas se cumplan 3h desde el inicio del anterior.`;
        } else {
            el.textContent = "Escaneo automático cada ~3h de todas las cajas del país (muestreo + confirmación). Aún no corre el primero.";
        }
    } catch (err) {
        el.textContent = "No se pudo obtener el estado del escaneo de alarmas.";
    }
}

function setupEventListeners() {
    // Navegación entre páginas (sidebar)
    document.querySelectorAll(".nav-item").forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            switchPage(item.dataset.page);
        });
    });

    // Sincronización
    btnSync.addEventListener("click", triggerSync);

    // Credenciales
    document.querySelectorAll(".cred-card .cred-save-btn").forEach(btn => {
        btn.addEventListener("click", () => saveCredentials(btn.closest(".cred-card")));
    });

    // Búsqueda y Filtrado
    tableSearch.addEventListener("input", filterData);
    filterType.addEventListener("change", filterData);
    filterCD.addEventListener("change", filterData);

    // Filtro de mes(es) para Tipificación por Motivo de Cierre (dropdown custom con checkboxes)
    const monthPicker = document.getElementById("typification-month-picker");
    const monthToggle = document.getElementById("typification-month-toggle");
    if (monthPicker && monthToggle) {
        monthToggle.addEventListener("click", (e) => {
            e.stopPropagation();
            monthPicker.classList.toggle("open");
        });
        document.addEventListener("click", (e) => {
            if (!monthPicker.contains(e.target)) {
                monthPicker.classList.remove("open");
            }
        });
    }

    // Paginación
    btnPrev.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });
    btnNext.addEventListener("click", () => {
        if (currentPage * rowsPerPage < filteredOrders.length) {
            currentPage++;
            renderTable();
        }
    });

    // Cerrar Modal
    btnModalClose.addEventListener("click", closeModal);
    window.addEventListener("click", (e) => {
        if (e.target === detailModal) closeModal();
    });

    // Cerrar Diagnóstico Modal
    const btnDiagModalClose = document.getElementById("diag-modal-close");
    if (btnDiagModalClose) {
        btnDiagModalClose.addEventListener("click", closeDiagModal);
    }
    const diagnosticsModal = document.getElementById("diagnostics-modal");
    window.addEventListener("click", (e) => {
        if (e.target === diagnosticsModal) closeDiagModal();
    });

    // Cerrar modal de detalle de alarma
    const closeAlarmModal = () => {
        const modal = document.getElementById("alarm-detail-modal");
        if (modal) modal.classList.remove("active");
        if (alarmModalInterval) clearInterval(alarmModalInterval);
    };
    const btnAlarmModalClose = document.getElementById("alarm-modal-close");
    if (btnAlarmModalClose) btnAlarmModalClose.addEventListener("click", closeAlarmModal);
    const alarmDetailModal = document.getElementById("alarm-detail-modal");
    window.addEventListener("click", (e) => {
        if (e.target === alarmDetailModal) closeAlarmModal();
    });

    // Exportar Excel
    btnExportTable.addEventListener("click", () => {
        const searchVal = tableSearch.value;
        const typeVal = filterType.value;
        const cdVal = filterCD.value;
        
        let filename = "listado_ordenes_trabajo.xlsx";
        if (searchVal || typeVal !== "all" || cdVal !== "all") {
            filename = "listado_ordenes_filtradas.xlsx";
        }
        
        const exportUrl = `/api/work_orders/export/${filename}?search=${encodeURIComponent(searchVal)}&type=${typeVal}&cd=${encodeURIComponent(cdVal)}`;
        
        // Crear un enlace temporal para forzar la descarga con nombre y extensión correcta
        const link = document.createElement("a");
        link.href = exportUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    // Alarmas de Red (todos los sites)
    const btnRefreshAlarms = document.getElementById("btn-refresh-alarms");
    const alarmSeverityFilter = document.getElementById("alarm-severity-filter");
    const alarmBranchFilter = document.getElementById("alarm-branch-filter");
    const alarmSiteFilter = document.getElementById("alarm-site-filter");
    if (btnRefreshAlarms) btnRefreshAlarms.addEventListener("click", () => { fetchTopologyAlarms(); fetchAlarmScanStatus(); });
    if (alarmSeverityFilter) alarmSeverityFilter.addEventListener("change", fetchTopologyAlarms);
    if (alarmBranchFilter) alarmBranchFilter.addEventListener("change", fetchTopologyAlarms);
    if (alarmSiteFilter) {
        let alarmSiteDebounce = null;
        alarmSiteFilter.addEventListener("input", () => {
            clearTimeout(alarmSiteDebounce);
            alarmSiteDebounce = setTimeout(fetchTopologyAlarms, 350);
        });
    }

    // Inspector Topología: escaneo en vivo GPON + BRAS
    const btnTopoScan = document.getElementById("btn-topo-scan");
    const topoSiteInput = document.getElementById("topo-site-input");
    if (btnTopoScan) {
        btnTopoScan.addEventListener("click", scanTopologyLive);
    }
    if (topoSiteInput) {
        topoSiteInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                scanTopologyLive();
            }
        });
    }
}

let syncInterval = null;
let syncTimerInterval = null;
let syncStartTime = null;

const syncTimerBadge = document.getElementById("sync-timer-badge");
const syncTimerText = document.getElementById("sync-timer-text");

function startSyncTimer() {
    syncStartTime = Date.now();
    syncTimerBadge.style.display = "inline-flex";
    syncTimerBadge.className = "timer-badge";
    syncTimerText.textContent = "00:00";
    
    if (syncTimerInterval) clearInterval(syncTimerInterval);
    syncTimerInterval = setInterval(() => {
        const elapsedSeconds = Math.floor((Date.now() - syncStartTime) / 1000);
        const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
        const secs = String(elapsedSeconds % 60).padStart(2, '0');
        syncTimerText.textContent = `${mins}:${secs}`;
    }, 1000);
}

function stopSyncTimer(isSuccess = true) {
    if (syncTimerInterval) {
        clearInterval(syncTimerInterval);
        syncTimerInterval = null;
    }
    if (syncStartTime) {
        const totalSeconds = Math.floor((Date.now() - syncStartTime) / 1000);
        const mins = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const secs = String(totalSeconds % 60).padStart(2, '0');
        syncTimerText.textContent = `${mins}:${secs}`;
    }
    if (isSuccess) {
        syncTimerBadge.className = "timer-badge completed";
    } else {
        syncTimerBadge.className = "timer-badge error";
    }
}

let deployTimerInterval = null;
let deployStartTime = null;

function startDeployTimer() {
    const badge = document.getElementById("deploy-timer-badge");
    const text = document.getElementById("deploy-timer-text");
    if (!badge || !text) return;
    deployStartTime = Date.now();
    badge.style.display = "inline-flex";
    badge.className = "timer-badge";
    text.textContent = "00:00";

    if (deployTimerInterval) clearInterval(deployTimerInterval);
    deployTimerInterval = setInterval(() => {
        const elapsedSeconds = Math.floor((Date.now() - deployStartTime) / 1000);
        const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
        const secs = String(elapsedSeconds % 60).padStart(2, '0');
        text.textContent = `${mins}:${secs}`;
    }, 1000);
}

function stopDeployTimer(isSuccess = true) {
    const badge = document.getElementById("deploy-timer-badge");
    const text = document.getElementById("deploy-timer-text");
    if (deployTimerInterval) {
        clearInterval(deployTimerInterval);
        deployTimerInterval = null;
    }
    if (!badge || !text) return;
    if (deployStartTime) {
        const totalSeconds = Math.floor((Date.now() - deployStartTime) / 1000);
        const mins = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const secs = String(totalSeconds % 60).padStart(2, '0');
        text.textContent = `${mins}:${secs}`;
    }
    badge.className = isSuccess ? "timer-badge completed" : "timer-badge error";
}

// Rango de meses a sincronizar (GNOC): se persiste en localStorage para que la elección
// se mantenga entre sincronizaciones sin tener que volver a elegirla cada vez.
const RANGE_LS_KEY = "gnocSyncMonthRange";
const inputFromMonth = document.getElementById("sync-from-month");
const inputToMonth = document.getElementById("sync-to-month");
const btnRangeClear = document.getElementById("btn-sync-range-clear");

const MONTH_NAMES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

// Llena los selects "Desde"/"Hasta" con los últimos 24 meses (más reciente primero) más la
// opción "Automático" arriba, igual de simple que el selector de meses de Tipificación.
function populateSyncMonthSelects() {
    const now = new Date();
    const options = ['<option value="">Automático</option>'];
    for (let i = 0; i < 24; i++) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const label = `${MONTH_NAMES_ES[d.getMonth()]} ${yyyy}`;
        options.push(`<option value="${yyyy}-${mm}">${label}</option>`);
    }
    const html = options.join("");
    inputFromMonth.innerHTML = html;
    inputToMonth.innerHTML = html;
}

function loadSyncRange() {
    try {
        const saved = JSON.parse(localStorage.getItem(RANGE_LS_KEY) || "{}");
        if (saved.from) inputFromMonth.value = saved.from;
        if (saved.to) inputToMonth.value = saved.to;
    } catch (e) { /* ignore */ }
}

function saveSyncRange() {
    localStorage.setItem(RANGE_LS_KEY, JSON.stringify({
        from: inputFromMonth.value || "",
        to: inputToMonth.value || ""
    }));
}

if (inputFromMonth && inputToMonth) {
    populateSyncMonthSelects();
    loadSyncRange();
    inputFromMonth.addEventListener("change", saveSyncRange);
    inputToMonth.addEventListener("change", saveSyncRange);
}
if (btnRangeClear) {
    btnRangeClear.addEventListener("click", () => {
        inputFromMonth.value = "";
        inputToMonth.value = "";
        saveSyncRange();
    });
}

// Consumir API: Sincronizar reporte de forma asíncrona
async function triggerSync() {
    btnSync.disabled = true;
    btnSync.classList.add("loading");
    btnSync.querySelector("span").textContent = "Iniciando descarga...";

    startSyncTimer();

    try {
        const fromMonth = inputFromMonth ? inputFromMonth.value : "";
        const toMonth = inputToMonth ? inputToMonth.value : "";
        const response = await fetch("/api/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ from_month: fromMonth, to_month: toMonth })
        });
        const result = await response.json();
        
        if (result.success) {
            pollSyncStatus();
        } else {
            stopSyncTimer(false);
            resetSyncButton();
            // Si hay un proceso activo, ofrecer cancelarlo y reiniciar
            const isBusy = result.message && result.message.includes("activa");
            if (isBusy) {
                const wantsCancel = confirm(
                    "⚠️ Ya hay una sincronización en curso (puede haberse quedado colgada).\n\n" +
                    "¿Deseas cancelarla y empezar una nueva sincronización?"
                );
                if (wantsCancel) {
                    try {
                        await fetch("/api/sync/cancel", { method: "POST" });
                    } catch (e) { /* ignore */ }
                    // Intentar sincronizar de nuevo
                    await triggerSync();
                }
            } else {
                alert("Error al iniciar: " + result.message);
            }
        }
    } catch (error) {
        console.error("Error en sync:", error);
        alert("Ocurrió un error al iniciar la sincronización.");
        stopSyncTimer(false);
        resetSyncButton();
    }
}

function resetSyncButton() {
    btnSync.disabled = false;
    btnSync.classList.remove("loading");
    btnSync.querySelector("span").textContent = "Sincronizar Excel";
}

async function _watchAutoTriggeredSync() {
    if (syncInterval) return; // ya se está siguiendo (manual o ya detectado antes)
    try {
        const r = await fetch("/api/sync/status");
        const status = await r.json();
        if (status.state === "downloading" || status.state === "processing") {
            // Mismo setup que triggerSync(), pero disparado por el ciclo automático de
            // server.py en vez de un clic -así el botón/cronómetro se ven igual de cualquier forma.
            btnSync.disabled = true;
            btnSync.classList.add("loading");
            btnSync.querySelector("span").textContent = status.message || "Sincronizando...";
            startSyncTimer();
            pollSyncStatus();
        }
    } catch (e) { /* silencioso, se reintenta en el próximo tick */ }
}

function pollSyncStatus() {
    if (syncInterval) clearInterval(syncInterval);
    
    syncInterval = setInterval(async () => {
        try {
            const response = await fetch("/api/sync/status");
            const status = await response.json();
            
            if (status.state === "downloading" || status.state === "processing") {
                btnSync.querySelector("span").textContent = status.message || "Sincronizando...";
            } else if (status.state === "success") {
                clearInterval(syncInterval);
                syncInterval = null;
                btnSync.querySelector("span").textContent = "Actualizando vista...";

                // Recargar datos y gráficos tras éxito
                await fetchStats();
                await fetchWorkOrders();
                await fetchBranchSlaReport();
                await fetchTypificationReport();

                // Detener el cronómetro al finalizar la actualización completa de la vista
                stopSyncTimer(true);
                resetSyncButton();

                const durationTxt = syncTimerText.textContent;
                showSyncToast(`¡Sincronización completa en ${durationTxt}! La base de datos y gráficos se actualizaron correctamente.`, "success");
            } else if (status.state === "error") {
                clearInterval(syncInterval);
                syncInterval = null;
                stopSyncTimer(false);
                resetSyncButton();
                // Este alert() puede aparecer encima de CUALQUIER página del dashboard (sigue
                // corriendo en segundo plano aunque hayas navegado a otra sección) -- el prefijo
                // evita que se confunda con un error de otra parte, como Despliegues Pendientes.
                alert("Sincronización de Excel (GNOC/Tableau/NIMS/CNOC) falló:\n\n" + status.message);
            } else if (status.state === "idle") {
                clearInterval(syncInterval);
                syncInterval = null;
                resetSyncButton();
            }
        } catch (error) {
            console.error("Error al consultar el estado de la sincronización:", error);
        }
    }, 3000);
}

// Consumir API: Obtener Estadísticas
async function fetchStats() {
    try {
        const response = await fetch("/api/stats");
        const stats = await response.json();
        
        // Actualizar tarjetas de métricas
        document.getElementById("stat-total").textContent = stats.total_valid;
        document.getElementById("stat-24").textContent = stats.pending_intervals.under_24h;
        document.getElementById("stat-48").textContent = stats.pending_intervals.under_48h;
        document.getElementById("stat-72").textContent = stats.pending_intervals.under_72h;
        document.getElementById("stat-over72").textContent = stats.pending_intervals.over_72h;
        document.getElementById("stat-errors").textContent = stats.total_errors;

        // Fecha/hora de la última sincronización de Excel exitosa. Se cachea el texto ya
        // formateado (no solo se pinta) porque la página de Auditoría OLT pisa esta misma
        // línea del header con SU propia última actualización (ver _updateOltStatusUI);
        // al salir de esa página hay que poder restaurar este valor sin volver a pedirlo.
        if (stats.last_sync_at) {
            const [datePart, timePart] = stats.last_sync_at.split(" ");
            const [y, m, d] = datePart.split("-");
            _lastExcelSyncText = `${d}/${m}/${y} ${timePart}`;
        } else {
            _lastExcelSyncText = "Sin registro aún";
        }
        if (!_oltPageActive) _setHeaderLastUpdate("fa-regular fa-clock", "Última sincronización", _lastExcelSyncText);

        // Generar gráficos
        renderSlaChart(stats.pending_intervals);
        renderBranchChart(stats.branch_distribution);

        // Llenar selectores del filtro CD
        populateCdFilter(stats.cd_groups_distribution);
        
    } catch (error) {
        console.error("Error al obtener estadísticas:", error);
    }
}

// Llenar dinámicamente el selector del filtro CD
function populateCdFilter(cdGroups) {
    // Guardar valor seleccionado actual
    const currentVal = filterCD.value;
    
    // Limpiar select y agregar opción por defecto
    filterCD.innerHTML = '<option value="all">Todos los grupos (CD)</option>';
    
    cdGroups.forEach(item => {
        if (item.cd_group) {
            const option = document.createElement("option");
            option.value = item.cd_group;
            option.textContent = `${item.cd_group} (${item.count})`;
            filterCD.appendChild(option);
        }
    });
    
    // Restaurar valor seleccionado si existe en el nuevo listado
    filterCD.value = currentVal;
    if (filterCD.value !== currentVal) {
        filterCD.value = "all";
    }
}

// Consumir API: Obtener Listado de WOs
async function fetchWorkOrders() {
    try {
        tableBody.innerHTML = '<tr><td colspan="8" class="loading-cell">Cargando órdenes de trabajo...</td></tr>';
        
        const response = await fetch("/api/work_orders");
        workOrders = await response.json();
        
        filterData(); // Aplica filtrado inicial y renderiza la tabla
    } catch (error) {
        console.error("Error al cargar órdenes de trabajo:", error);
        tableBody.innerHTML = '<tr><td colspan="8" class="loading-cell text-red">Error al cargar datos desde el servidor.</td></tr>';
    }
}

// Lógica de Filtro Cliente (Instantánea)
function filterData() {
    const searchVal = tableSearch.value.toLowerCase().trim();
    const typeVal = filterType.value;
    const cdVal = filterCD.value;

    filteredOrders = workOrders.filter(order => {
        // 1. Filtro de búsqueda textual (incluye campos de Tableau)
        const matchesSearch = 
            order.wo_code.toLowerCase().includes(searchVal) ||
            (order.ft_technician && order.ft_technician.toLowerCase().includes(searchVal)) ||
            (order.cd_group && order.cd_group.toLowerCase().includes(searchVal)) ||
            (order.close_reason && order.close_reason.toLowerCase().includes(searchVal)) ||
            (order.wo_name && order.wo_name.toLowerCase().includes(searchVal)) ||
            (order.branch && order.branch.toLowerCase().includes(searchVal)) ||
            (order.connector_code && order.connector_code.toLowerCase().includes(searchVal));
            
        // 2. Filtro de tipo (Total vs Solo Pendientes vs Pendientes sin errores vs Errores)
        let matchesType = true;
        const statusLower = (order.wo_status || "").toLowerCase();
        const isPendingInGnoc = statusLower.includes("inprocessing") || statusLower.includes("pending") || !["close", "closed", "closed ft", "ft completed"].includes(statusLower);

        if (typeVal === "pending") {
            matchesType = isPendingInGnoc;
        } else if (typeVal === "valid") {
            matchesType = isPendingInGnoc && !order.is_error;
        } else if (typeVal === "error") {
            matchesType = order.is_error;
        }
        
        // 3. Filtro de CD
        const matchesCD = (cdVal === "all" || order.cd_group === cdVal);

        return matchesSearch && matchesType && matchesCD;
    });

    currentPage = 1; // Reiniciar a la primera página tras filtrar
    renderTable();
}

// Renderizar Tabla con Paginación
function renderTable() {
    tableBody.innerHTML = "";
    
    if (filteredOrders.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="11" class="loading-cell">No se encontraron órdenes de trabajo con los criterios de búsqueda.</td></tr>';
        updatePaginationUI(0, 0, 0);
        return;
    }

    const startIndex = (currentPage - 1) * rowsPerPage;
    const endIndex = Math.min(startIndex + rowsPerPage, filteredOrders.length);
    const pagedOrders = filteredOrders.slice(startIndex, endIndex);

    pagedOrders.forEach(order => {
        const tr = document.createElement("tr");
        
        // Asignar clases si es error
        if (order.is_error) {
            tr.classList.add("row-error");
        }
        
        // Badge de tiempo pendiente (o de resolución, si la WO ya está cerrada)
        const statusLowerRow = (order.wo_status || "").toLowerCase();
        const isClosedRow = ["close", "closed", "closed ft", "ft completed"].includes(statusLowerRow);

        let pendingBadgeClass = "green";
        if (order.pending_hours >= 72) {
            pendingBadgeClass = "red";
        } else if (order.pending_hours >= 48) {
            pendingBadgeClass = "orange";
        } else if (order.pending_hours >= 24) {
            pendingBadgeClass = "yellow";
        }

        let pendingBadge;
        if (order.is_error) {
            pendingBadge = `<span class="badge purple">Error (Bloqueado)</span>`;
        } else if (isClosedRow) {
            const resText = (order.resolution_hours !== null && order.resolution_hours !== undefined)
                ? `${order.resolution_hours} hrs para cerrar`
                : "Cerrada";
            const closedTxt = order.closed_time ? ` · ${order.closed_time}` : "";
            pendingBadge = `<span class="badge blue"><i class="fa-regular fa-circle-check"></i> ${resText}${closedTxt}</span>`;
        } else {
            pendingBadge = `<span class="badge ${pendingBadgeClass}"><i class="fa-regular fa-clock"></i> ${order.pending_hours} hrs</span>`;
        }

        // Badge de Clasificación/Motivo de cierre
        let reasonBadgeClass = "orange";
        if (order.is_error) reasonBadgeClass = "purple";
        else if (order.close_reason.includes("Recuperación")) reasonBadgeClass = "green";
        else if (order.close_reason.includes("Pendiente")) reasonBadgeClass = "yellow";
        
        const reasonBadge = `<span class="badge ${reasonBadgeClass}">${order.close_reason}</span>`;

        // Columna Estado
        const statusBadge = order.is_error
            ? `<span class="badge red">ERROR</span>`
            : `<span class="badge green">ACTIVA</span>`;

        // Datos de Tableau
        const branchBadge = order.branch 
            ? `<span class="badge blue">${order.branch}</span>` 
            : `<span class="text-muted">-</span>`;
            
        const warrantyBadge = order.warranty_period !== "" 
            ? `<span class="badge orange">${order.warranty_period} días</span>` 
            : `<span class="text-muted">-</span>`;
            
        const connectorTxt = order.connector_code || "-";

        tr.innerHTML = `
            <td><strong>${order.wo_code}</strong></td>
            <td>${branchBadge}</td>
            <td>${order.create_time}</td>
            <td>${order.cd_group || "-"}</td>
            <td>${order.ft_technician || "-"}</td>
            <td>${pendingBadge}</td>
            <td>${warrantyBadge}</td>
            <td><small style="font-family: monospace;">${connectorTxt}</small></td>
            <td>${reasonBadge}</td>
            <td>${statusBadge}</td>
        `;
        
        // Click para ver detalles
        tr.addEventListener("click", () => showDetails(order));
        
        tableBody.appendChild(tr);
    });

    updatePaginationUI(startIndex + 1, endIndex, filteredOrders.length);
}

// Actualizar Controles de Paginación
function updatePaginationUI(start, end, total) {
    pagStart.textContent = start;
    pagEnd.textContent = end;
    pagTotal.textContent = total;

    btnPrev.disabled = (currentPage === 1);
    btnNext.disabled = (currentPage * rowsPerPage >= total);
}

// Mostrar Detalle de la WO en Modal
function showDetails(order) {
    document.getElementById("modal-wo-code").textContent = order.wo_code;
    document.getElementById("modal-wo-name").textContent = order.wo_name || "-";
    document.getElementById("modal-wo-type").textContent = order.wo_type || "-";
    document.getElementById("modal-cd-group").textContent = order.cd_group || "-";
    document.getElementById("modal-ft-tech").textContent = order.ft_technician || "-";
    
    // Llenar metadatos de Tableau
    document.getElementById("modal-branch").textContent = order.branch || "Sin data en Tableau";
    document.getElementById("modal-warranty").textContent = order.warranty_period !== "" ? `${order.warranty_period} días` : "Sin data en Tableau";
    document.getElementById("modal-impl-test").textContent = order.implementation_test || "Sin data en Tableau";
    document.getElementById("modal-connector").textContent = order.connector_code || "Sin data en Tableau";
    document.getElementById("modal-act-status").textContent = order.act_status || "Sin data en Tableau";
    document.getElementById("modal-sub-status").textContent = order.sub_status || "Sin data en Tableau";

    document.getElementById("modal-description").textContent = order.description || "Sin descripción disponible.";
    document.getElementById("modal-create-time").textContent = order.create_time;
    
    const statusLowerModal = (order.wo_status || "").toLowerCase();
    const isClosedModal = ["close", "closed", "closed ft", "ft completed"].includes(statusLowerModal);

    let pendingText;
    if (order.is_error) {
        pendingText = "No aplica (Error de sistema bloqueante)";
    } else if (isClosedModal) {
        pendingText = (order.resolution_hours !== null && order.resolution_hours !== undefined)
            ? `${order.resolution_hours} horas de resolución`
            : "Cerrada (sin fecha de cierre registrada)";
    } else {
        pendingText = `${order.pending_hours} horas de retraso`;
    }
    document.getElementById("modal-pending-hours").textContent = pendingText;

    const closedTimeEl = document.getElementById("modal-closed-time");
    if (closedTimeEl) {
        closedTimeEl.textContent = order.closed_time || "-";
    }

    document.getElementById("modal-ft-comment").textContent = order.ft_comment || "Sin comentarios registrados por el técnico.";

    // Configurar badge de motivo en modal
    const reasonBadge = document.getElementById("modal-reason-badge");
    reasonBadge.textContent = order.close_reason;
    reasonBadge.className = "badge large"; // Resetear clases
    
    if (order.is_error) reasonBadge.classList.add("purple");
    else if (order.close_reason.includes("Recuperación")) reasonBadge.classList.add("green");
    else if (order.close_reason.includes("Pendiente")) reasonBadge.classList.add("yellow");
    else reasonBadge.classList.add("orange");

    // Ocultar bloque de suscriptor y resultados live por defecto
    const subBlock = document.getElementById("modal-subscriber-block");
    const liveBlock = document.getElementById("live-results-block");
    subBlock.style.display = "none";
    liveBlock.style.display = "none";

    // Cargar información del suscriptor si existe cuenta
    const account = order.account || "";
    if (account) {
        fetch(`/api/subscriber/info?account=${encodeURIComponent(account)}`)
            .then(res => res.json())
            .then(res => {
                if (res.success && (res.nims || res.tms)) {
                    subBlock.style.display = "block";
                    
                    const nims = res.nims || {};
                    const tms = res.tms || {};
                    
                    document.getElementById("sub-name").textContent = nims.customer_name || tms.username || "Desconocido";
                    document.getElementById("sub-status").textContent = nims.status || tms.status || "Sin Estado";
                    document.getElementById("sub-mac").textContent = tms.mac || "Sin MAC";
                    document.getElementById("sub-olt").textContent = nims.site_code || "Sin OLT";
                    document.getElementById("sub-port").textContent = tms.port || "Sin Puerto";
                    document.getElementById("sub-bras").textContent = tms.bras || "Sin BRAS";
                    
                    // Bind de botones de acción
                    const btnQueryBras = document.getElementById("btn-query-bras");
                    const btnQueryOlt = document.getElementById("btn-query-olt");
                    
                    // Reset click listeners
                    const newBtnBras = btnQueryBras.cloneNode(true);
                    btnQueryBras.replaceWith(newBtnBras);
                    const newBtnOlt = btnQueryOlt.cloneNode(true);
                    btnQueryOlt.replaceWith(newBtnOlt);
                    
                    newBtnBras.addEventListener("click", () => runBrasQuery(account, tms.bras));
                    newBtnOlt.addEventListener("click", () => runOltPortStatus(tms.port, nims.site_code));
                }
            })
            .catch(err => console.error("Error al obtener info de suscriptor:", err));
    }

    detailModal.classList.add("active");
}

async function runBrasQuery(account, bras) {
    const liveBlock = document.getElementById("live-results-block");
    const liveTitle = document.getElementById("live-results-title");
    const liveContent = document.getElementById("live-results-content");
    
    liveTitle.textContent = "Consulta de BRAS";
    liveContent.textContent = "Conectando con BRAS y ejecutando consulta en vivo...\n(Esto puede tardar unos segundos)";
    liveBlock.style.display = "block";
    liveBlock.scrollIntoView({ behavior: 'smooth' });
    
    try {
        const response = await fetch(`/api/bras/user_info?account=${encodeURIComponent(account)}&bras=${encodeURIComponent(bras)}`);
        const res = await response.json();
        if (res.success) {
            liveContent.textContent = res.output || "No se recibió respuesta del BRAS.";
        } else {
            liveContent.textContent = `Error: ${res.error}`;
        }
    } catch (err) {
        liveContent.textContent = `Error de red: ${err.message}`;
    }
}

// El campo "port" de TMS viene como OLT_NAME/3/PUERTO/ID (el "3" es una constante
// fija, PUERTO va de 1 a 16, ID es el número de ONU dentro de ese puerto). En vez de
// ir en vivo a un portal externo (lento y menos confiable), esto lee el último
// escaneo del loop continuo de Auditoría OLT -que ya recorre los 16 puertos de cada
// OLT- y responde al instante con el estado real del puerto y el de esa ONU puntual.
async function runOltPortStatus(portString, fallbackOltName) {
    const liveBlock = document.getElementById("live-results-block");
    const liveTitle = document.getElementById("live-results-title");
    const liveContent = document.getElementById("live-results-content");

    liveTitle.textContent = "Estado del Puerto OLT";
    liveBlock.style.display = "block";
    liveBlock.scrollIntoView({ behavior: 'smooth' });

    if (!portString) {
        liveContent.textContent = "No hay dato de puerto (TMS) para este cliente; no se puede consultar el estado de la línea.";
        return;
    }

    const parts = portString.split('/');
    if (parts.length < 4) {
        liveContent.textContent = `Formato de puerto no reconocido: "${portString}"`;
        return;
    }
    const oltName = parts[0] || fallbackOltName;
    // El último segmento puede traer un sufijo tipo "21:4096.35" (ancho de banda u
    // otro dato pegado con ":"); el ONU ID real es solo el número antes de los ":".
    const onuId = parts[parts.length - 1].split(':')[0];
    const puerto = parts[parts.length - 2];

    liveContent.textContent = `Consultando estado del PUERTO ${puerto} en ${oltName}...`;

    try {
        const response = await fetch(`/api/olt/port_status?olt_name=${encodeURIComponent(oltName)}&port=${encodeURIComponent(puerto)}&onu_id=${encodeURIComponent(onuId)}`);
        const res = await response.json();
        if (res.success) {
            let txt = `OLT: ${res.olt_name}   |   PUERTO ${res.pon_num} de 16   |   IP: ${res.olt_ip}\n`;
            txt += res.live ? `Consultado EN VIVO: ${res.ts_scan}\n` : `Último escaneo: ${res.ts_scan}\n`;
            txt += `--------------------------------------------------\n`;
            txt += `Resumen del puerto (${res.total_onus} ONUs):\n`;
            txt += `  OK: ${res.ok}   LOS: ${res.los}   Energía: ${res.energia}   Inactivas: ${res.inactivo}   Error: ${res.error}\n`;
            txt += `--------------------------------------------------\n`;
            if (res.client_onu) {
                const c = res.client_onu;
                txt += `Tu cliente (ONU ID ${c.onu_id}):\n`;
                txt += `  Estado             : ${c.estado}\n`;
                txt += `  Tipo Falla         : ${c.tipo_falla}\n`;
                txt += `  Prioridad          : ${c.prioridad || "-"}\n`;
                txt += `  Última caída       : ${c.lastofftime || "-"}\n`;
                txt += `  Días sin servicio  : ${c.dias_sin_servicio ?? "-"}\n`;
            } else {
                txt += `No se encontró la ONU ID ${onuId} en el último escaneo de este puerto.\n`;
                txt += `(Puede que el escaneo continuo aún no haya llegado a este puerto, o el ID cambió.)\n`;
            }
            liveContent.textContent = txt;
        } else {
            liveContent.textContent = `Error: ${res.error}`;
        }
    } catch (err) {
        liveContent.textContent = `Error de conexión: ${err.message}`;
    }
}

function closeModal() {
    detailModal.classList.remove("active");
}

// ================= RENDERIZAR GRÁFICOS (CHART.JS) =================

// Gráfico 1: SLA Doughnut
function renderSlaChart(intervals) {
    const ctx = document.getElementById("slaChart").getContext("2d");
    
    if (slaChartInstance) {
        slaChartInstance.destroy();
    }
    
    slaChartInstance = new Chart(ctx, {
        type: 'doughnut',
        plugins: [ChartDataLabels],
        data: {
            labels: ['< 24 horas', '24 - 48 horas', '48 - 72 horas', '> 72 horas'],
            datasets: [{
                data: [
                    intervals.under_24h,
                    intervals.under_48h,
                    intervals.under_72h,
                    intervals.over_72h
                ],
                backgroundColor: ['#0F9D58', '#F4B400', '#FF6D01', '#DB4437'],
                borderColor: '#10141D',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#16233A', font: { family: 'Outfit', size: 12 } }
                },
                datalabels: {
                    color: '#fff',
                    font: { family: 'Outfit', size: 13, weight: 'bold' },
                    formatter: (value) => value > 0 ? value : ''
                }
            }
        }
    });
}

// Gráfico 2: Top Branches con Mayor Cantidad de Averías (Horizontal Bar)
function renderBranchChart(branchData) {
    const ctx = document.getElementById("branchChart").getContext("2d");

    if (branchChartInstance) {
        branchChartInstance.destroy();
    }

    const labels = branchData.map(item => item.branch || "Sin branch");
    const counts = branchData.map(item => item.count);

    branchChartInstance = new Chart(ctx, {
        type: 'bar',
        plugins: [ChartDataLabels],
        data: {
            labels: labels,
            datasets: [{
                label: 'Averías Pendientes',
                data: counts,
                backgroundColor: '#1A73E8',
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                datalabels: {
                    color: '#16233A',
                    anchor: 'end',
                    align: 'end',
                    font: { family: 'Outfit', size: 11, weight: 'bold' },
                    formatter: (value) => value > 0 ? value : ''
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(15, 23, 42, 0.05)' },
                    ticks: { color: '#5B6577', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#16233A', font: { family: 'Outfit', size: 12 } }
                }
            }
        }
    });
}

// Gráfico 3: Motivos de Cierre (Horizontal Bar)
function renderReasonsChart(reasonsData) {
    const ctx = document.getElementById("reasonsChart").getContext("2d");

    if (reasonsChartInstance) {
        reasonsChartInstance.destroy();
    }

    // Agrupar los motivos
    const labels = reasonsData.map(item => item.reason);
    const counts = reasonsData.map(item => item.count);

    reasonsChartInstance = new Chart(ctx, {
        type: 'bar',
        plugins: [ChartDataLabels],
        data: {
            labels: labels,
            datasets: [{
                label: 'Órdenes por Motivo',
                data: counts,
                backgroundColor: ['#AB47BC', '#F4B400', '#FF6D01', '#1A73E8', '#0F9D58'],
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { titleFont: { family: 'Outfit' }, bodyFont: { family: 'Outfit' } },
                datalabels: {
                    color: '#16233A',
                    anchor: 'end',
                    align: 'end',
                    font: { family: 'Outfit', size: 11, weight: 'bold' },
                    formatter: (value) => value > 0 ? value : ''
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(15, 23, 42, 0.05)' },
                    ticks: { color: '#5B6577', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#5B6577', font: { family: 'Outfit', size: 11 } }
                }
            }
        }
    });
}

// --- NIMS & TOPOLOGÍA DE RED ---

function fetchNimsReport() {
    const tbody = document.getElementById("nims-boxes-table-body");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="9" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando reporte de averías NIMS...</td></tr>';

    fetch("/api/nims/faults_report")
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger">Error: ${data.error}</td></tr>`;
                return;
            }

            // Actualizar tarjetas de métricas
            document.getElementById("nims-stat-boxes").textContent = data.summary.total_boxes_affected || 0;
            document.getElementById("nims-stat-sites").textContent = data.summary.total_sites_affected || 0;

            let totalClients = 0;
            if (data.boxes) {
                data.boxes.forEach(b => totalClients += (b.affected_accounts || 0));
            }
            document.getElementById("nims-stat-clients").textContent = totalClients;

            // Renderizar tabla de cajas
            if (!data.boxes || data.boxes.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="text-center">No hay averías registradas por caja en NIMS.</td></tr>';
                return;
            }

            tbody.innerHTML = "";
            data.boxes.slice(0, 30).forEach(b => {
                const tr = document.createElement("tr");

                const topReason = (b.top_reasons && b.top_reasons.length > 0)
                    ? `${b.top_reasons[0][0]} (${b.top_reasons[0][1]})`
                    : "Desconocido";

                const datesStr = b.dates ? b.dates.slice(-3).join(", ") : "-";

                tr.innerHTML = `
                    <td><strong class="text-accent">${b.site_code || 'N/A'}</strong></td>
                    <td><span class="badge blue">${b.box_code || 'N/A'}</span></td>
                    <td><span class="badge purple">${b.expansion_code || 'N/A'}</span></td>
                    <td>${b.line_code || 'N/A'} (${b.hb_code || 'HB'})</td>
                    <td class="text-mono small">${b.full_route || '-'}</td>
                    <td class="text-center"><strong>${b.total_wos}</strong></td>
                    <td class="text-center"><span class="badge yellow">${b.affected_accounts}</span></td>
                    <td class="small">${datesStr}</td>
                    <td class="small">${topReason}</td>
                `;
                tr.style.cursor = "pointer";
                tr.addEventListener("click", () => openBoxDiagnostics(b.site_code, b.box_code));
                tbody.appendChild(tr);
            });
        })
        .catch(err => {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger">Error al cargar datos: ${err}</td></tr>`;
        });
}

let topoScanInterval = null;

function scanTopologyLive() {
    const siteInput = document.getElementById("topo-site-input");
    if (!siteInput || !siteInput.value.trim()) return;

    const site = siteInput.value.trim();
    const olt = document.getElementById("topo-olt-select").value;
    const hubbox = document.getElementById("topo-hubbox-select").value;

    const loading = document.getElementById("topo-scan-loading");
    const resultContainer = document.getElementById("topo-scan-result");
    const alarmBanner = document.getElementById("topo-alarm-banner");
    const btn = document.getElementById("btn-topo-scan");

    loading.style.display = "block";
    resultContainer.style.display = "none";
    alarmBanner.style.display = "none";
    if (btn) btn.disabled = true;
    if (topoScanInterval) clearInterval(topoScanInterval);

    // El escaneo corre en un hilo de fondo en el servidor (puede tardar varios minutos);
    // se arranca con un POST y luego se hace polling del estado, en vez de mantener una
    // sola petición abierta por minutos (eso causaba "NetworkError" al cortarse la conexión).
    fetch(`/api/topology/scan/start?site=${encodeURIComponent(site)}&olt=${encodeURIComponent(olt)}&hubbox=${encodeURIComponent(hubbox)}`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                loading.style.display = "none";
                if (btn) btn.disabled = false;
                resultContainer.style.display = "block";
                document.getElementById("topo-scan-grid").innerHTML = `<span class="text-danger">Error: ${data.error}</span>`;
                return;
            }
            pollTopologyScanStatus();
        })
        .catch(err => {
            loading.style.display = "none";
            if (btn) btn.disabled = false;
            resultContainer.style.display = "block";
            document.getElementById("topo-scan-grid").innerHTML = `<span class="text-danger">Error de conexión: ${err}</span>`;
        });
}

function pollTopologyScanStatus() {
    const loading = document.getElementById("topo-scan-loading");
    const resultContainer = document.getElementById("topo-scan-result");
    const btn = document.getElementById("btn-topo-scan");

    topoScanInterval = setInterval(async () => {
        try {
            const response = await fetch("/api/topology/scan/status");
            const status = await response.json();

            if (status.state === "running") {
                if (status.total > 0) {
                    loading.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Consultando BRAS en vivo... (${status.checked}/${status.total} cuentas)`;
                }
            } else if (status.state === "done") {
                clearInterval(topoScanInterval);
                loading.style.display = "none";
                if (btn) btn.disabled = false;
                renderTopologyResult(status.result);
            } else if (status.state === "error") {
                clearInterval(topoScanInterval);
                loading.style.display = "none";
                if (btn) btn.disabled = false;
                resultContainer.style.display = "block";
                document.getElementById("topo-scan-grid").innerHTML = `<span class="text-danger">Error: ${status.error}</span>`;
            }
        } catch (err) {
            // Error de red puntual en un poll: se reintenta en el próximo tick, no se corta el intervalo.
            console.error("Error consultando estado del escaneo de topología:", err);
        }
    }, 2000);
}

// Mapa box_code -> lista de clientes del último escaneo, para el click-to-expand.
window.topoBoxClients = {};

function renderTopologyResult(data) {
    const resultContainer = document.getElementById("topo-scan-result");
    const alarmBanner = document.getElementById("topo-alarm-banner");
    resultContainer.style.display = "block";

    document.getElementById("topo-scan-title").textContent = `SITE ${data.site} | OLT ${data.olt} | ${data.xb_code}`;
    document.getElementById("topo-scan-branch").textContent = data.branch || "Sin identificar";
    document.getElementById("topo-scan-total-act").textContent = data.totals.act;
    document.getElementById("topo-scan-total-online").textContent = data.totals.online;
    document.getElementById("topo-scan-total-offline").textContent = data.totals.not_online;
    document.getElementById("topo-scan-total-unknown").textContent = data.totals.unknown;
    document.getElementById("topo-scan-total-never").textContent = data.totals.nunca_online;

    if (data.alarm.boxes_down_count > 0) {
        alarmBanner.style.display = "block";
        alarmBanner.innerHTML = `
            <div class="card p-1-5" style="background: rgba(234,67,53,0.12); border: 1px solid #EA4335;">
                <strong style="color:#D93025;"><i class="fa-solid fa-triangle-exclamation"></i> ALARMA: ${data.alarm.boxes_down_count} caja(s) caída(s) en este site</strong>
                <div style="margin-top:6px; font-family: monospace;">${data.alarm.boxes_down.join(", ")}</div>
            </div>
        `;
    } else {
        alarmBanner.style.display = "none";
    }

    document.getElementById("topo-scan-grid").innerHTML = buildTopologyGridHtml(data);
}

// Construye el HTML de la grilla de cajas (reutilizado por la vista principal del
// Inspector Topología y por el modal de detalle de alarma).
function buildTopologyGridHtml(data) {
    const colorMap = { red: "#D93025", orange: "#B04C00", green: "#0B7A44", blue: "#0F58BD", grey: "#5B6577" };
    window.topoBoxClients = window.topoBoxClients || {};
    let html = "";
    data.hbs.forEach(hb => {
        html += `<h4 style="margin-top:16px; color:#5B6577;">${hb.hb_code}</h4>`;
        hb.lineas.forEach(linea => {
            [linea.cajas, linea.exps].forEach(grupo => {
                if (grupo.length === 0) return;
                html += `<div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:4px;">`;
                grupo.forEach(b => {
                    const color = colorMap[b.color] || "#5B6577";
                    const boxId = `topo-box-${b.box_code}-${Math.floor(Math.random() * 1000000)}`;
                    window.topoBoxClients[boxId] = b.clients || [];
                    html += `
                        <span onclick="toggleTopoBoxClients('${boxId}')" style="cursor:pointer; display:inline-block; min-width: 22ch; padding:3px 6px; border-radius:4px; background: rgba(15, 23, 42, 0.03); border:1px solid ${color}; color:${color}; font-family: monospace; font-size:12px;" title="Act:${b.act} On:${b.online} Off:${b.not_online} Unk:${b.unknown} NuncaOn:${b.nunca_online} - click para ver clientes">
                            ${b.box_code} (${b.pct}%) |Act:${b.act}|On:${b.online}|Off:${b.not_online}|
                        </span>
                        <div id="${boxId}" style="display:none; width:100%; margin: 2px 0 6px;"></div>
                    `;
                });
                html += `</div>`;
            });
        });
    });
    return html;
}

const TOPO_ESTADO_COLOR = { "ONLINE": "#0B7A44", "NOT ONLINE": "#D93025", "UNKNOWN": "#5B6577", "NUNCA ONLINE": "#9B3FB0" };

window.toggleTopoBoxClients = function(boxId) {
    const container = document.getElementById(boxId);
    if (!container) return;

    if (container.style.display === "block") {
        container.style.display = "none";
        return;
    }

    const clients = window.topoBoxClients[boxId] || [];
    if (clients.length === 0) {
        container.innerHTML = `<div class="card p-1" style="font-size:12px; color:#5B6577;">Sin clientes activos en esta caja.</div>`;
    } else {
        let rows = clients.map(c => `
            <tr style="border-bottom:1px solid rgba(15, 23, 42, 0.05);">
                <td style="padding:4px 6px; font-family:monospace; color:#0F58BD;">${c.account}</td>
                <td style="padding:4px 6px;">${c.customer_name || "-"}</td>
                <td style="padding:4px 6px;">${c.phone || "-"}</td>
                <td style="padding:4px 6px; text-align:center; color:${TOPO_ESTADO_COLOR[c.estado] || '#5B6577'}; font-weight:600;">${c.estado}</td>
            </tr>
        `).join("");
        container.innerHTML = `
            <div class="card p-1" style="background: rgba(15, 23, 42, 0.04);">
                <table style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                        <tr style="text-align:left; color:#5B6577; border-bottom:1px solid rgba(15, 23, 42, 0.1);">
                            <th style="padding:4px 6px;">Cuenta</th>
                            <th style="padding:4px 6px;">Cliente</th>
                            <th style="padding:4px 6px;">Teléfono</th>
                            <th style="padding:4px 6px; text-align:center;">Estado BRAS</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }
    container.style.display = "block";
};

async function fetchBranchSlaReport() {
    const tbody = document.getElementById("branch-sla-table-body");
    if (!tbody) return;
    try {
        const response = await fetch("/api/reports/branch_sla");
        const data = await response.json();
        tbody.innerHTML = "";
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No hay pendientes.</td></tr>';
            return;
        }
        data.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${r.branch}</strong></td>
                <td class="text-center text-success clickable-cell" onclick="filterByBranchSla('${r.branch}', 'under_24h')" style="cursor: pointer; font-weight: bold;">${r.under_24h}</td>
                <td class="text-center text-warning clickable-cell" onclick="filterByBranchSla('${r.branch}', 'under_48h')" style="cursor: pointer; font-weight: bold;">${r.under_48h}</td>
                <td class="text-center text-orange clickable-cell" onclick="filterByBranchSla('${r.branch}', 'under_72h')" style="cursor: pointer; font-weight: bold;">${r.under_72h}</td>
                <td class="text-center text-danger clickable-cell" onclick="filterByBranchSla('${r.branch}', 'over_72h')" style="cursor: pointer; font-weight: bold;">${r.over_72h}</td>
                <td class="text-center font-bold text-primary clickable-cell" onclick="filterByBranchSla('${r.branch}', 'all')" style="cursor: pointer; font-weight: bold; background: rgba(66, 133, 244, 0.08);">${r.total_pending}</td>
            `;
            tbody.appendChild(tr);
        });

        // Fila de TOTAL al pie, sumando cada columna de todas las branches
        const totals = data.reduce((acc, r) => {
            acc.under_24h += r.under_24h;
            acc.under_48h += r.under_48h;
            acc.under_72h += r.under_72h;
            acc.over_72h += r.over_72h;
            acc.total_pending += r.total_pending;
            return acc;
        }, { under_24h: 0, under_48h: 0, under_72h: 0, over_72h: 0, total_pending: 0 });

        const totalRow = document.createElement("tr");
        totalRow.style.borderTop = "2px solid rgba(15, 23, 42, 0.15)";
        totalRow.innerHTML = `
            <td><strong>TOTAL</strong></td>
            <td class="text-center" style="font-weight: bold;">${totals.under_24h}</td>
            <td class="text-center" style="font-weight: bold;">${totals.under_48h}</td>
            <td class="text-center" style="font-weight: bold;">${totals.under_72h}</td>
            <td class="text-center" style="font-weight: bold;">${totals.over_72h}</td>
            <td class="text-center" style="font-weight: bold; background: rgba(66, 133, 244, 0.14);">${totals.total_pending}</td>
        `;
        tbody.appendChild(totalRow);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Error: ${err.message}</td></tr>`;
    }
}

// Motivos que no representan una tipificación real de avería (se excluyen del gráfico,
// pero se siguen mostrando en la tabla de resumen)
const NON_FAULT_REASONS = ["Pendiente (Sin comentario)", "Error (vtp_marlo.delacruz)", "PENDIENTE"];

function getSelectedTypificationMonths() {
    const panel = document.getElementById("typification-month-panel");
    if (!panel) return [];
    return Array.from(panel.querySelectorAll("input[data-month]:checked")).map(cb => cb.value);
}

function updateTypificationMonthLabel() {
    const label = document.getElementById("typification-month-label");
    if (!label) return;
    const selected = getSelectedTypificationMonths();
    if (selected.length === 0) label.textContent = "Todos los meses";
    else if (selected.length === 1) label.textContent = selected[0];
    else label.textContent = `${selected.length} meses`;
}

// Descubre los meses (YYYY-MM) presentes en las WOs cargadas y llena el panel del dropdown
function populateTypificationMonthFilter() {
    const panel = document.getElementById("typification-month-panel");
    if (!panel) return;

    const months = new Set();
    workOrders.forEach(order => {
        if (order.create_time && order.create_time.length >= 7) {
            months.add(order.create_time.substring(0, 7)); // YYYY-MM
        }
    });
    const sortedMonths = Array.from(months).sort().reverse();
    const previouslySelected = getSelectedTypificationMonths();

    panel.innerHTML = `
        <label class="month-multiselect-option">
            <input type="checkbox" id="typification-month-all">
            Todos los meses
        </label>
        <div class="month-multiselect-divider"></div>
        ${sortedMonths.map(m => `
            <label class="month-multiselect-option">
                <input type="checkbox" data-month value="${m}" ${previouslySelected.includes(m) ? "checked" : ""}>
                ${m}
            </label>
        `).join("")}
    `;

    const allCb = document.getElementById("typification-month-all");
    allCb.checked = previouslySelected.length === 0;

    allCb.addEventListener("change", () => {
        if (allCb.checked) {
            panel.querySelectorAll("input[data-month]").forEach(cb => { cb.checked = false; });
        }
        updateTypificationMonthLabel();
        fetchTypificationReport();
    });
    panel.querySelectorAll("input[data-month]").forEach(cb => {
        cb.addEventListener("change", () => {
            // "Todos los meses" y meses específicos son mutuamente excluyentes
            allCb.checked = getSelectedTypificationMonths().length === 0;
            updateTypificationMonthLabel();
            fetchTypificationReport();
        });
    });

    updateTypificationMonthLabel();
}

const MONTH_LABELS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
function _formatMonthKey(monthKey) {
    const [y, m] = monthKey.split("-");
    const idx = parseInt(m, 10) - 1;
    return `${MONTH_LABELS_ES[idx] || m} ${y}`;
}

async function fetchTypificationReport() {
    const tbody = document.getElementById("typification-table-body");
    const headRow = document.getElementById("typification-table-head-row");
    if (!tbody) return;
    try {
        const months = getSelectedTypificationMonths();
        const url = months.length > 0
            ? `/api/reports/typification?months=${encodeURIComponent(months.join(","))}`
            : "/api/reports/typification";

        const response = await fetch(url);
        const data = await response.json();

        // Meses presentes en los datos (unión de todos los motivos), ordenados. Se usan como
        // columnas propias en la tabla para ver la evolución mes a mes de cada motivo.
        const monthKeys = Array.from(new Set(data.flatMap(r => Object.keys(r.by_month || {})))).sort();
        const colspan = 3 + monthKeys.length;

        if (headRow) {
            headRow.innerHTML = `
                <th>Clasificación / Motivo</th>
                ${monthKeys.map(mk => `<th class="text-center">${_formatMonthKey(mk)}</th>`).join("")}
                <th class="text-center">Total Casos</th>
                <th class="text-center">Pendientes</th>
            `;
        }

        tbody.innerHTML = "";
        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center">No hay motivos.</td></tr>`;
            renderReasonsChart([]);
            return;
        }
        data.forEach(r => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            tr.onclick = () => filterByReason(r.reason);
            const monthCells = monthKeys.map(mk => {
                const v = (r.by_month || {})[mk] || 0;
                return `<td class="text-center">${v > 0 ? v : '<span style="opacity:0.4;">—</span>'}</td>`;
            }).join("");
            tr.innerHTML = `
                <td><span class="badge ${r.reason.includes('OLT') ? 'purple' : (r.reason.includes('Fibra') ? 'red' : 'orange')}">${r.reason}</span></td>
                ${monthCells}
                <td class="text-center"><strong>${r.total_wos}</strong></td>
                <td class="text-center text-warning"><strong>${r.pending_wos}</strong></td>
            `;
            tbody.appendChild(tr);
        });

        // El gráfico de "Tipificación por Motivo de Cierre" comparte el mismo filtro de mes,
        // pero solo muestra motivos reales (excluye buckets de pendiente/error)
        const chartData = data
            .filter(r => !NON_FAULT_REASONS.includes(r.reason))
            .map(r => ({ reason: r.reason, count: r.total_wos }));
        renderReasonsChart(chartData);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error: ${err.message}</td></tr>`;
    }
}

window.filterByBranchSla = function(branch, bracket) {
    filteredOrders = workOrders.filter(order => {
        if (order.is_error) return false;
        const matchesBranch = (branch === 'SIN BRANCH') ? (!order.branch) : (order.branch === branch);
        if (!matchesBranch) return false;
        
        if (bracket === 'all') {
            const s = order.wo_status.toLowerCase();
            return !(s.includes('close') || s.includes('completed'));
        }
        
        const hours = order.pending_hours;
        if (bracket === 'under_24h') return hours > 0 && hours <= 24;
        if (bracket === 'under_48h') return hours > 24 && hours <= 48;
        if (bracket === 'under_72h') return hours > 48 && hours <= 72;
        if (bracket === 'over_72h') return hours > 72;
        
        return true;
    });
    
    currentPage = 1;
    renderTable();
    
    document.getElementById("table-section").scrollIntoView({ behavior: 'smooth' });
    tableSearch.value = `[Branch: ${branch}${bracket !== 'all' ? ', SLA: ' + bracket : ''}]`;
};

window.filterByReason = function(reason) {
    filteredOrders = workOrders.filter(order => {
        if (reason === 'PENDIENTE') return !order.close_reason;
        return order.close_reason === reason;
    });
    
    currentPage = 1;
    renderTable();
    
    document.getElementById("table-section").scrollIntoView({ behavior: 'smooth' });
    tableSearch.value = `[Motivo: ${reason}]`;
};

window.openBoxDiagnostics = async function(siteCode, boxCode) {
    const modal = document.getElementById("diagnostics-modal");
    if (!modal) return;
    
    document.getElementById("diag-box-code").textContent = boxCode;
    document.getElementById("diag-full-route").textContent = "Cargando ruta física...";
    document.getElementById("diag-assessment-text").textContent = "Analizando estado de conectividad...";
    document.getElementById("diag-solution-text").textContent = "Proponiendo plan de acción...";
    
    const portsContainer = document.getElementById("splitter-ports-container");
    portsContainer.innerHTML = '<div style="grid-column: span 8; text-align: center; color: #5B6577;"><i class="fa-solid fa-spinner fa-spin"></i> Cargando puertos...</div>';
    
    const wosTableBody = document.getElementById("diag-wos-table-body");
    wosTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Buscando incidentes...</td></tr>';
    
    modal.classList.add("active");
    
    try {
        const response = await fetch(`/api/nims/box_diagnostics?site_code=${encodeURIComponent(siteCode)}&box_code=${encodeURIComponent(boxCode)}`);
        const data = await response.json();
        
        if (!data.success) {
            alert("Error al cargar diagnósticos: " + data.error);
            return;
        }
        
        document.getElementById("diag-full-route").textContent = data.full_route;
        document.getElementById("diag-assessment-text").textContent = data.diagnosis;
        document.getElementById("diag-solution-text").textContent = data.proposed_solution;
        
        const sevCard = document.getElementById("diag-severity-card");
        if (data.severity === 'critical') {
            sevCard.style.background = "rgba(231, 76, 60, 0.12)";
            sevCard.style.borderColor = "rgba(231, 76, 60, 0.4)";
            sevCard.querySelector("strong").style.color = "#e74c3c";
        } else if (data.severity === 'warning') {
            sevCard.style.background = "rgba(241, 196, 15, 0.12)";
            sevCard.style.borderColor = "rgba(241, 196, 15, 0.4)";
            sevCard.querySelector("strong").style.color = "#f1c40f";
        } else {
            sevCard.style.background = "rgba(46, 204, 113, 0.12)";
            sevCard.style.borderColor = "rgba(46, 204, 113, 0.4)";
            sevCard.querySelector("strong").style.color = "#2ecc71";
        }
        
        portsContainer.innerHTML = "";
        const ports = Array.from({ length: 8 }, (_, i) => ({ port_num: i + 1, client: null }));
        
        data.clients.forEach(c => {
            const portNum = parseInt(c.splitter_port);
            if (portNum >= 1 && portNum <= 8) {
                ports[portNum - 1].client = c;
            }
        });
        
        ports.forEach(p => {
            const portDiv = document.createElement("div");
            portDiv.style.background = "rgba(15, 23, 42, 0.03)";
            portDiv.style.border = "1px solid rgba(15, 23, 42, 0.08)";
            portDiv.style.borderRadius = "8px";
            portDiv.style.padding = "10px 5px";
            portDiv.style.textAlign = "center";
            
            let portStatusColor = "#7f8c8d";
            let clientHtml = '<span style="font-size: 10px; color: #5f6368;">Libre</span>';
            let tooltipHtml = `Puerto ${p.port_num}: Libre (Disponible)`;
            
            if (p.client) {
                const c = p.client;
                portStatusColor = c.nims_status === 'Activo' ? '#2ecc71' : '#f1c40f';
                clientHtml = `
                    <div style="font-size: 11px; font-weight: bold; color:#0F58BD; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${c.account}</div>
                    <div style="font-size: 9px; color: #5B6577; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${c.customer_name}</div>
                `;
                tooltipHtml = `Puerto ${p.port_num}: ${c.account} - ${c.customer_name} (${c.nims_status})`;
                
                portDiv.setAttribute("data-account", c.account);
                portDiv.setAttribute("data-bras", c.bras);
            }
            
            portDiv.innerHTML = `
                <div style="font-size: 11px; color: #5B6577; margin-bottom: 6px;">PORT ${p.port_num}</div>
                <div class="port-status-indicator" style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: ${portStatusColor}; margin-bottom: 6px; border: 2px solid #10141D; transition: all 0.3s ease;"></div>
                ${clientHtml}
            `;
            
            portDiv.title = tooltipHtml;
            portsContainer.appendChild(portDiv);
        });
        
        wosTableBody.innerHTML = "";
        if (data.wos.length === 0) {
            wosTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay órdenes de trabajo activas en esta caja.</td></tr>';
        } else {
            data.wos.forEach(w => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${w.wo_code}</strong></td>
                    <td><span class="badge mini-badge blue">${w.wo_type}</span></td>
                    <td class="text-danger"><strong>${w.pending_hours}h</strong></td>
                    <td><small>${w.ft_technician}</small></td>
                    <td class="small" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${w.ft_comment}">${w.ft_comment}</td>
                `;
                wosTableBody.appendChild(tr);
            });
        }
        
        const btnPingAll = document.getElementById("btn-diag-ping-all");
        const newBtnPingAll = btnPingAll.cloneNode(true);
        btnPingAll.replaceWith(newBtnPingAll);
        
        newBtnPingAll.onclick = async () => {
            newBtnPingAll.disabled = true;
            newBtnPingAll.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Pingueando...';
            
            const portDivs = portsContainer.querySelectorAll("div[data-account]");
            const promises = Array.from(portDivs).map(async div => {
                const account = div.getAttribute("data-account");
                const bras = div.getAttribute("data-bras");
                if (!account) return;
                
                const dot = div.querySelector(".port-status-indicator");
                dot.style.background = "#f1c40f";
                
                try {
                    const res = await fetch(`/api/bras/user_info?account=${encodeURIComponent(account)}&bras=${encodeURIComponent(bras)}`);
                    const resData = await res.json();
                    if (resData.success && resData.output && !resData.output.toUpperCase().includes("NOT ONLINE")) {
                        dot.style.background = "#2ecc71";
                    } else {
                        dot.style.background = "#e74c3c";
                    }
                } catch {
                    dot.style.background = "#95a5a6";
                }
            });
            
            await Promise.all(promises);
            newBtnPingAll.disabled = false;
            newBtnPingAll.innerHTML = '<i class="fa-solid fa-radar"></i> Ping Todo BRAS';
        };
        
    } catch (err) {
        alert("Error al cargar diagnósticos: " + err.message);
    }
};


window.closeDiagModal = function() {
    const modal = document.getElementById("diagnostics-modal");
    if (modal) modal.classList.remove("active");
};

let _oltPollInterval = null;
let _oltPageActive   = false;
let _oltAutoRefresh  = null;   // Auto-refresca datos mientras se está en la página

// ── Scan Button ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const btnOltScan = document.getElementById("btn-olt-scan");
    const btnOltScanCancel = document.getElementById("btn-olt-scan-cancel");
    if (btnOltScan) {
        btnOltScan.addEventListener("click", async () => {
            btnOltScan.disabled = true;
            btnOltScan.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Iniciando...</span>';
            try {
                const r = await fetch("/api/olt/scan", { method: "POST" });
                const d = await r.json();
                if (!r.ok) {
                    alert(d.error || "Error al iniciar el escaneo.");
                    btnOltScan.disabled = false;
                    btnOltScan.innerHTML = '<i class="fa-solid fa-radar"></i> <span>Forzar Escaneo</span>';
                    return;
                }
                _startOltPolling();
            } catch (e) {
                alert("Error: " + e.message);
                btnOltScan.disabled = false;
                btnOltScan.innerHTML = '<i class="fa-solid fa-radar"></i> <span>Forzar Escaneo</span>';
            }
        });
    }

    if (btnOltScanCancel) {
        btnOltScanCancel.addEventListener("click", async () => {
            btnOltScanCancel.disabled = true;
            btnOltScanCancel.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Cancelando...</span>';
            try {
                const r = await fetch("/api/olt/scan/cancel", { method: "POST" });
                const d = await r.json();
                if (!r.ok) alert(d.error || "Error al cancelar.");
                _startOltPolling(); // force rapid UI update
            } catch (e) {
                alert("Error: " + e.message);
            }
        });
    }

    // Modal Consultar OLTs
    const btnOltConsultar = document.getElementById("btn-olt-consultar");
    const modalOltSelection = document.getElementById("olt-selection-modal");
    const btnOltModalClose = document.getElementById("olt-modal-close");
    const btnOltModalCancel = document.getElementById("btn-olt-modal-cancel");
    const btnOltModalStart = document.getElementById("btn-olt-modal-start");
    const oltCheckboxList = document.getElementById("olt-checkbox-list");
    const oltSearchInput = document.getElementById("olt-search-input");
    const btnOltSelectAll = document.getElementById("btn-olt-select-all");
    const btnOltDeselectAll = document.getElementById("btn-olt-deselect-all");

    if (btnOltConsultar && modalOltSelection) {
        btnOltConsultar.addEventListener("click", async () => {
            modalOltSelection.classList.add("active");
            oltCheckboxList.innerHTML = '<p style="color:#9aa0a6;">Cargando OLTs...</p>';
            
            try {
                const r = await fetch("/api/olt/list");
                const olts = await r.json();
                oltCheckboxList.innerHTML = "";
                
                if (olts.length === 0) {
                    oltCheckboxList.innerHTML = '<p style="color:#ea4335;">No se encontraron OLTs (Revisa olts_input.xlsx)</p>';
                    return;
                }
                
                olts.forEach(olt => {
                    const label = document.createElement("label");
                    label.style.display = "flex";
                    label.style.alignItems = "center";
                    label.style.gap = "8px";
                    label.style.cursor = "pointer";
                    label.style.padding = "4px";
                    label.className = "olt-checkbox-item";
                    
                    const cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.value = olt.name;
                    cb.className = "olt-checkbox";
                    
                    const span = document.createElement("span");
                    span.textContent = `${olt.name} (${olt.ip})`;
                    span.style.fontSize = "13px";
                    
                    label.appendChild(cb);
                    label.appendChild(span);
                    oltCheckboxList.appendChild(label);
                });
            } catch (e) {
                oltCheckboxList.innerHTML = `<p style="color:#ea4335;">Error cargando lista: ${e.message}</p>`;
            }
        });
        
        const closeModal = () => modalOltSelection.classList.remove("active");
        btnOltModalClose.addEventListener("click", closeModal);
        btnOltModalCancel.addEventListener("click", closeModal);
        
        oltSearchInput.addEventListener("input", (e) => {
            const term = e.target.value.toLowerCase();
            const items = oltCheckboxList.querySelectorAll(".olt-checkbox-item");
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(term) ? "flex" : "none";
            });
        });
        
        btnOltSelectAll.addEventListener("click", () => {
            const items = oltCheckboxList.querySelectorAll(".olt-checkbox-item");
            items.forEach(item => {
                if (item.style.display !== "none") {
                    item.querySelector("input").checked = true;
                }
            });
        });
        
        btnOltDeselectAll.addEventListener("click", () => {
            const items = oltCheckboxList.querySelectorAll(".olt-checkbox-item");
            items.forEach(item => {
                if (item.style.display !== "none") {
                    item.querySelector("input").checked = false;
                }
            });
        });
        
        btnOltModalStart.addEventListener("click", async () => {
            const checkedBoxes = Array.from(oltCheckboxList.querySelectorAll(".olt-checkbox:checked"));
            const selectedOlts = checkedBoxes.map(cb => cb.value);
            
            if (selectedOlts.length === 0) {
                alert("Debes seleccionar al menos una OLT.");
                return;
            }
            
            btnOltModalStart.disabled = true;
            btnOltModalStart.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Iniciando...';
            
            try {
                const r = await fetch("/api/olt/scan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ selected_olts: selectedOlts })
                });
                const d = await r.json();
                if (!r.ok) {
                    alert(d.error || "Error al iniciar el escaneo.");
                } else {
                    closeModal();
                    _startOltPolling();
                }
            } catch (e) {
                alert("Error: " + e.message);
            } finally {
                btnOltModalStart.disabled = false;
                btnOltModalStart.innerHTML = '<i class="fa-solid fa-play"></i> Iniciar Escaneo';
            }
        });
    }

    // Tabs OLT
    document.querySelectorAll(".olt-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".olt-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".olt-tab-content").forEach(c => c.style.display = "none");
            tab.classList.add("active");
            const key = tab.dataset.oltTab;
            const panel = document.getElementById(`olt-tab-${key}`);
            if (panel) panel.style.display = "block";
            if (key === "cortes")  _loadOltCortes();
            if (key === "resumen") _loadOltResumen();
        });
    });

    document.getElementById("olt-cortes-filter-branch")?.addEventListener("change", _renderOltCortes);
    document.getElementById("olt-cortes-filter-tipo")?.addEventListener("change", _renderOltCortes);

    // ── Página Despliegues Pendientes ──────────────────────────
    document.getElementById("nav-deploy-pending")?.addEventListener("click", _loadDeployPending);
    document.getElementById("btn-deploy-pending-run")?.addEventListener("click", _runDeployPendingUpdate);
    document.getElementById("btn-deploy-pending-cancel")?.addEventListener("click", _cancelDeployPendingUpdate);
    document.getElementById("dp-filter-search")?.addEventListener("input", _renderDeployPendingClients);
    document.getElementById("dp-filter-branch")?.addEventListener("change", _renderDeployPendingClients);
    document.getElementById("dp-filter-tipo")?.addEventListener("change", _renderDeployPendingClients);

    // Búsqueda de Cliente
    const btnClientSearch = document.getElementById("btn-olt-client-search");
    const clientSearchInput = document.getElementById("olt-client-search-input");
    if (btnClientSearch) btnClientSearch.addEventListener("click", () => _searchOltClient());
    if (clientSearchInput) clientSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") _searchOltClient();
    });

    // Al entrar a la página OLT: cargar datos + arrancar loop de status
    const navOlt = document.getElementById("nav-olt");
    if (navOlt) {
        navOlt.addEventListener("click", () => {
            _oltPageActive = true;
            _pollOltLoopStatus();
            _loadOltCortes();
            // Auto-refrescar datos y estado continuo cada 10 s mientras se está en esta página
            if (_oltAutoRefresh) clearInterval(_oltAutoRefresh);
            _oltAutoRefresh = setInterval(() => {
                if (_oltPageActive) {
                    _pollOltLoopStatus();
                    _loadOltCortes();
                }
            }, 10000);
        });
    }

    // Navegar a otras páginas detiene el auto-refresh OLT
    document.querySelectorAll(".nav-item:not(#nav-olt)").forEach(item => {
        item.addEventListener("click", () => {
            _oltPageActive = false;
            if (_oltAutoRefresh) { clearInterval(_oltAutoRefresh); _oltAutoRefresh = null; }
        });
    });

    // Poll de status global cada 30 s (para el badge del sidebar)
    _pollOltLoopStatus();
    setInterval(_pollOltLoopStatus, 30000);
});

// ── EMS Connectivity Check ────────────────────────────────────
async function _checkEmsStatus() {
    const banner = document.getElementById("olt-ems-banner");
    const errHint = document.getElementById("olt-stat-err-hint");
    if (!banner) return;

    banner.style.display = "block";
    banner.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verificando conectividad con el EMS...';

    try {
        const r = await fetch("/api/olt/ems_status");
        const d = await r.json();
        if (d.ok) {
            banner.style.display = "none";
            if (errHint) errHint.textContent = "";
        } else {
            banner.innerHTML = `
                <span style="color:#D93025;">
                    <i class="fa-solid fa-circle-exclamation"></i>
                    <strong>EMS inaccesible:</strong> No hay conexión con el servidor EMS
                    (<code>${d.host}:${d.port}</code>).
                    Los escaneos darán TIMEOUT y las OLTs aparecerán como "sin respuesta".
                    Verifica tu conexión a la red corporativa / VPN.
                </span>`;
            banner.style.display = "block";
            if (errHint) errHint.textContent = "⚠ Sin red al EMS";
        }
    } catch (_) {
        banner.innerHTML = '<span style="color:#D93025;"><i class="fa-solid fa-circle-exclamation"></i> No se pudo verificar el estado del EMS.</span>';
    }
}

let _lastKnownOltScan = null;
let _lastKnownOltCycle = null;
let _lastKnownOltState = null;

// ── Polling del loop continuo ─────────────────────────────────
function _startOltPolling() {
    if (_oltPollInterval) clearInterval(_oltPollInterval);
    _pollOltLoopStatus();
    _oltPollInterval = setInterval(() => {
        _pollOltLoopStatus();
    }, 2500);
}

async function _pollOltLoopStatus() {
    try {
        const r  = await fetch("/api/olt/loop_status");
        const d  = await r.json();
        const st = d.scan || {};
        const loop = d.loop || {};

        _updateOltStatusUI(st, loop, d);

        const currentScan = st.last_scan || loop.last_scan;
        const currentCycle = loop.cycle;
        const currentState = st.state;

        // Si terminó un escaneo o cambió el ciclo o el estado pasó a done, recargar tablas automáticamente
        const scanJustFinished = (_lastKnownOltState === "scanning" && currentState === "done") ||
                                 (currentScan && _lastKnownOltScan && currentScan !== _lastKnownOltScan) ||
                                 (currentCycle && _lastKnownOltCycle && currentCycle !== _lastKnownOltCycle);

        if (scanJustFinished && _oltPageActive) {
            _loadOltCortes();
            _loadOltResumen();
        }

        _lastKnownOltScan = currentScan;
        _lastKnownOltCycle = currentCycle;
        _lastKnownOltState = currentState;
    } catch (_) {}
}

function _updateOltStatusUI(st, loop, loopData) {
    st       = st       || {};
    loop     = loop     || {};
    loopData = loopData || {};

    const btnOltScan   = document.getElementById("btn-olt-scan");
    const btnOltCancel = document.getElementById("btn-olt-scan-cancel");
    const progressWrap = document.getElementById("olt-scan-progress-wrap");
    const progressBar  = document.getElementById("olt-progress-bar");
    const progressPct  = document.getElementById("olt-progress-pct");
    const lastScanEl   = document.getElementById("olt-last-scan");
    const loopStatusEl = document.getElementById("olt-loop-status");

    // Actualizar badge del menú lateral (siempre)
    const badge = document.getElementById("olt-nav-badge") || document.getElementById("olt-alarm-badge");
    if (badge) {
        const hasCortes = (st.n_cortes || 0) > 0;
        badge.style.display = hasCortes ? "inline-flex" : "none";
        if (hasCortes) badge.textContent = st.n_cortes;
    }

    // Actualizar SIEMPRE las 4 cards de resumen
    _setOltCard("olt-stat-olts",   st.n_olts_ok  != null ? st.n_olts_ok  : "—");
    _setOltCard("olt-stat-fallas", st.n_fallas   != null ? st.n_fallas   : "—");
    _setOltCard("olt-stat-cortes", st.n_cortes   != null ? st.n_cortes   : "—");
    _setOltCard("olt-stat-err",    st.n_olts_err != null ? st.n_olts_err : "—");

    if (!btnOltScan) return;

    const isScanning = st.state === "scanning" || loop.running;
    const total = st.total || 0;
    const done = Math.min(st.done || 0, total > 0 ? total : (st.done || 0));
    const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((done / total) * 100))) : Math.min(100, Math.max(0, st.progress || 0));

    if (isScanning) {
        btnOltScan.style.display = "none";
        if (btnOltCancel) {
            btnOltCancel.style.display = "inline-flex";
            btnOltCancel.disabled = false;
            btnOltCancel.innerHTML = '<i class="fa-solid fa-ban"></i> <span>Cancelar Escaneo</span>';
        }
        if (progressWrap) progressWrap.style.display = "flex";
        if (progressBar)  progressBar.style.width = pct + "%";
        if (progressPct)  progressPct.textContent = pct + "%";
    } else {
        btnOltScan.style.display = "inline-flex";
        btnOltScan.disabled = false;
        btnOltScan.innerHTML = '<i class="fa-solid fa-radar"></i> <span>Forzar Escaneo</span>';
        if (btnOltCancel) btnOltCancel.style.display = "none";
        if (progressWrap) progressWrap.style.display = "none";
    }

    // Texto de último escaneo
    if (lastScanEl) {
        const lastTs = loop.last_scan || st.last_scan;
        const nextTs = loop.next_scan;
        const cycle  = loop.cycle || 0;
        let txt = lastTs ? `Último escaneo: ${lastTs}` : "Iniciando escaneo continuo...";
        if (cycle) txt += `  |  Ciclo #${cycle}`;
        if (isScanning) {
            txt += `  |  Progreso: ${done}/${total} Puertos (${pct}%)`;
        } else if (nextTs) {
            txt += `  |  Próximo: ${nextTs}`;
        }
        lastScanEl.textContent = txt;

        if (_oltPageActive) {
            _setHeaderLastUpdate("fa-solid fa-tower-broadcast", "Último escaneo OLT", lastTs || "En curso...");
        }
    }

    // Banner de estado del loop (falta archivo / escaneando / esperando)
    if (loopStatusEl) {
        if (loopData.input_exists === false || loop.input_missing) {
            loopStatusEl.innerHTML = '<span style="color:#D93025;"><i class="fa-solid fa-circle-exclamation"></i> Falta <code>olts_input.xlsx</code> con columnas OLT_NAME y OLT_IP para iniciar el escaneo automático.</span>';
            loopStatusEl.style.display = "block";
        } else if (isScanning) {
            const oltDoneCount = Math.floor(done / 16);
            const oltTotalCount = Math.floor(total / 16) || 400;
            loopStatusEl.innerHTML = `<span style="color:#0F58BD;"><i class="fa-solid fa-spinner fa-spin"></i> Escaneando OLT ${oltDoneCount}/${oltTotalCount} (${pct}% — ${done}/${total} Puertos)...</span>`;
            loopStatusEl.style.display = "block";
        } else if (loop.last_scan || st.last_scan) {
            loopStatusEl.innerHTML = `<span style="color:#0B7A44;"><i class="fa-solid fa-circle-check"></i> Ciclo #${loop.cycle || 1} completado (${st.last_scan || loop.last_scan}). Reiniciando siguiente ciclo en breve...</span>`;
            loopStatusEl.style.display = "block";
        } else {
            loopStatusEl.style.display = "none";
        }
    }
}

function _setOltCard(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

// El backend identifica cada puerto como "1-1-3-N" (N = 1 a 16); para el usuario
// solo el número final importa, así que se muestra como "PUERTO N".
function _puertoNum(pon) {
    if (!pon) return pon;
    return pon.includes("-") ? pon.split("-").pop() : pon;
}

// ── Fallas (Puertos Caídos) ───────────────────────────────────
async function _searchOltClient(forcedQuery) {
    const input = document.getElementById("olt-client-search-input");
    const resultBox = document.getElementById("olt-client-search-result");
    if (!resultBox) return;

    const q = (typeof forcedQuery === "string" ? forcedQuery : (input?.value ?? "")).trim();
    if (!q) return;
    if (forcedQuery && input) input.value = forcedQuery;

    resultBox.innerHTML = '<p style="color:#9AA0A6;font-size:13px;"><i class="fa-solid fa-spinner fa-spin"></i> Buscando...</p>';

    try {
        const r = await fetch(`/api/olt/client_search?q=${encodeURIComponent(q)}`);
        const d = await r.json();

        if (!r.ok) {
            resultBox.innerHTML = `<p style="color:#D93025;font-size:13px;"><i class="fa-solid fa-triangle-exclamation"></i> ${d.error || "Error en la búsqueda."}</p>`;
            return;
        }

        if (d.multiple) {
            resultBox.innerHTML = `
                <p style="font-size:13px;color:#9AA0A6;margin-bottom:10px;">Se encontraron ${d.candidates.length} clientes, elige uno:</p>
                <div style="display:flex;flex-direction:column;gap:6px;">
                    ${d.candidates.map(c => `
                        <div class="olt-pon-card all-ok" style="cursor:pointer;" onclick="_searchOltClient('${c.account}')">
                            <strong style="font-size:12px;color:#E8EAED;">${c.account}</strong>
                            <div style="font-size:11px;color:#9AA0A6;">${c.customer_name || "—"} &middot; ${c.phone || "—"}</div>
                        </div>
                    `).join("")}
                </div>`;
            return;
        }

        let html = `
            <div class="olt-pon-card all-ok" style="cursor:default;margin-bottom:14px;">
                <strong style="font-size:13px;color:#E8EAED;">${d.account}</strong>
                <div style="font-size:12px;color:#9AA0A6;margin-top:4px;">
                    ${d.customer_name || "—"} &middot; ${d.phone || "—"}<br>
                    ${d.address ? d.address + "<br>" : ""}
                    Estado TMS: <strong>${d.tms_status || "—"}</strong>
                    ${d.box_code ? ` &middot; Caja: <strong>${d.box_code}</strong>` : ""}
                </div>
            </div>`;

        if (d.error) {
            html += `<p style="color:#D93025;font-size:13px;"><i class="fa-solid fa-triangle-exclamation"></i> ${d.error}</p>`;
            resultBox.innerHTML = html;
            return;
        }

        const os = d.olt_status;
        html += `
            <div class="olt-pon-card" style="cursor:default;margin-bottom:14px;">
                <div style="font-size:13px;color:#9AA0A6;margin-bottom:10px;">
                    OLT: <strong style="color:#E8EAED;">${os.olt_name}</strong> &middot;
                    PUERTO <strong style="color:#E8EAED;">${os.pon_num} de 16</strong> &middot;
                    IP: ${os.olt_ip} &middot; ${os.live ? `<strong style="color:#81C995;"><i class="fa-solid fa-bolt"></i> Consultado en vivo</strong>: ${os.ts_scan}` : `Último escaneo: ${os.ts_scan}`}
                </div>
                <div style="display:flex;gap:14px;font-size:12px;">
                    <span style="color:#81C995;">${os.ok} OK</span>
                    ${os.los > 0 ? `<span style="color:#F28B82;font-weight:600;">${os.los} LOS</span>` : ""}
                    ${os.energia > 0 ? `<span style="color:#FDD663;font-weight:600;">${os.energia} Energía</span>` : ""}
                    ${os.inactivo > 0 ? `<span style="color:#9AA0A6;">${os.inactivo} Inactivas</span>` : ""}
                    ${os.error > 0 ? `<span style="color:#CE93D8;">${os.error} Error</span>` : ""}
                </div>
            </div>`;

        if (os.client_onu) {
            const c = os.client_onu;
            html += `
                <div class="olt-pon-card ${(c.tipo_falla === 'LOS' || c.tipo_falla === 'OPTICA' || c.tipo_falla === 'ENERGIA') ? 'has-fault' : 'all-ok'}" style="cursor:default;">
                    <strong style="font-size:12px;color:#E8EAED;">ONU del cliente (ID ${c.onu_id})</strong>
                    <div style="font-size:12px;color:#9AA0A6;margin-top:6px;line-height:1.6;">
                        Estado: <strong style="color:#E8EAED;">${c.estado}</strong> &middot; Tipo Falla: <strong>${c.tipo_falla}</strong><br>
                        Prioridad: ${c.prioridad || "—"} &middot; Días sin servicio: ${c.dias_sin_servicio ?? "—"}<br>
                        Última caída: ${c.lastofftime || "—"} &middot; SN: ${c.sn || "—"}
                    </div>
                </div>`;
        } else {
            html += `<p style="color:#9AA0A6;font-size:12px;">No se encontró la ONU ID esperada en el último escaneo de este puerto (puede que el ID haya cambiado).</p>`;
        }

        resultBox.innerHTML = html;
    } catch (e) {
        resultBox.innerHTML = `<p style="color:#D93025;font-size:13px;"><i class="fa-solid fa-triangle-exclamation"></i> No se pudo conectar con el servidor (${e.message}). <button class="btn btn-subtle btn-sm" onclick="_searchOltClient('${q.replace(/'/g, "")}')" style="margin-left:10px;padding:4px 10px;font-size:12px;"><i class="fa-solid fa-rotate-right"></i> Reintentar</button></p>`;
    }
}
window._searchOltClient = _searchOltClient;

// ── Cortes Masivos ────────────────────────────────────────────
// Nombres técnicos internos (CORTE-LOS/CORTE-ENERGIA, usados para filtrar) vs. la
// etiqueta en español que se le muestra al usuario.
function _corteTypeLabel(tipoCorte) {
    if (!tipoCorte) return "—";
    if (tipoCorte.startsWith("CORTE-LOS")) return "Pérdida de potencia" + (tipoCorte.includes("SIN-TS") ? " (sin hora exacta)" : "");
    if (tipoCorte.startsWith("CORTE-ENERGIA")) return "Corte de energía" + (tipoCorte.includes("SIN-TS") ? " (sin hora exacta)" : "");
    return tipoCorte;
}

function _joinSpanishList(parts) {
    if (parts.length <= 1) return parts.join("");
    return parts.slice(0, -1).join(", ") + " y " + parts[parts.length - 1];
}

// Desglosa una lista de cortes por tipo, ej. "16 puertos con pérdida de potencia y 1 puerto
// con corte de energía" -un mismo puerto puede tener un corte por LOS Y uno por energía a la
// vez, así que un simple "N puertos con corte" (contando eventos) infla el total real de
// puertos afectados; este desglose es siempre exacto porque cuenta cada tipo por separado.
function _corteBreakdownLabel(cortesArr) {
    const porTipo = {};
    cortesArr.forEach(c => {
        const label = _corteTypeLabel(c.tipo_corte);
        porTipo[label] = (porTipo[label] || 0) + 1;
    });
    const partes = Object.entries(porTipo).map(([label, n]) => `${n} ${n === 1 ? "puerto" : "puertos"} con ${label.toLowerCase()}`);
    return _joinSpanishList(partes);
}

let _oltCortesRaw = [];

async function _loadOltCortes() {
    const tbody = document.getElementById("olt-cortes-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando cortes...</td></tr>';
    try {
        const r    = await fetch("/api/olt/cortes");
        _oltCortesRaw = await r.json();

        // Poblar el filtro de Branch dinámicamente con los branches presentes
        const branchSelect = document.getElementById("olt-cortes-filter-branch");
        if (branchSelect) {
            const currentVal = branchSelect.value;
            const branches = [...new Set(_oltCortesRaw.map(c => c.branch).filter(Boolean))].sort();
            branchSelect.innerHTML = '<option value="">Todos los Branch</option>' +
                branches.map(b => `<option value="${b}">${b}</option>`).join("");
            branchSelect.value = currentVal;
        }

        _renderOltCortes();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center" style="color:#D93025;padding:16px;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>No se pudo conectar con el servidor (${e.message}). <button class="btn btn-subtle btn-sm" onclick="_loadOltCortes()" style="margin-left:10px;padding:4px 10px;font-size:12px;"><i class="fa-solid fa-rotate-right"></i> Reintentar</button></td></tr>`;
    }
}

function _renderOltCortes() {
    const tbody = document.getElementById("olt-cortes-body");
    if (!tbody) return;

    const branchFilter = document.getElementById("olt-cortes-filter-branch")?.value || "";
    const tipoFilter = document.getElementById("olt-cortes-filter-tipo")?.value || "";

    let rows = _oltCortesRaw;
    if (branchFilter) rows = rows.filter(c => c.branch === branchFilter);
    if (tipoFilter) rows = rows.filter(c => c.tipo_corte.startsWith(tipoFilter));

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center" style="color:#0B7A44;"><i class="fa-solid fa-check-circle"></i> Sin cortes masivos detectados con estos filtros.</td></tr>';
        return;
    }

    // Agrupar por OLT: cada grupo muestra una fila de cabecera (branch + OLT + totales)
    // seguida de sus cortes individuales por puerto, en vez de repetir el nombre de la
    // OLT en cada fila cuando tiene varios puertos afectados.
    const groups = new Map();
    for (const c of rows) {
        if (!groups.has(c.olt_name)) groups.set(c.olt_name, { branch: c.branch, olt_ip: c.olt_ip, cortes: [] });
        groups.get(c.olt_name).cortes.push(c);
    }
    const sortedGroups = [...groups.entries()].sort((a, b) => {
        const totalA = a[1].cortes.reduce((s, c) => s + c.onus_afectadas, 0);
        const totalB = b[1].cortes.reduce((s, c) => s + c.onus_afectadas, 0);
        return totalB - totalA;
    });

    tbody.innerHTML = sortedGroups.map(([oltName, g]) => {
        const totalOnus = g.cortes.reduce((s, c) => s + c.onus_afectadas, 0);
        const headerRow = `
            <tr style="background:rgba(234,67,53,0.14);font-weight:700;">
                <td>${g.branch || "—"}</td>
                <td colspan="2">
                    <span class="olt-clickable-name" onclick="_openOltDetailModal('${oltName}')" title="Ver ficha técnica completa de ${oltName}">
                        <i class="fa-solid fa-circle-info" style="font-size:10px;margin-right:4px;"></i>${oltName}
                    </span>
                    <span style="font-weight:400;color:#9AA0A6;font-size:11px;"> (${g.olt_ip})</span>
                </td>
                <td colspan="2">${_corteBreakdownLabel(g.cortes)}</td>
                <td></td>
                <td class="text-center" style="font-size:1.1rem;color:#D93025;">${totalOnus}</td>
                <td colspan="2"></td>
            </tr>`;
        const subRows = g.cortes.map(c => {
            const isLos = c.tipo_corte.startsWith("CORTE-LOS");
            const icon = isLos ? "🔴" : "⚡";
            return `<tr style="background:rgba(15,23,42,0.02);">
                <td></td>
                <td></td>
                <td></td>
                <td>${_puertoNum(c.pon)}</td>
                <td>${icon} ${_corteTypeLabel(c.tipo_corte)}</td>
                <td>${c.hora_corte}</td>
                <td class="text-center" style="color:#D93025;">${c.onus_afectadas}</td>
                <td>${c.causa}</td>
                <td style="font-family:monospace;font-size:10px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${c.onus_ids}">${c.onus_ids}</td>
            </tr>`;
        }).join("");
        return headerRow + subRows;
    }).join("");
}

// ── Resumen por OLT ───────────────────────────────────────────
async function _loadOltResumen() {
    const tbody = document.getElementById("olt-resumen-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando resumen por OLT...</td></tr>';
    try {
        const r    = await fetch("/api/olt/resumen");
        const rows = await r.json();
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center" style="color:#5B6577;">Sin datos de resumen.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(o => {
            const hasFault = (o.los + o.energia) > 0;
            const hasError = o.error_pons > 0;
            const rowStyle = hasFault ? "background:rgba(219,68,55,0.07);" : hasError ? "background:rgba(251,188,4,0.05);" : "";
            
            const errBadge = hasError 
                ? `<span style="color:#7A5900; font-weight:700; cursor:pointer;" onclick="_openOltErrorsModal()" title="Click para ver causas de error">⚠️ ${o.error_pons}</span>`
                : `<span style="color:#5B6577;">0</span>`;

            return `<tr style="${rowStyle}">
                <td>
                    <span class="olt-clickable-name" onclick="_openOltDetailModal('${o.olt_name}')" title="Ver ficha técnica y desglose de ${o.olt_name}">
                        <i class="fa-solid fa-circle-info" style="font-size:10px;margin-right:4px;"></i>${o.olt_name}
                    </span>
                </td>
                <td style="font-family:monospace;font-size:11px;">${o.olt_ip}</td>
                <td class="text-center" style="color:#0B7A44;font-weight:600;">${o.ok}</td>
                <td class="text-center" style="color:#D93025;font-weight:${o.los>0?700:400};">${o.los}</td>
                <td class="text-center" style="color:#7A5900;font-weight:${o.energia>0?700:400};">${o.energia}</td>
                <td class="text-center" style="color:#5B6577;">${o.inactivo}</td>
                <td class="text-center">${errBadge}</td>
            </tr>`;
        }).join("");
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color:#D93025;padding:16px;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>No se pudo conectar con el servidor (${e.message}). <button class="btn btn-subtle btn-sm" onclick="_loadOltResumen()" style="margin-left:10px;padding:4px 10px;font-size:12px;"><i class="fa-solid fa-rotate-right"></i> Reintentar</button></td></tr>`;
    }
}

// ── Modal de OLTs con Error / Sin Respuesta ───────────────────
let _allOltErrorsData = [];

window._closeOltErrorsModal = function() {
    const modal = document.getElementById("olt-errors-modal");
    if (modal) modal.classList.remove("active");
};

window._openOltErrorsModal = async function() {
    const modal = document.getElementById("olt-errors-modal");
    if (!modal) return;
    modal.classList.add("active");

    const tbody = document.getElementById("olt-errors-tbody");
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Obteniendo diagnóstico de OLTs con error...</td></tr>';

    try {
        const r = await fetch("/api/olt/errors");
        _allOltErrorsData = await r.json();
        _renderOltErrors();
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Error: ${e.message}</td></tr>`;
    }
};

function _renderOltErrors() {
    const tbody = document.getElementById("olt-errors-tbody");
    if (!tbody) return;

    const query = (document.getElementById("olt-errors-search")?.value || "").toLowerCase().trim();
    const catFilter = document.getElementById("olt-errors-filter-cat")?.value || "";

    const filtered = _allOltErrorsData.filter(item => {
        const cat = item.category || item.error_category || "";
        const desc = (item.category_desc || "") + " " + (item.status_sample || "") + " " + (item.last_error || "");
        const matchesQuery = !query || item.olt_name.toLowerCase().includes(query) || (item.olt_ip || "").includes(query) || desc.toLowerCase().includes(query);
        const matchesCat = !catFilter || cat === catFilter;
        return matchesQuery && matchesCat;
    });

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:#5B6577;">No se encontraron OLTs con el criterio seleccionado.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(item => {
        const cat = item.category || item.error_category || "TIMEOUT";
        const catBadge = cat === "NE_NOT_EXIST"
            ? '<span class="badge-err-exist"><i class="fa-solid fa-ban"></i> No Existe en EMS</span>'
            : cat === "NE_DISCONNECTED"
            ? '<span class="badge-err-disco"><i class="fa-solid fa-triangle-exclamation"></i> Desconectada (Offline)</span>'
            : '<span class="badge-err-timeout"><i class="fa-solid fa-clock"></i> Timeout de Red</span>';

        const count = item.error_count != null ? item.error_count : (Array.isArray(item.error_pons) ? item.error_pons.length : 16);
        const sample = item.status_sample || item.last_error || item.category_desc || "—";
        const descHuman = item.category_desc || "";

        return `<tr>
            <td>
                <span class="olt-clickable-name" onclick="_openOltDetailModal('${item.olt_name}')" title="Ver ficha técnica de ${item.olt_name}">
                    <i class="fa-solid fa-circle-info" style="font-size:11px;margin-right:4px;"></i><strong>${item.olt_name}</strong>
                </span>
            </td>
            <td style="font-family:monospace; font-size:11px; color:#0F58BD;">${item.olt_ip || "—"}</td>
            <td>${catBadge}</td>
            <td class="text-center" style="font-weight:700; color:#D93025;">${count} / 16</td>
            <td style="font-size:11px; color:#16233A; max-width:280px; word-break:break-word;">
                ${descHuman ? `<div style="font-weight:600; color:#7A5900; margin-bottom:2px;">${descHuman}</div>` : ''}
                <div style="font-family:monospace; font-size:10px; color:#5B6577;">${sample}</div>
            </td>
            <td class="text-center">
                <button class="btn-sm-blue" onclick="_openOltDetailModal('${item.olt_name}')" style="font-size:11px; padding:4px 10px; cursor:pointer;">
                    <i class="fa-solid fa-eye"></i> Inspeccionar
                </button>
            </td>
        </tr>`;
    }).join("");
}

// ── Modal de Detalle Completo de OLT ─────────────────────────
let _currentOltDetail = null;

window._closeOltDetailModal = function() {
    const modal = document.getElementById("olt-detail-modal");
    if (modal) modal.classList.remove("active");
};

window._openOltDetailModal = async function(oltName) {
    const modal = document.getElementById("olt-detail-modal");
    if (!modal) return;

    modal.classList.add("active");
    const titleEl = document.getElementById("olt-detail-title");
    const ipEl = document.getElementById("olt-detail-ip");
    const tsEl = document.getElementById("olt-detail-ts");
    const statsGrid = document.getElementById("olt-detail-stats-grid");
    const ponGrid = document.getElementById("olt-detail-pon-grid");
    const cortesWrap = document.getElementById("olt-detail-cortes-wrap");
    const onusTbody = document.getElementById("olt-detail-onus-tbody");

    if (titleEl) titleEl.textContent = oltName;
    if (ipEl) ipEl.textContent = "...";
    if (tsEl) tsEl.textContent = "Cargando información detallada...";
    if (statsGrid) statsGrid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#5B6577;"><i class="fa-solid fa-spinner fa-spin"></i> Cargando datos de OLT...</div>';
    if (ponGrid) ponGrid.innerHTML = '';
    if (cortesWrap) cortesWrap.style.display = "none";
    if (onusTbody) onusTbody.innerHTML = '<tr><td colspan="8" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando ONUs...</td></tr>';

    try {
        const r = await fetch(`/api/olt/detail?olt_name=${encodeURIComponent(oltName)}`);
        if (!r.ok) {
            const err = await r.json();
            throw new Error(err.error || "No se pudo obtener el detalle.");
        }
        _currentOltDetail = await r.json();
        _renderOltDetail();
    } catch (e) {
        if (tsEl) tsEl.textContent = `Error: ${e.message}`;
        if (statsGrid) statsGrid.innerHTML = `<div style="grid-column:1/-1;color:#D93025;">Error cargando detalle: ${e.message}</div>`;
    }
};

function _renderOltDetail() {
    if (!_currentOltDetail) return;
    const d = _currentOltDetail;
    const s = d.summary || d.olt_info || {};

    const titleEl = document.getElementById("olt-detail-title");
    const ipEl = document.getElementById("olt-detail-ip");
    const tsEl = document.getElementById("olt-detail-ts");

    if (titleEl) titleEl.textContent = d.olt_name || s.olt_name || "OLT";
    if (ipEl) ipEl.textContent = d.olt_ip || s.olt_ip || "—";
    if (tsEl) tsEl.textContent = `Último escaneo: ${d.ts_scan || s.last_scan || '—'}`;

    // Render Stats Pills
    const statsHtml = `
        <div style="background:rgba(66,133,244,0.1); border:1px solid rgba(66,133,244,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#0F58BD; display:block; text-transform:uppercase; font-weight:600;">Total ONUs</span>
            <strong style="font-size:16px; color:#16233A;">${s.total_onus ?? 0}</strong>
        </div>
        <div style="background:rgba(52,168,83,0.1); border:1px solid rgba(52,168,83,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#0B7A44; display:block; text-transform:uppercase; font-weight:600;">ONUs OK</span>
            <strong style="font-size:16px; color:#0B7A44;">${s.ok ?? s.total_ok ?? 0}</strong>
        </div>
        <div style="background:rgba(234,67,53,0.1); border:1px solid rgba(234,67,53,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#B7261C; display:block; text-transform:uppercase; font-weight:600;">LOS (Fibra)</span>
            <strong style="font-size:16px; color:#B7261C;">${s.los ?? s.total_los ?? 0}</strong>
        </div>
        <div style="background:rgba(251,188,4,0.1); border:1px solid rgba(251,188,4,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#7A5900; display:block; text-transform:uppercase; font-weight:600;">Energía (Dying)</span>
            <strong style="font-size:16px; color:#7A5900;">${s.energia ?? s.total_energia ?? 0}</strong>
        </div>
        <div style="background:rgba(154,160,166,0.1); border:1px solid rgba(154,160,166,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#5B6577; display:block; text-transform:uppercase; font-weight:600;">Inactivos</span>
            <strong style="font-size:16px; color:#5B6577;">${s.inactivo ?? s.total_inactivo ?? 0}</strong>
        </div>
        <div style="background:rgba(171,71,188,0.1); border:1px solid rgba(171,71,188,0.3); padding:8px 12px; border-radius:6px; text-align:center;">
            <span style="font-size:10px; color:#9B3FB0; display:block; text-transform:uppercase; font-weight:600;">Puertos Error</span>
            <strong style="font-size:16px; color:#9B3FB0;">${s.error_pons ?? s.total_error_pons ?? 0}</strong>
        </div>
    `;
    const statsGrid = document.getElementById("olt-detail-stats-grid");
    if (statsGrid) statsGrid.innerHTML = statsHtml;

    // Render Cortes
    const cortesWrap = document.getElementById("olt-detail-cortes-wrap");
    const cortesList = document.getElementById("olt-detail-cortes-list");
    const cortesSummary = document.getElementById("olt-detail-cortes-summary");
    if (d.cortes && d.cortes.length > 0) {
        if (cortesWrap) cortesWrap.style.display = "block";

        if (cortesSummary) cortesSummary.textContent = _corteBreakdownLabel(d.cortes);

        if (cortesList) {
            cortesList.innerHTML = d.cortes.map(c => `
                <div style="background:rgba(234,67,53,0.12); border-left:4px solid #EA4335; padding:10px 14px; border-radius:4px; margin-bottom:6px; font-size:12px;">
                    <strong><i class="fa-solid fa-bolt" style="color:#D93025;"></i> ${_corteTypeLabel(c.tipo_corte)} en PUERTO ${_puertoNum(c.pon)}</strong> &mdash;
                    <span>${c.onus_afectadas} ONUs afectadas (${c.causa})</span> &mdash; 
                    <span style="color:#5B6577;">Hora: ${c.hora_corte}</span>
                </div>
            `).join("");
        }
    } else {
        if (cortesWrap) cortesWrap.style.display = "none";
    }

    // Render Puerto grid
    const ponSelect = document.getElementById("olt-detail-filter-pon");
    if (ponSelect) {
        ponSelect.innerHTML = '<option value="">Todos los Puertos</option>';
    }

    const ponGrid = document.getElementById("olt-detail-pon-grid");
    if (d.pons && d.pons.length > 0) {
        // PONs con un corte masivo activo (ver d.cortes) se resaltan mucho más fuerte que
        // un simple "tiene alguna falla" -un corte de 29 LOS no debería verse igual que un
        // puerto con 1 LOS aislado.
        const corteByPon = {};
        (d.cortes || []).forEach(c => { corteByPon[c.pon] = c; });

        if (ponGrid) {
            ponGrid.innerHTML = d.pons.map(p => {
                const puertoNum = _puertoNum(p.pon);
                if (ponSelect) {
                    ponSelect.innerHTML += `<option value="${p.pon}">PUERTO ${puertoNum} (${p.total} ONUs)</option>`;
                }
                const corte = corteByPon[p.pon];
                const hasFault = (p.los + p.energia) > 0;
                const hasError = p.error > 0;
                const cardClass = corte ? "olt-pon-card is-corte" : hasFault ? "olt-pon-card has-fault" : hasError ? "olt-pon-card has-error" : "olt-pon-card all-ok";

                let errorNotice = '';
                if (hasError) {
                    errorNotice = `<div style="font-size:10px; color:#CE93D8; margin-top:4px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${p.error_msg}">⚠️ ${p.error_msg || 'Error'}</div>`;
                }
                const corteBadge = corte
                    ? `<div class="olt-corte-badge"><i class="fa-solid fa-bolt"></i> CORTE MASIVO — ${corte.onus_afectadas} ONUs</div>`
                    : '';

                return `
                    <div class="${cardClass}" onclick="_filterOltDetailByPon('${p.pon}')" id="pon-card-${p.pon.replace(/\//g,'-')}" title="Click para filtrar ONUs del PUERTO ${puertoNum}">
                        ${corteBadge}
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <strong style="font-size:12px; color:#E8EAED;">PUERTO ${puertoNum}</strong>
                            <span style="font-size:11px; font-weight:600; color:#8AB4F8;">${p.total} ONUs</span>
                        </div>
                        <div style="display:flex; gap:6px; font-size:11px; align-items:center;">
                            <span style="color:#81C995;" title="OK">${p.ok} OK</span>
                            ${p.los > 0 ? `<span class="${corte ? 'olt-los-count-big' : ''}" style="color:#F28B82; font-weight:600;" title="LOS">${p.los} LOS</span>` : ''}
                            ${p.energia > 0 ? `<span style="color:#FDD663; font-weight:600;" title="Energía">${p.energia} PWR</span>` : ''}
                            ${p.inactivo > 0 ? `<span style="color:#9AA0A6;" title="Inactivo">${p.inactivo} INA</span>` : ''}
                        </div>
                        ${errorNotice}
                    </div>
                `;
            }).join("");
        }
    } else {
        if (ponGrid) ponGrid.innerHTML = '<div style="color:#5B6577; font-size:12px;">No hay datos de puertos registrados para esta OLT.</div>';
    }

    _renderOltDetailOnus();
}

window._filterOltDetailByPon = function(pon) {
    const select = document.getElementById("olt-detail-filter-pon");
    if (select) {
        select.value = select.value === pon ? "" : pon;
    }
    _renderOltDetailOnus();
};

function _renderOltDetailOnus() {
    if (!_currentOltDetail) return;
    const tbody = document.getElementById("olt-detail-onus-tbody");
    if (!tbody) return;

    const selectedPon = document.getElementById("olt-detail-filter-pon")?.value || "";
    const selectedEstado = document.getElementById("olt-detail-filter-estado")?.value || "";

    // Highlight selected Puerto card
    document.querySelectorAll(".olt-pon-card").forEach(c => c.classList.remove("active"));
    if (selectedPon) {
        const activeCard = document.getElementById(`pon-card-${selectedPon.replace(/\//g,'-')}`);
        if (activeCard) activeCard.classList.add("active");
    }

    const filtered = (_currentOltDetail.onus || []).filter(onu => {
        const matchesPon = !selectedPon || onu.pon === selectedPon;
        let matchesEstado = true;
        if (selectedEstado === "OK") matchesEstado = onu.estado === "online";
        else if (selectedEstado === "FALLA") matchesEstado = (onu.tipo_falla === "LOS" || onu.tipo_falla === "ENERGIA");
        else if (selectedEstado === "INACTIVO") matchesEstado = (onu.estado === "inactive" || onu.estado === "offline");
        return matchesPon && matchesEstado;
    });

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="color:#5B6577;">No hay ONUs que coincidan con los filtros.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(o => {
        const isFalla = o.tipo_falla === "LOS" || o.tipo_falla === "ENERGIA";
        const rowClass = o.tipo_falla === "LOS" ? "olt-row-los" : o.tipo_falla === "ENERGIA" ? "olt-row-energia" : "";
        const prioBadge = o.prioridad === "ALTA"  ? `<span class="badge-alta">ALTA</span>`
                        : o.prioridad === "MEDIA" ? `<span class="badge-media">MEDIA</span>` : (o.prioridad || "—");

        const tipoBadge = o.tipo_falla === "LOS"     ? `<span class="badge-los">LOS</span>`
                        : o.tipo_falla === "ENERGIA" ? `<span class="badge-energia">ENERGÍA</span>`
                        : o.tipo_falla ? `<span class="badge-optica">${o.tipo_falla}</span>` : "—";

        return `<tr class="${rowClass}">
            <td style="font-weight:600;">${_puertoNum(o.pon)}</td>
            <td style="font-family:monospace;">${o.onu_id || "—"}</td>
            <td style="font-family:monospace;font-size:11px;">${o.sn || "—"}</td>
            <td><span style="color:${o.estado==='online'?'#81C995':'#F28B82'};">${o.estado}</span></td>
            <td>${o.lastofftime || "—"}</td>
            <td class="text-center">${o.dias_sin_servicio ?? "—"}</td>
            <td>${tipoBadge}</td>
            <td>${prioBadge}</td>
        </tr>`;
    }).join("");
}

// ── Global Initializer for OLT Modals & Cards ────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Stat Cards Click to Navigate / Open Modal
    document.getElementById("olt-stat-err-card")?.addEventListener("click", _openOltErrorsModal);
    document.getElementById("olt-stat-olts-card")?.addEventListener("click", () => {
        const tab = document.querySelector('.olt-tab[data-olt-tab="resumen"]');
        if (tab) tab.click();
    });
    document.getElementById("olt-stat-fallas-card")?.addEventListener("click", () => {
        const tab = document.querySelector('.olt-tab[data-olt-tab="resumen"]');
        if (tab) tab.click();
    });
    document.getElementById("olt-stat-cortes-card")?.addEventListener("click", () => {
        const tab = document.querySelector('.olt-tab[data-olt-tab="cortes"]');
        if (tab) tab.click();
    });

    // Close buttons for OLT Errors Modal
    document.getElementById("olt-errors-modal-close")?.addEventListener("click", _closeOltErrorsModal);
    document.getElementById("btn-olt-errors-close")?.addEventListener("click", _closeOltErrorsModal);
    document.getElementById("olt-errors-search")?.addEventListener("input", _renderOltErrors);
    document.getElementById("olt-errors-filter-cat")?.addEventListener("change", _renderOltErrors);

    // Close buttons for OLT Detail Modal
    document.getElementById("olt-detail-modal-close")?.addEventListener("click", _closeOltDetailModal);
    document.getElementById("olt-detail-filter-pon")?.addEventListener("change", _renderOltDetailOnus);
    document.getElementById("olt-detail-filter-estado")?.addEventListener("change", _renderOltDetailOnus);

    // Close modals on Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            _closeOltErrorsModal();
            _closeOltDetailModal();
            const modalSel = document.getElementById("olt-selection-modal");
            if (modalSel) modalSel.classList.remove("active");
        }
    });

    // ── Página KPI ──────────────────────────────────────────────
    document.getElementById("nav-kpi")?.addEventListener("click", () => {
        if (!_kpiState.periods) _initKpiPage();
    });
    document.querySelectorAll("#page-kpi .kpi-period-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#page-kpi .kpi-period-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            _kpiState.periodType = btn.dataset.kpiPeriod;
            _populateKpiPeriodSelect();
            _loadKpiData();
            _loadKpiTrend();
        });
    });
    document.getElementById("kpi-period-select")?.addEventListener("change", _loadKpiData);
    document.getElementById("btn-kpi-refresh-reference")?.addEventListener("click", _refreshKpiReference);

    // Cancelar sincronización desde la página de Credenciales (aparece solo cuando el
    // guardado falla por haber un sync activo -Excel/GNOC/Tableau/NIMS bloquean el .env
    // mientras corren, para no cambiar credenciales a mitad de un login en curso).
    document.getElementById("btn-cancel-sync-for-creds")?.addEventListener("click", async (e) => {
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
            const r = await fetch("/api/sync/cancel", { method: "POST" });
            const result = await r.json();
            const banner = document.getElementById("cred-sync-blocked-banner");
            if (banner) {
                banner.querySelector("span").textContent = result.message || "Sincronización cancelada. Ya puedes guardar tus credenciales.";
                banner.style.background = "rgba(15,157,88,0.1)";
                banner.style.borderColor = "rgba(15,157,88,0.3)";
                banner.querySelector("span").style.color = "#0F9D58";
                btn.style.display = "none";
            }
            if (typeof stopSyncTimer === "function") stopSyncTimer(false);
            if (typeof resetSyncButton === "function") resetSyncButton();
        } catch (err) {
            console.error("Error al cancelar sincronización:", err);
        } finally {
            btn.disabled = false;
        }
    });

    // ── Página Reporte Diario ──────────────────────────────────
    document.getElementById("nav-daily-report")?.addEventListener("click", () => {
        if (!_drOverview) _initDailyReportPage();
    });
    document.querySelectorAll("[data-dr-period]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-dr-period]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            _drState.periodType = btn.dataset.drPeriod;
            _populateDrPeriodSelect();
            _loadDrInstalls();
        });
    });
    document.getElementById("dr-period-select")?.addEventListener("change", _loadDrInstalls);
});

// ═════════════════════════════════════════════════════════════
//  KPI — WO Incident Report (calculado en Python desde GNOC)
// ═════════════════════════════════════════════════════════════
let _kpiTrendComplainsChart = null, _kpiTrendKsubMinChart = null, _kpiTrendOnTimeChart = null;
const _kpiState = { periodType: "monthly", periods: null };

const KPI_METRIC_LABELS = {
    qty_complains: "Qty. Complains",
    ksub_min_per_10ksub: "Ksub*min/10Ksub",
    ksub_min_per_10ksub_day: "Ksub*min/10Ksub/day",
    resolve_time_hrs: "Resolve Time (Hrs)",
    complain_per_10k_day: "Complain/10K/day",
    incident_satisfaction_rate: "Incident Satisfaction Rate",
    recurrings_per_10k_day: "Recurrings/10K/day",
    complain_within_15_day: "Complain within 15 Day",
    warranty_rate: "Rate of Client Need Warranty",
    incident_resolve_on_time_rate: "Incident Resolve On Time Rate",
    recurring_rate: "Recurring Rate",
    active_customers: "Active Customers",
};
const KPI_METRIC_IS_PCT = new Set([
    "incident_satisfaction_rate", "complain_within_15_day", "warranty_rate",
    "incident_resolve_on_time_rate", "recurring_rate",
]);

async function _initKpiPage() {
    try {
        const r = await fetch("/api/kpi/periods");
        _kpiState.periods = await r.json();
        _populateKpiPeriodSelect();
        await _loadKpiData();
        await _loadKpiTrend();
        _loadKpiReferenceStatus();
    } catch (err) {
        console.error("Error al inicializar página KPI:", err);
    }
}

function _populateKpiPeriodSelect() {
    const select = document.getElementById("kpi-period-select");
    if (!select || !_kpiState.periods) return;
    const list = _kpiState.periodType === "monthly" ? _kpiState.periods.months : _kpiState.periods.weeks;
    const valueKey = _kpiState.periodType === "monthly" ? "month_key" : "week_key";
    select.innerHTML = list.map(p => `<option value="${p[valueKey]}">${p.label}</option>`).join("");
    if (list.length) select.value = list[list.length - 1][valueKey];
}

async function _loadKpiData() {
    const select = document.getElementById("kpi-period-select");
    const value = select?.value;
    if (!value) return;

    const loadingEl = document.getElementById("kpi-loading");
    const contentEl = document.getElementById("kpi-content");
    loadingEl.style.display = "block";
    contentEl.style.display = "none";

    try {
        const endpoint = _kpiState.periodType === "monthly"
            ? `/api/kpi/monthly?month=${encodeURIComponent(value)}`
            : `/api/kpi/weekly?week=${encodeURIComponent(value)}`;
        const r = await fetch(endpoint);
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Error al calcular KPIs.");

        const label = _kpiState.periodType === "monthly" ? data.month_name : `Semana ${data.week_label}`;
        document.getElementById("kpi-summary-title").textContent = `Resumen KPI — ${label}`;
        document.getElementById("kpi-branch-table-title").innerHTML =
            `<i class="fa-solid fa-building-user" style="color:#4285F4;margin-right:8px;"></i> Incident Resolve On Time Rate — ${label}`;
        document.getElementById("kpi-hours-table-title").innerHTML =
            `<i class="fa-solid fa-clock" style="color:#F4B400;margin-right:8px;"></i> Sum Hours — ${label}`;
        document.getElementById("kpi-recurring-table-title").innerHTML =
            `<i class="fa-solid fa-rotate" style="color:#AB47BC;margin-right:8px;"></i> Recurring Incidents Report — ${label}`;

        _renderKpiSummary(data.summary);
        _renderKpiBranchTable(data.branch_table, data.total_row);
        _renderKpiHoursTable(data.branch_table, data.sum_hours_total);
        _renderKpiRecurringTable(data.recurring_by_branch, data.recurring_total, data.total_wo);

        loadingEl.style.display = "none";
        contentEl.style.display = "block";
    } catch (err) {
        loadingEl.innerHTML = `<span style="color:#D93025;"><i class="fa-solid fa-triangle-exclamation"></i> ${err.message}</span>`;
    }
}

function _fmtKpiVal(key, val) {
    if (val === null || val === undefined) return "—";
    if (KPI_METRIC_IS_PCT.has(key)) return (val * 100).toFixed(2) + "%";
    if (typeof val === "number") return val.toLocaleString("es-PE", { maximumFractionDigits: 2 });
    return val;
}

function _renderKpiSummary(summary) {
    const grid = document.getElementById("kpi-summary-grid");
    const order = [
        "qty_complains", "ksub_min_per_10ksub", "ksub_min_per_10ksub_day", "resolve_time_hrs",
        "complain_per_10k_day", "incident_satisfaction_rate", "recurrings_per_10k_day",
        "complain_within_15_day", "warranty_rate", "incident_resolve_on_time_rate",
        "recurring_rate", "active_customers",
    ];
    grid.innerHTML = order
        .filter(key => key !== "ksub_min_per_10ksub_day" || summary[key] !== null)
        .map(key => `
            <div class="kpi-stat-card">
                <p class="kpi-stat-label">${KPI_METRIC_LABELS[key]}</p>
                <p class="kpi-stat-val">${_fmtKpiVal(key, summary[key])}</p>
            </div>
        `).join("");
}

function _renderKpiBranchTable(branchTable, totalRow) {
    const tbody = document.getElementById("kpi-branch-table-body");
    const pctFmt = v => (v * 100).toFixed(2) + "%";
    tbody.innerHTML = branchTable.map(b => `
        <tr>
            <td><strong>${b.branch}</strong></td>
            <td class="text-center">${b.total_wo}</td>
            <td class="text-center">${pctFmt(b.under_24h)}</td>
            <td class="text-center">${pctFmt(b.under_48h)}</td>
            <td class="text-center">${pctFmt(b.under_72h)}</td>
            <td class="text-center">${pctFmt(b.over)}</td>
            <td class="text-center">${b.qty_pending}</td>
        </tr>
    `).join("") + `
        <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
            <td>TOTAL</td>
            <td class="text-center">${totalRow.total_wo}</td>
            <td class="text-center">${pctFmt(totalRow.under_24h)}</td>
            <td class="text-center">${pctFmt(totalRow.under_48h)}</td>
            <td class="text-center">${pctFmt(totalRow.under_72h)}</td>
            <td class="text-center">${pctFmt(totalRow.over)}</td>
            <td class="text-center">${totalRow.qty_pending}</td>
        </tr>
    `;
}

function _renderKpiHoursTable(branchTable, sumHoursTotal) {
    const tbody = document.getElementById("kpi-hours-table-body");
    tbody.innerHTML = branchTable.map(b => `
        <tr><td>${b.branch}</td><td class="text-center">${b.sum_hours.toLocaleString("es-PE", { maximumFractionDigits: 2 })}</td></tr>
    `).join("") + `
        <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
            <td>Suma total</td><td class="text-center">${sumHoursTotal.toLocaleString("es-PE", { maximumFractionDigits: 2 })}</td>
        </tr>
    `;
}

function _renderKpiRecurringTable(recurringByBranch, recurringTotal, totalWo) {
    const tbody = document.getElementById("kpi-recurring-table-body");
    tbody.innerHTML = recurringByBranch.map(b => `
        <tr>
            <td>${b.branch}</td>
            <td class="text-center">${b.recurring_count}</td>
            <td class="text-center">${(b.recurring_rate * 100).toFixed(2)}%</td>
        </tr>
    `).join("") + `
        <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
            <td>TOTAL</td>
            <td class="text-center">${recurringTotal}</td>
            <td class="text-center">${totalWo ? ((recurringTotal / totalWo) * 100).toFixed(2) : "0.00"}%</td>
        </tr>
    `;
}

async function _loadKpiTrend() {
    const isWeekly = _kpiState.periodType === "weekly";
    const titleEl = document.getElementById("kpi-trend-title");
    if (titleEl) {
        titleEl.innerHTML = isWeekly
            ? 'Tendencia Semanal <span style="font-weight:400;font-size:0.8rem;color:#9AA0A6;">(comparación semana a semana, desde fines de junio)</span>'
            : 'Tendencia Mensual <span style="font-weight:400;font-size:0.8rem;color:#9AA0A6;">(meses con datos locales completos)</span>';
    }
    const complainsTitleEl = document.getElementById("kpi-trend-complains-title");
    if (complainsTitleEl) complainsTitleEl.textContent = isWeekly ? "WO Created by Week" : "WO Created by Month";
    const ksubTitleEl = document.getElementById("kpi-trend-ksub-title");
    if (ksubTitleEl) ksubTitleEl.textContent = isWeekly ? "Ksub*min/10Ksub (semanal)" : "Ksub*min/10Ksub/month";

    try {
        const r = await fetch(isWeekly ? "/api/kpi/weekly_trend" : "/api/kpi/trend");
        const trend = await r.json();
        if (!r.ok || !trend.length) return;

        const labels = isWeekly
            ? trend.map(t => t.week_label)
            : trend.map(t => `${t.month_name} ${t.month_key.slice(0, 4)}`);

        const ctx1 = document.getElementById("kpiTrendComplainsChart").getContext("2d");
        if (_kpiTrendComplainsChart) _kpiTrendComplainsChart.destroy();
        _kpiTrendComplainsChart = new Chart(ctx1, {
            type: "bar",
            data: { labels, datasets: [{ label: "WOs Creadas", data: trend.map(t => t.qty_complains), backgroundColor: "#1A73E8", borderRadius: 5 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });

        const ctx2 = document.getElementById("kpiTrendKsubMinChart").getContext("2d");
        if (_kpiTrendKsubMinChart) _kpiTrendKsubMinChart.destroy();
        _kpiTrendKsubMinChart = new Chart(ctx2, {
            type: "line",
            data: { labels, datasets: [{ label: "Ksub*min/10Ksub", data: trend.map(t => t.ksub_min_per_10ksub), borderColor: "#AB47BC", backgroundColor: "rgba(171,71,188,0.15)", fill: true, tension: 0.3 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });

        const ctx3 = document.getElementById("kpiTrendOnTimeChart").getContext("2d");
        if (_kpiTrendOnTimeChart) _kpiTrendOnTimeChart.destroy();
        _kpiTrendOnTimeChart = new Chart(ctx3, {
            type: "line",
            data: { labels, datasets: [{ label: "On Time Rate", data: trend.map(t => t.incident_resolve_on_time_rate * 100), borderColor: "#0F9D58", backgroundColor: "rgba(15,157,88,0.15)", fill: true, tension: 0.3 }] },
            options: {
                responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
                scales: { y: { ticks: { callback: v => v + "%" } } }
            }
        });
    } catch (err) {
        console.error("Error al cargar tendencia KPI:", err);
    }
}

async function _loadKpiReferenceStatus() {
    try {
        const r = await fetch("/api/kpi/reference_status");
        const d = await r.json();
        const el = document.getElementById("kpi-reference-status");
        if (!el) return;
        if (d.last_refresh) {
            el.textContent = `Referencia (ZONAS/Staff/TWMS) actualizada: ${d.last_refresh}`;
        } else {
            el.textContent = "Referencia sin actualizar aún";
        }
    } catch (err) { /* silencioso */ }
}

async function _refreshKpiReference() {
    const btn = document.getElementById("btn-kpi-refresh-reference");
    btn.disabled = true;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Actualizando...';
    try {
        const r = await fetch("/api/kpi/refresh_reference", { method: "POST" });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "Error al actualizar referencia.");
        await _loadKpiReferenceStatus();
        await _loadKpiData();
        await _loadKpiTrend();
    } catch (err) {
        alert("Error al actualizar referencia: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

// ═════════════════════════════════════════════════════════════
//  REPORTE DIARIO (instalaciones + averías pendientes/cierres)
// ═════════════════════════════════════════════════════════════
let _drOverview = null;
let _drInstallsChart = null, _drClosuresMonthChart = null, _drClosuresWeekChart = null, _drClosuresDayChart = null;
const _drState = { periodType: "monthly" };

async function _initDailyReportPage() {
    const loadingEl = document.getElementById("dr-loading");
    const contentEl = document.getElementById("dr-content");
    try {
        const r = await fetch("/api/daily_report/overview");
        _drOverview = await r.json();
        if (!r.ok) throw new Error(_drOverview.error || "Error al cargar el reporte diario.");

        _renderDrPending(_drOverview.pending);
        _renderDrClosuresCharts(_drOverview.closures_by_month, _drOverview.closures_by_week, _drOverview.closures_by_day);
        _populateDrPeriodSelect();
        await _loadDrInstalls();

        loadingEl.style.display = "none";
        contentEl.style.display = "block";
    } catch (err) {
        loadingEl.innerHTML = `<span style="color:#D93025;"><i class="fa-solid fa-triangle-exclamation"></i> ${err.message}</span>`;
    }
}

function _populateDrPeriodSelect() {
    const select = document.getElementById("dr-period-select");
    if (!select || !_drOverview) return;
    const periods = _drOverview.installs_periods || { months: [], weeks: [] };
    const list = _drState.periodType === "monthly" ? periods.months : periods.weeks;
    const valueKey = _drState.periodType === "monthly" ? "month_key" : "week_key";
    select.innerHTML = list.map(p => `<option value="${p[valueKey]}">${p.label}</option>`).join("");
    if (list.length) select.value = list[list.length - 1][valueKey];
}

async function _loadDrInstalls() {
    const select = document.getElementById("dr-period-select");
    const value = select?.value;
    if (!value) return;

    try {
        const endpoint = `/api/daily_report/installs?type=${_drState.periodType === "monthly" ? "month" : "week"}&key=${encodeURIComponent(value)}`;
        const r = await fetch(endpoint);
        const result = await r.json();
        if (!r.ok) throw new Error(result.error || "Error al cargar instalaciones.");

        const isWeekly = _drState.periodType === "weekly";
        const label = select.options[select.selectedIndex]?.textContent || value;

        document.getElementById("dr-installs-table-title").innerHTML =
            `<i class="fa-solid fa-building-user" style="color:#4285F4;margin-right:8px;"></i> Instalaciones por Branch — ${label}`;
        document.getElementById("dr-installs-chart-title").textContent = isWeekly ? "Instalaciones por Branch" : "Instalaciones por Día";

        let branchTotals, total;
        if (isWeekly) {
            branchTotals = result.data.branch_table.map(b => ({ branch: b.branch, qty: b.qty }));
            total = result.data.total;
        } else {
            const days = result.data;
            const branchList = _drOverview.pending.branch_table.map(b => b.branch);
            branchTotals = branchList.map(br => ({
                branch: br,
                qty: days.reduce((sum, d) => sum + (d[br] || 0), 0)
            }));
            total = days.reduce((sum, d) => sum + d.total, 0);
        }

        const tbody = document.getElementById("dr-installs-table-body");
        tbody.innerHTML = branchTotals.map(b => `
            <tr><td>${b.branch}</td><td class="text-center">${b.qty}</td></tr>
        `).join("") + `
            <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
                <td>TOTAL</td><td class="text-center">${total}</td>
            </tr>
        `;

        const ctx = document.getElementById("drInstallsChart").getContext("2d");
        if (_drInstallsChart) _drInstallsChart.destroy();
        if (isWeekly) {
            _drInstallsChart = new Chart(ctx, {
                type: "bar",
                data: { labels: branchTotals.map(b => b.branch), datasets: [{ label: "Instalaciones", data: branchTotals.map(b => b.qty), backgroundColor: "#1A73E8", borderRadius: 5 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        } else {
            const days = result.data;
            _drInstallsChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: days.map(d => d.day.slice(8, 10)),
                    datasets: [{ label: "Instalaciones", data: days.map(d => d.total), borderColor: "#0F9D58", backgroundColor: "rgba(15,157,88,0.15)", fill: true, tension: 0.3 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    } catch (err) {
        console.error("Error al cargar instalaciones del Reporte Diario:", err);
    }
}

function _renderDrPending(pending) {
    document.getElementById("dr-pending-since").textContent = `(desde ${pending.since_month})`;
    const tbody = document.getElementById("dr-pending-table-body");
    tbody.innerHTML = pending.branch_table.map(b => `
        <tr><td>${b.branch}</td><td class="text-center">${b.qty_pending}</td></tr>
    `).join("") + `
        <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
            <td>TOTAL</td><td class="text-center">${pending.total_pending}</td>
        </tr>
    `;
}

function _renderDrClosuresCharts(byMonth, byWeek, byDay) {
    const ctx1 = document.getElementById("drClosuresMonthChart").getContext("2d");
    if (_drClosuresMonthChart) _drClosuresMonthChart.destroy();
    _drClosuresMonthChart = new Chart(ctx1, {
        type: "bar",
        data: {
            labels: byMonth.map(m => `${m.month_name} ${m.month_key.slice(0, 4)}`),
            datasets: [{ label: "Cierres", data: byMonth.map(m => m.qty_closed), backgroundColor: "#0F9D58", borderRadius: 5 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });

    const ctx2 = document.getElementById("drClosuresWeekChart").getContext("2d");
    if (_drClosuresWeekChart) _drClosuresWeekChart.destroy();
    _drClosuresWeekChart = new Chart(ctx2, {
        type: "bar",
        data: {
            labels: byWeek.map(w => w.week_label),
            datasets: [{ label: "Cierres", data: byWeek.map(w => w.qty_closed), backgroundColor: "#F4B400", borderRadius: 5 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });

    const ctx3 = document.getElementById("drClosuresDayChart").getContext("2d");
    if (_drClosuresDayChart) _drClosuresDayChart.destroy();
    _drClosuresDayChart = new Chart(ctx3, {
        type: "line",
        data: {
            labels: byDay.map(d => d.day),
            datasets: [{ label: "Cierres", data: byDay.map(d => d.qty_closed), borderColor: "#AB47BC", backgroundColor: "rgba(171,71,188,0.15)", fill: true, tension: 0.3 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

// ═════════════════════════════════════════════════════════════
//  DESPLIEGUES PENDIENTES (integración con deploy ant)
// ═════════════════════════════════════════════════════════════
let _dpSummary = null;
let _dpRunPollInterval = null;

async function _loadDeployPending() {
    const statusLine = document.getElementById("deploy-pending-status-line");

    // Si ya hay una actualización en curso (ej. se recargó la página a mitad de una
    // corrida), retomar el sondeo en vez de mostrar el botón como si no pasara nada.
    try {
        const rs = await fetch("/api/deploy_pending/run_status");
        const status = await rs.json();
        if (status.state === "running" && !_dpRunPollInterval) {
            _startDeployPendingPolling();
        }
    } catch (err) { /* silencioso */ }

    try {
        const r = await fetch("/api/deploy_pending/summary");
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Error al cargar el resumen.");
        _dpSummary = data;

        document.getElementById("dp-stat-total").textContent = data.total;
        const buckets = {};
        data.branch_table.forEach(b => {
            buckets["Under 24h"] = (buckets["Under 24h"] || 0) + b["Under 24h"];
            buckets["Over 24h"] = (buckets["Over 24h"] || 0) + b["Over 24h"];
            buckets["Over 48h"] = (buckets["Over 48h"] || 0) + b["Over 48h"];
            buckets["Over 72h"] = (buckets["Over 72h"] || 0) + b["Over 72h"];
        });
        const cerrarTotal = data.branch_table.reduce((s, b) => s + b.cerrar_wo, 0);
        document.getElementById("dp-stat-under24").textContent = buckets["Under 24h"] || 0;
        document.getElementById("dp-stat-over2448").textContent = (buckets["Over 24h"] || 0) + (buckets["Over 48h"] || 0);
        document.getElementById("dp-stat-over72").textContent = buckets["Over 72h"] || 0;
        document.getElementById("dp-stat-cerrar").textContent = cerrarTotal;

        // Tabla por branch
        const branchBody = document.getElementById("dp-branch-table-body");
        branchBody.innerHTML = data.branch_table.map(b => `
            <tr>
                <td><strong>${b.branch}</strong></td>
                <td class="text-center">${b.total}</td>
                <td class="text-center">${b["Under 24h"]}</td>
                <td class="text-center">${b["Over 24h"]}</td>
                <td class="text-center">${b["Over 48h"]}</td>
                <td class="text-center" style="color:${b["Over 72h"] > 0 ? '#D93025' : 'inherit'};font-weight:${b["Over 72h"] > 0 ? '700' : '400'};">${b["Over 72h"]}</td>
                <td class="text-center">${b.cerrar_wo || 0}</td>
            </tr>
        `).join("") + `
            <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.1);">
                <td>TOTAL</td>
                <td class="text-center">${data.total}</td>
                <td class="text-center">${buckets["Under 24h"] || 0}</td>
                <td class="text-center">${buckets["Over 24h"] || 0}</td>
                <td class="text-center">${buckets["Over 48h"] || 0}</td>
                <td class="text-center">${buckets["Over 72h"] || 0}</td>
                <td class="text-center">${cerrarTotal}</td>
            </tr>
        `;

        // Poblar filtro de branch
        const branchSelect = document.getElementById("dp-filter-branch");
        if (branchSelect && branchSelect.options.length <= 1) {
            const branches = [...new Set(data.clients.map(c => c.branch).filter(Boolean))].sort();
            branchSelect.innerHTML = '<option value="">Todos los Branch</option>' +
                branches.map(b => `<option value="${b}">${b}</option>`).join("");
        }

        _renderDeployPendingClients();

        const cloudWarning = data.cloud_push_error
            ? ` <span style="color:#D93025;font-weight:600;" title="${_escapeHtml(data.cloud_push_error)}"><i class="fa-solid fa-triangle-exclamation"></i> El último push a la nube falló, el portal de sucursales puede estar desactualizado</span>`
            : "";
        statusLine.innerHTML = `<i class="fa-regular fa-clock"></i> Última actualización de despliegues: <strong>${data.last_deploy_run || "sin registro"}</strong> &middot; datos leídos: ${data.checked_at}${cloudWarning}`;
    } catch (err) {
        statusLine.innerHTML = `<span style="color:#D93025;"><i class="fa-solid fa-triangle-exclamation"></i> ${err.message}</span>`;
    }
}

function _escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function _renderDeployPendingClients() {
    if (!_dpSummary) return;
    const tbody = document.getElementById("dp-clients-table-body");
    const search = (document.getElementById("dp-filter-search")?.value || "").toLowerCase().trim();
    const branchFilter = document.getElementById("dp-filter-branch")?.value || "";
    const tipoFilter = document.getElementById("dp-filter-tipo")?.value || "";

    let rows = _dpSummary.clients;
    if (branchFilter) rows = rows.filter(c => c.branch === branchFilter);
    if (tipoFilter) rows = rows.filter(c => c.deployment_type === tipoFilter);
    if (search) {
        rows = rows.filter(c =>
            c.account.toLowerCase().includes(search) ||
            c.customer_name.toLowerCase().includes(search) ||
            c.phone.toLowerCase().includes(search)
        );
    }

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="color:#9AA0A6;">Sin resultados con estos filtros.</td></tr>';
        return;
    }

    const tipoColor = t => t === "Over 72h" ? "#D93025" : t === "Over 48h" ? "#F4B400" : t === "Over 24h" ? "#FF6D01" : "#0F9D58";

    tbody.innerHTML = rows.slice(0, 500).map(c => {
        const needsExplanation = c.deployment_type === "Over 72h" && !c.comment;
        const commentCell = c.comment
            ? `<span title="${_escapeHtml(`Actualizado por ${c.comment_updated_by || "—"} el ${c.comment_updated_at || "—"}`)}">${_escapeHtml(c.comment)}</span>`
            : `<span style="color:${needsExplanation ? "#D93025" : "#9AA0A6"};">${needsExplanation ? "⚠ Sin explicación" : "—"}</span>`;
        return `
        <tr>
            <td>${c.branch || "—"}</td>
            <td style="font-family:monospace;font-size:11px;">${c.account}</td>
            <td>${c.customer_name || "—"}</td>
            <td>${c.phone || "—"}</td>
            <td>${c.partner || "—"}</td>
            <td style="font-family:monospace;font-size:11px;">${c.shop_code || "—"}</td>
            <td><span style="color:${tipoColor(c.deployment_type)};font-weight:600;">${c.deployment_type || "—"}</span></td>
            <td class="text-center">${c.pending_days || "—"}</td>
            <td style="font-family:monospace;font-size:10px;">${c.connector_code || "—"}</td>
            <td style="max-width:220px;">${commentCell}</td>
        </tr>`;
    }).join("") + (rows.length > 500 ? `<tr><td colspan="10" class="text-center" style="color:#9AA0A6;">Mostrando 500 de ${rows.length} resultados — afina la búsqueda para ver más.</td></tr>` : "");
}

const _dpRunBtnOriginalHtml = '<i class="fa-solid fa-arrows-rotate"></i> <span>Actualizar Despliegues</span>';

function _setDeployPendingRunningUI(isRunning) {
    const btnRun = document.getElementById("btn-deploy-pending-run");
    const btnCancel = document.getElementById("btn-deploy-pending-cancel");
    if (!btnRun || !btnCancel) return;
    btnRun.disabled = isRunning;
    btnRun.innerHTML = isRunning
        ? '<i class="fa-solid fa-spinner fa-spin"></i> <span>Actualizando...</span>'
        : _dpRunBtnOriginalHtml;
    btnCancel.style.display = isRunning ? "inline-flex" : "none";
}

async function _runDeployPendingUpdate() {
    try {
        const r = await fetch("/api/deploy_pending/run", { method: "POST" });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "No se pudo iniciar la actualización.");
    } catch (err) {
        alert(err.message);
        return;
    }
    _startDeployPendingPolling();
}

async function _cancelDeployPendingUpdate() {
    const btnCancel = document.getElementById("btn-deploy-pending-cancel");
    btnCancel.disabled = true;
    try {
        const r = await fetch("/api/deploy_pending/cancel", { method: "POST" });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "No se pudo cancelar.");
    } catch (err) {
        alert(err.message);
    } finally {
        btnCancel.disabled = false;
    }
    // El próximo tick del poll (o esta llamada inmediata) va a ver state="idle" y detenerse.
    await _pollDeployPendingStatusOnce();
}

async function _pollDeployPendingStatusOnce() {
    const statusLine = document.getElementById("deploy-pending-status-line");
    try {
        const r = await fetch("/api/deploy_pending/run_status");
        const status = await r.json();

        if (status.state === "running") {
            statusLine.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${status.message} (iniciado: ${status.started_at || ""})`;
            return;
        }

        if (_dpRunPollInterval) {
            clearInterval(_dpRunPollInterval);
            _dpRunPollInterval = null;
        }
        _setDeployPendingRunningUI(false);

        stopDeployTimer(status.state === "success");

        if (status.state === "success") {
            await _loadDeployPending();
        } else if (status.state === "error") {
            alert("La actualización de despliegues terminó con un problema:\n\n" + status.message);
            statusLine.innerHTML = `<span style="color:#D93025;"><i class="fa-solid fa-triangle-exclamation"></i> ${status.message}</span>`;
        } else {
            // "idle" -típicamente tras cancelar
            statusLine.innerHTML = `<i class="fa-regular fa-clock"></i> ${status.message || "Sin actualización en curso."}`;
        }
    } catch (err) {
        // Error de red puntual al pollear: se sigue intentando en el próximo intervalo.
    }
}

function _startDeployPendingPolling() {
    _setDeployPendingRunningUI(true);
    startDeployTimer();
    if (_dpRunPollInterval) clearInterval(_dpRunPollInterval);
    _pollDeployPendingStatusOnce();
    _dpRunPollInterval = setInterval(_pollDeployPendingStatusOnce, 5000);
}

async function _watchAutoTriggeredDeploy() {
    if (_dpRunPollInterval) return; // ya se está siguiendo (manual o ya detectado antes)
    try {
        const r = await fetch("/api/deploy_pending/run_status");
        const status = await r.json();
        if (status.state === "running") {
            _startDeployPendingPolling();
        }
    } catch (e) { /* silencioso, se reintenta en el próximo tick */ }
}


