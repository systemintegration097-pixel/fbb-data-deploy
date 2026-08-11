// State Management for the application
const AppState = {
    currentSection: 'dashboard-section',
    
    // Zones Pagination & Filters
    zones: {
        page: 1,
        perPage: 12,
        search: '',
        branch: '',
        department: '',
        sortBy: 'zone',
        sortDir: 'ASC',
        total: 0
    },
    
    // Boxes Pagination & Filters
    boxes: {
        page: 1,
        perPage: 12,
        search: '',
        branch: '',
        boxClass: '',
        zone: '',
        siteLogical: '',
        sortBy: 'node_code',
        sortDir: 'ASC',
        total: 0,
        selectedBoxId: null
    },
    
    // Staff Pagination & Filters
    staff: {
        page: 1,
        perPage: 12,
        search: '',
        branch: '',
        partner: '',
        sortBy: 'staff_team',
        sortDir: 'ASC',
        total: 0
    },
    
    // Global filter choices populated from server
    filters: {
        branches: [],
        departments: [],
        boxClasses: [],
        partners: []
    },
    
    // Chart instances
    charts: {
        branchSaturation: null,
        customerRatio: null,
        branchCapacityStacked: null,
        incidentsMonthly: null
    },
    
    // Leaflet Map instance
    map: null,
    mapMarkers: []
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initMobileMenu();
    initFilters();
    initSyncButton();
    initMapControls();
    
    // Initial data load
    loadFilterOptions();
    loadDashboardStats();
    loadZones();
    loadBoxes();
    loadStaff();
    loadStackedCapacityChart();
    
    // Modals setup
    initModals();
});

function initMobileMenu() {
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    const closeBtn = document.getElementById('mobile-menu-close');
    const overlay = document.getElementById('sidebar-overlay');
    const sidebar = document.querySelector('.sidebar');
    
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.add('active');
            if (overlay) overlay.classList.add('active');
        });
    }
    
    const closeSidebar = () => {
        if (sidebar) sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
    };
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }
    
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }
    
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', closeSidebar);
    });
}


// ==========================================
// NAVIGATION
// ==========================================
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const sections = document.querySelectorAll('.content-section');
    const titleEl = document.getElementById('section-title');
    const subtitleEl = document.getElementById('section-subtitle');
    
    const sectionMetadata = {
        'dashboard-section': {
            title: 'Panel de Control',
            subtitle: 'Visualización general de la red de banda ancha fija.'
        },
        'zones-section': {
            title: 'Zonas Activas',
            subtitle: 'Administración y estado de las zonas FBB a nivel nacional.'
        },
        'boxes-section': {
            title: 'Lista de Cajas',
            subtitle: 'Catálogo de cajas de distribución y mapeo de coordenadas.'
        },
        'staff-section': {
            title: 'Personal (Staff)',
            subtitle: 'Administración del personal asignado a zonas y OLTs.'
        },
        'partner-capacity-section': {
            title: 'Capacidad de Partners',
            subtitle: 'Resumen y análisis de carga de los socios y equipos asignados.'
        },
        'incidents-section': {
            title: 'Incidentes y Averías',
            subtitle: 'Reporte detallado de volumen de averías y clientes afectados.'
        },
        'deployments-section': {
            title: 'Despliegues y SLA',
            subtitle: 'Análisis de eficiencia de partners, branch y capacidad operativa de los equipos de despliegue.'
        }
    };
    
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-target');
            
            // Toggle buttons
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Toggle sections
            sections.forEach(s => s.classList.remove('active'));
            const activeSection = document.getElementById(target);
            activeSection.classList.add('active');
            
            // Update Headers
            titleEl.textContent = sectionMetadata[target].title;
            subtitleEl.textContent = sectionMetadata[target].subtitle;
            
            AppState.currentSection = target;
            
            // Trigger specific page loads
            if (target === 'partner-capacity-section') {
                loadPartnerCapacityReport();
            }
            
            if (target === 'incidents-section') {
                const branchSel = document.getElementById('incidents-filter-branch');
                if (branchSel && branchSel.options.length <= 1) {
                    branchSel.innerHTML = '<option value="">Todas</option>';
                    AppState.filters.branches.forEach(b => {
                        branchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
                    });
                }
                
                (async () => {
                    await loadIncidentsMonthsOptions();
                    await loadIncidentsWeeksOptions();
                    const bVal = branchSel ? branchSel.value : '';
                    await loadIncidentsSiteOptions(bVal);
                    loadIncidents();
                })();
            }
            
            if (target === 'deployments-section') {
                const branchSel = document.getElementById('deployments-filter-branch');
                if (branchSel && branchSel.options.length <= 1) {
                    branchSel.innerHTML = '<option value="">Todas</option>';
                    AppState.filters.branches.forEach(b => {
                        branchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
                    });
                }
                
                const monthSel = document.getElementById('deployments-filter-month');
                if (monthSel && monthSel.options.length <= 1) {
                    monthSel.innerHTML = '<option value="">Todos los meses</option>';
                    const months = ['01/2026', '02/2026', '03/2026', '04/2026', '05/2026', '06/2026'];
                    months.forEach(m => {
                        monthSel.insertAdjacentHTML('beforeend', `<option value="${m}">${m}</option>`);
                    });
                }
                
                loadDeploymentsReport();
            }
            
            // Leaflet map needs size recalculation when container becomes visible
            if (target === 'boxes-section') {
                setTimeout(() => {
                    if (AppState.map) {
                        AppState.map.invalidateSize();
                    } else {
                        initLeafletMap();
                    }
                }, 100);
            }
        });
    });
}

// ==========================================
// SYNC UTILITY
// ==========================================
function initSyncButton() {
    const syncBtn = document.getElementById('sync-btn');
    const loadingWidget = document.getElementById('sync-loading');
    
    syncBtn.addEventListener('click', async () => {
        if (!confirm('¿Estás seguro de que deseas sincronizar con Google Sheets? Esto descargará las planillas originales y recreará la base de datos local. Los registros modificados se sobrescribirán.')) {
            return;
        }
        
        syncBtn.disabled = true;
        syncBtn.classList.add('hidden');
        loadingWidget.classList.remove('hidden');
        
        try {
            const response = await fetch('/api/fbb/sync', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                showToast(`Sincronización exitosa. Zonas: ${result.zones_imported}. Cajas: ${result.boxes_imported}. Personal: ${result.staff_imported}. Incidentes: ${result.incidents_imported || 0}`, 'success');
                // Reload everything
                loadFilterOptions();
                loadDashboardStats();
                loadZones();
                loadBoxes();
                loadStaff();
                loadStackedCapacityChart();
            } else {
                showToast(`Error al sincronizar: ${result.error}`, 'error');
            }
        } catch (err) {
            showToast(`Error de conexión al servidor: ${err.message}`, 'error');
        } finally {
            syncBtn.disabled = false;
            syncBtn.classList.remove('hidden');
            loadingWidget.classList.add('hidden');
        }
    });
}

// ==========================================
// TOAST NOTIFICATIONS
// ==========================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check';
    if (type === 'error') iconClass = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Auto remove
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==========================================
// DASHBOARD & CHARTS
// ==========================================
async function loadDashboardStats(branch = '', zone = '') {
    try {
        const params = new URLSearchParams();
        if (branch) params.append('branch', branch);
        if (zone) params.append('zone', zone);
        
        const response = await fetch(`/api/fbb/dashboard?${params.toString()}`);
        const stats = await response.json();
        
        if (!response.ok) throw new Error(stats.error || 'Failed to fetch');
        
        // Update values in UI
        document.getElementById('stat-total-zones').textContent = stats.total_zones.toLocaleString();
        document.getElementById('stat-total-ports').textContent = stats.total_ports.toLocaleString();
        document.getElementById('stat-active-cust').textContent = stats.total_active.toLocaleString();
        document.getElementById('stat-susp-cust').textContent = stats.total_suspended.toLocaleString();
        document.getElementById('stat-canc-cust').textContent = stats.total_canceled.toLocaleString();
        document.getElementById('stat-avg-sat').textContent = `${stats.avg_saturation}%`;
        
        // Populate Critical Zones Table
        const tbody = document.getElementById('critical-zones-table');
        tbody.innerHTML = '';
        if (stats.critical_zones.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No hay zonas altamente saturadas.</td></tr>';
        } else {
            stats.critical_zones.forEach(z => {
                const tr = document.createElement('tr');
                
                let satColor = 'var(--color-success)';
                if (z.saturation > 80) satColor = 'var(--color-danger)';
                else if (z.saturation > 50) satColor = 'var(--color-warning)';
                
                tr.innerHTML = `
                    <td><strong>${z.zone}</strong></td>
                    <td><span class="badge badge-secondary">${z.branch}</span></td>
                    <td>
                        <div class="sat-progress-wrapper">
                            <div class="sat-progress-bar">
                                <div class="sat-progress-fill" style="width: ${z.saturation}%; background-color: ${satColor};"></div>
                            </div>
                            <span class="sat-progress-val">${z.saturation}%</span>
                        </div>
                    </td>
                    <td>${(z.active_customers || 0).toLocaleString()}</td>
                    <td><span class="badge ${z.status_service === 'Online' ? 'badge-success' : 'badge-danger'}">${z.status_service || 'Offline'}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        // Render Charts
        renderDashboardCharts(stats);
        
    } catch (err) {
        showToast(`Error cargando métricas: ${err.message}`, 'error');
    }
}

function renderDashboardCharts(stats) {
    const defaultChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#5B6577', font: { family: 'Inter', size: 11 } }
            }
        }
    };
    
    // 1. Branch Saturation and Boxes Chart
    const branchCtx = document.getElementById('chart-branch-saturation').getContext('2d');
    if (AppState.charts.branchSaturation) AppState.charts.branchSaturation.destroy();
    
    const branches = stats.branch_distribution.map(b => b.branch);
    const branchBoxes = stats.branch_distribution.map(b => b.boxes_sum);
    const branchActive = stats.branch_distribution.map(b => b.active_sum);
    
    AppState.charts.branchSaturation = new Chart(branchCtx, {
        type: 'bar',
        data: {
            labels: branches,
            datasets: [
                {
                    label: 'Cajas de Distribución',
                    data: branchBoxes,
                    backgroundColor: 'rgba(0, 162, 232, 0.6)',
                    borderColor: 'rgba(0, 162, 232, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Clientes Activos',
                    data: branchActive,
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            ...defaultChartOptions,
            scales: {
                x: { grid: { color: 'rgba(15, 23, 42, 0.05)' }, ticks: { color: '#5B6577' } },
                y: { grid: { color: 'rgba(15, 23, 42, 0.05)' }, ticks: { color: '#5B6577' } }
            }
        }
    });
    
    // 2. Customer Ratio (Bar Chart)
    const ratioCtx = document.getElementById('chart-customer-ratio').getContext('2d');
    if (AppState.charts.customerRatio) AppState.charts.customerRatio.destroy();
    
    AppState.charts.customerRatio = new Chart(ratioCtx, {
        type: 'bar',
        data: {
            labels: ['Activos', 'Suspendidos', 'Cancelados'],
            datasets: [{
                label: 'Clientes',
                data: [stats.total_active, stats.total_suspended, stats.total_canceled],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.75)',
                    'rgba(245, 158, 11, 0.75)',
                    'rgba(239, 68, 68, 0.75)'
                ],
                borderColor: [
                    'rgba(16, 185, 129, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(239, 68, 68, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            ...defaultChartOptions,
            plugins: {
                ...defaultChartOptions.plugins,
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let value = context.raw || 0;
                            let sum = stats.total_active + stats.total_suspended + stats.total_canceled;
                            let percentage = sum > 0 ? ((value / sum) * 100).toFixed(2) + '%' : '0.00%';
                            return value.toLocaleString() + ' (' + percentage + ')';
                        }
                    }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(15, 23, 42, 0.05)' }, ticks: { color: '#5B6577' } },
                y: { grid: { color: 'rgba(15, 23, 42, 0.05)' }, ticks: { color: '#5B6577' } }
            }
        }
    });
    
    // 3. Branch Port Saturation and Cancellation Ratio Dual-Axis Chart
    const satCancelCtx = document.getElementById('chart-branch-sat-cancel-ratio');
    if (satCancelCtx) {
        const satCancelContext = satCancelCtx.getContext('2d');
        if (AppState.charts.branchSatCancelRatio) AppState.charts.branchSatCancelRatio.destroy();
        
        const branchLabels = stats.branch_distribution.map(b => b.branch);
        const branchSaturations = stats.branch_distribution.map(b => b.avg_saturation);
        const branchCancels = stats.branch_distribution.map(b => b.percent_cancel);
        const activeSums = stats.branch_distribution.map(b => b.active_sum);
        const suspendedSums = stats.branch_distribution.map(b => b.suspended_sum);
        const canceledSums = stats.branch_distribution.map(b => b.canceled_sum);
        const totalPorts = stats.branch_distribution.map(b => b.total_ports);
        
        AppState.charts.branchSatCancelRatio = new Chart(satCancelContext, {
            type: 'bar',
            data: {
                labels: branchLabels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Saturación Promedio (%)',
                        data: branchSaturations,
                        activeSums: activeSums,
                        suspendedSums: suspendedSums,
                        canceledSums: canceledSums,
                        totalPorts: totalPorts,
                        backgroundColor: 'rgba(59, 130, 246, 0.6)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        type: 'line',
                        label: 'Tasa de Cancelación (%)',
                        data: branchCancels,
                        canceledSums: canceledSums,
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgba(239, 68, 68, 1)',
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                ...defaultChartOptions,
                scales: {
                    x: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Saturación (%)',
                            color: '#5B6577',
                            font: { family: 'Inter', size: 11 }
                        },
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: {
                            color: '#5B6577',
                            callback: function(value) { return value + '%'; }
                        },
                        min: 0,
                        max: 100
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Cancelación (%)',
                            color: '#5B6577',
                            font: { family: 'Inter', size: 11 }
                        },
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#5B6577',
                            callback: function(value) { return value + '%'; }
                        },
                        min: 0
                    }
                },
                plugins: {
                    ...defaultChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toFixed(2) + '%';
                                    const index = context.dataIndex;
                                    if (context.datasetIndex === 0) {
                                        const act = context.dataset.activeSums[index] || 0;
                                        const susp = context.dataset.suspendedSums[index] || 0;
                                        const canc = context.dataset.canceledSums[index] || 0;
                                        const tot = context.dataset.totalPorts[index] || 0;
                                        const used = act + susp + canc;
                                        label += ' (' + used.toLocaleString() + ' ocupados / ' + tot.toLocaleString() + ' puertos)';
                                    } else {
                                        const act = stats.branch_distribution[index].active_sum || 0;
                                        const susp = stats.branch_distribution[index].suspended_sum || 0;
                                        const canc = context.dataset.canceledSums[index] || 0;
                                        const used = act + susp + canc;
                                        label += ' (' + canc.toLocaleString() + ' cancelados / ' + used.toLocaleString() + ' ocupados)';
                                    }
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
}

// ==========================================
// FILTERS (DROPDOWN OPTIONS)
// ==========================================
async function loadFilterOptions() {
    try {
        const response = await fetch('/api/fbb/filters');
        const data = await response.json();
        
        AppState.filters = data;
        
        // Populate branch dropdowns
        const zBranchSel = document.getElementById('zone-filter-branch');
        const bBranchSel = document.getElementById('box-filter-branch');
        const sBranchSel = document.getElementById('staff-filter-branch');
        const rBranchSel = document.getElementById('ratio-filter-branch');
        
        zBranchSel.innerHTML = '<option value="">Todas</option>';
        bBranchSel.innerHTML = '<option value="">Todas</option>';
        sBranchSel.innerHTML = '<option value="">Todas</option>';
        if (rBranchSel) rBranchSel.innerHTML = '<option value="">Sucursal</option>';
        
        data.branches.forEach(b => {
            const opt1 = `<option value="${b}">${b}</option>`;
            zBranchSel.insertAdjacentHTML('beforeend', opt1);
            bBranchSel.insertAdjacentHTML('beforeend', opt1);
            sBranchSel.insertAdjacentHTML('beforeend', opt1);
            if (rBranchSel) rBranchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
        });
        
        // Populate department dropdown
        const zDeptSel = document.getElementById('zone-filter-dept');
        zDeptSel.innerHTML = '<option value="">Todos</option>';
        data.departments.forEach(d => {
            zDeptSel.insertAdjacentHTML('beforeend', `<option value="${d}">${d}</option>`);
        });
        
        // Populate box class dropdown
        const bClassSel = document.getElementById('box-filter-class');
        bClassSel.innerHTML = '<option value="">Todas</option>';
        data.box_classes.forEach(c => {
            bClassSel.insertAdjacentHTML('beforeend', `<option value="${c}">${c}</option>`);
        });
        
        // Populate partner dropdown for staff
        const sPartnerSel = document.getElementById('staff-filter-partner');
        sPartnerSel.innerHTML = '<option value="">Todos</option>';
        data.partners.forEach(p => {
            sPartnerSel.insertAdjacentHTML('beforeend', `<option value="${p}">${p}</option>`);
        });
        
        // Stacked capacity chart filters
        const stackedBranchSel = document.getElementById('stacked-filter-branch');
        const stackedPartnerSel = document.getElementById('stacked-filter-partner');
        
        if (stackedBranchSel) {
            stackedBranchSel.innerHTML = '<option value="">Sucursal</option>';
            data.branches.forEach(b => {
                stackedBranchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
            });
        }
        
        populateStackedPartners();
        
        // Populate ZONA datalist for boxes predictive dropdown
        const bZoneList = document.getElementById('box-zone-list');
        if (bZoneList && data.zones) {
            bZoneList.innerHTML = '';
            data.zones.forEach(z => {
                bZoneList.insertAdjacentHTML('beforeend', `<option value="${z}">`);
            });
        }
        
        // Populate SITE datalist for boxes predictive dropdown
        const bSiteList = document.getElementById('box-site-list');
        if (bSiteList && data.sites) {
            bSiteList.innerHTML = '';
            data.sites.forEach(s => {
                bSiteList.insertAdjacentHTML('beforeend', `<option value="${s}">`);
            });
        }
        
    } catch (err) {
        console.error('Error loading filter options:', err);
    }
}

function initFilters() {
    // Zones Filter Listeners
    const zSearch = document.getElementById('zone-filter-search');
    const zBranch = document.getElementById('zone-filter-branch');
    const zDept = document.getElementById('zone-filter-dept');
    
    const triggerZonesReload = debounce(() => {
        AppState.zones.page = 1;
        AppState.zones.search = zSearch.value;
        AppState.zones.branch = zBranch.value;
        AppState.zones.department = zDept.value;
        loadZones();
    }, 300);
    
    zSearch.addEventListener('input', triggerZonesReload);
    zBranch.addEventListener('change', triggerZonesReload);
    zDept.addEventListener('change', triggerZonesReload);
    
    // Boxes Filter Listeners
    const bSearch = document.getElementById('box-filter-search');
    const bBranch = document.getElementById('box-filter-branch');
    const bClass = document.getElementById('box-filter-class');
    const bZone = document.getElementById('box-filter-zone');
    const bSite = document.getElementById('box-filter-site');
    
    const triggerBoxesReload = debounce(() => {
        isNearestMode = false;
        AppState.boxes.page = 1;
        AppState.boxes.search = bSearch.value;
        AppState.boxes.branch = bBranch.value;
        AppState.boxes.boxClass = bClass.value;
        AppState.boxes.zone = bZone.value;
        AppState.boxes.siteLogical = bSite.value;
        loadBoxes();
    }, 300);
    
    bSearch.addEventListener('input', triggerBoxesReload);
    bBranch.addEventListener('change', triggerBoxesReload);
    bClass.addEventListener('change', triggerBoxesReload);
    bZone.addEventListener('input', triggerBoxesReload);
    bSite.addEventListener('input', triggerBoxesReload);
    
    // Staff Filter Listeners
    const sSearch = document.getElementById('staff-filter-search');
    const sBranch = document.getElementById('staff-filter-branch');
    const sPartner = document.getElementById('staff-filter-partner');
    
    const triggerStaffReload = debounce(() => {
        AppState.staff.page = 1;
        AppState.staff.search = sSearch.value;
        AppState.staff.branch = sBranch.value;
        AppState.staff.partner = sPartner.value;
        loadStaff();
    }, 300);
    
    sSearch.addEventListener('input', triggerStaffReload);
    sBranch.addEventListener('change', triggerStaffReload);
    sPartner.addEventListener('change', triggerStaffReload);
    
    // Ratio Chart Filters (Branch -> Zone -> Stats reload)
    const rBranch = document.getElementById('ratio-filter-branch');
    const rZone = document.getElementById('ratio-filter-zone');
    
    if (rBranch && rZone) {
        rBranch.addEventListener('change', async () => {
            const branchVal = rBranch.value;
            
            // Clear and disable zone select by default
            rZone.innerHTML = '<option value="">Zona</option>';
            rZone.disabled = true;
            
            if (branchVal) {
                try {
                    const response = await fetch(`/api/fbb/branches/${encodeURIComponent(branchVal)}/zones`);
                    const zonesList = await response.json();
                    if (response.ok) {
                        rZone.disabled = false;
                        zonesList.forEach(z => {
                            rZone.insertAdjacentHTML('beforeend', `<option value="${z}">${z}</option>`);
                        });
                    }
                } catch (err) {
                    console.error('Error fetching branch zones:', err);
                }
            }
            
            // Reload dashboard stats with new branch filter
            loadDashboardStats(branchVal, '');
        });
        
        rZone.addEventListener('change', () => {
            loadDashboardStats(rBranch.value, rZone.value);
        });
    }
    
    // Stacked Capacity Chart Filters
    const stackedBranch = document.getElementById('stacked-filter-branch');
    const stackedPartner = document.getElementById('stacked-filter-partner');
    
    if (stackedBranch) {
        stackedBranch.addEventListener('change', () => {
            populateStackedPartners();
            loadStackedCapacityChart(stackedBranch.value, stackedPartner ? stackedPartner.value : '');
        });
    }
    if (stackedPartner) {
        stackedPartner.addEventListener('change', () => {
            loadStackedCapacityChart(stackedBranch ? stackedBranch.value : '', stackedPartner.value);
        });
    }
    
    // Incidents Filters
    const incidentsBranchFilter = document.getElementById('incidents-filter-branch');
    const incidentsMonthFilter = document.getElementById('incidents-filter-month');
    const incidentsWeekFilter = document.getElementById('incidents-filter-week');
    const incidentsSiteFilter = document.getElementById('incidents-filter-site');
    
    if (incidentsBranchFilter) {
        incidentsBranchFilter.addEventListener('change', async () => {
            const bVal = incidentsBranchFilter.value;
            await loadIncidentsSiteOptions(bVal);
            loadIncidents();
        });
    }
    if (incidentsMonthFilter) {
        incidentsMonthFilter.addEventListener('change', () => {
            if (incidentsMonthFilter.value && incidentsWeekFilter) {
                incidentsWeekFilter.value = '';
            }
            loadIncidents();
        });
    }
    if (incidentsWeekFilter) {
        incidentsWeekFilter.addEventListener('change', () => {
            if (incidentsWeekFilter.value && incidentsMonthFilter) {
                incidentsMonthFilter.value = '';
            }
            loadIncidents();
        });
    }
    if (incidentsSiteFilter) {
        incidentsSiteFilter.addEventListener('change', () => {
            loadIncidents();
        });
    }
}

// ==========================================
// ZONES DATA TABLE
// ==========================================
async function loadZones() {
    const z = AppState.zones;
    const params = new URLSearchParams({
        page: z.page,
        per_page: z.perPage,
        search: z.search,
        branch: z.branch,
        department: z.department,
        sort_by: z.sortBy,
        sort_dir: z.sortDir
    });
    
    try {
        const response = await fetch(`/api/fbb/zones?${params.toString()}`);
        const result = await response.json();
        
        if (!response.ok) throw new Error(result.error);
        
        const tbody = document.getElementById('zones-table-body');
        tbody.innerHTML = '';
        
        if (result.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center py-4">No se encontraron zonas coincidentes.</td></tr>';
            document.getElementById('zones-pagination-info').textContent = 'Mostrando 0 de 0 registros';
            renderPagination('zones-pagination', 1, 1, 0, handleZonesPageChange);
            return;
        }
        
        result.data.forEach(item => {
            const tr = document.createElement('tr');
            
            let satColor = 'var(--color-success)';
            let satVal = item.saturation_percent !== null ? item.saturation_percent : 0;
            if (satVal > 80) satColor = 'var(--color-danger)';
            else if (satVal > 50) satColor = 'var(--color-warning)';
            
            let satClientsVal = item.percent_saturation_formatted !== undefined && item.percent_saturation_formatted !== null ? item.percent_saturation_formatted : 0.0;
            let cancelVal = item.percent_cancel_formatted !== undefined && item.percent_cancel_formatted !== null ? item.percent_cancel_formatted : 0.0;
            
            tr.innerHTML = `
                <td><strong>${item.zone}</strong></td>
                <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
                <td>
                    <div class="sat-progress-wrapper">
                        <div class="sat-progress-bar">
                            <div class="sat-progress-fill" style="width: ${satVal}%; background-color: ${satColor};"></div>
                        </div>
                        <span class="sat-progress-val">${item.saturation_percent !== null ? item.saturation_percent + '%' : '0.00%'}</span>
                    </div>
                </td>
                <td>
                    <span class="${satClientsVal > 80 ? 'text-danger' : (satClientsVal > 50 ? 'text-warning' : 'text-success')}" style="font-weight: 600;">
                        ${satClientsVal.toFixed(2)}%
                    </span>
                </td>
                <td>
                    <span class="${cancelVal > 15 ? 'text-danger' : 'text-muted'}" style="font-weight: 500;">
                        ${cancelVal.toFixed(2)}%
                    </span>
                </td>
                <td>
                    <div class="customer-breakdown-cell" title="Activos / Suspendidos / Cancelados">
                        <span class="text-success">${(item.active_customers || 0).toLocaleString()}</span> /
                        <span class="text-warning">${(item.suspended_customers || 0).toLocaleString()}</span> /
                        <span class="text-danger">${(item.canceled_customers || 0).toLocaleString()}</span>
                    </div>
                </td>
                <td>${item.site_physical || '-'}</td>
                <td>${item.olt || '-'}</td>
                <td><span class="text-info">${item.boxes_count || 0}</span></td>
                <td><span class="badge ${item.status_service === 'Online' ? 'badge-success' : 'badge-danger'}">${item.status_service || 'Offline'}</span></td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-action btn-action-edit" onclick="editZone(${item.id})" title="Editar Zona">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn-action btn-action-delete" onclick="deleteZone(${item.id})" title="Eliminar Zona">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        const start = (z.page - 1) * z.perPage + 1;
        const end = Math.min(start + result.data.length - 1, result.total);
        document.getElementById('zones-pagination-info').textContent = `Mostrando ${start}-${end} de ${result.total} registros`;
        
        AppState.zones.total = result.total;
        renderPagination('zones-pagination', z.page, result.pages, result.total, handleZonesPageChange);
        
    } catch (err) {
        showToast(`Error cargando zonas: ${err.message}`, 'error');
    }
}

function handleZonesPageChange(newPage) {
    AppState.zones.page = newPage;
    loadZones();
}

// ==========================================
// BOXES DATA TABLE
// ==========================================
async function loadBoxes() {
    if (isNearestMode) return;
    const b = AppState.boxes;
    const params = new URLSearchParams({
        page: b.page,
        per_page: b.perPage,
        search: b.search,
        zone: b.zone,
        branch: b.branch,
        box_class: b.boxClass,
        site_logical: b.siteLogical || '',
        sort_by: b.sortBy,
        sort_dir: b.sortDir
    });
    
    try {
        const response = await fetch(`/api/fbb/boxes?${params.toString()}`);
        const result = await response.json();
        
        if (!response.ok) throw new Error(result.error);
        
        const tbody = document.getElementById('boxes-table-body');
        tbody.innerHTML = '';
        
        if (result.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">No se encontraron cajas coincidentes.</td></tr>';
            document.getElementById('boxes-pagination-info').textContent = 'Mostrando 0 de 0 registros';
            renderPagination('boxes-pagination', 1, 1, 0, handleBoxesPageChange);
            
            // Clear map markers if no data
            if (AppState.mapMarkers) {
                AppState.mapMarkers.forEach(m => m.remove());
                AppState.mapMarkers = [];
            }
            document.getElementById('map-fallback').classList.remove('hidden');
            return;
        }
        
        result.data.forEach(item => {
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.setAttribute('data-id', item.id);
            
            if (AppState.boxes.selectedBoxId === item.id) {
                tr.classList.add('table-active-row');
            }
            
            tr.addEventListener('click', (e) => {
                if (e.target.closest('.action-buttons')) return;
                
                highlightTableRow(item.id);
                
                // Focus on map marker
                const markerObj = AppState.mapMarkers.find(m => m.boxId === item.id);
                if (markerObj) {
                    AppState.map.setView(markerObj.getLatLng(), 16);
                    markerObj.openPopup();
                } else {
                    showToast(`La caja ${item.node_code} no tiene coordenadas geográficas registradas.`, 'info');
                }
            });
            
            tr.innerHTML = `
                <td><strong>${item.node_code}</strong></td>
                <td><span class="text-info">${item.zone || '-'}</span></td>
                <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
                <td><span class="text-muted" style="font-size:12px">${item.site_logical || '-'}</span></td>
                <td><span class="badge badge-secondary" style="font-size:10px">${item.box_class || '-'}</span></td>
                <td><span class="badge ${item.status_service === 'Online' ? 'badge-success' : 'badge-danger'}">${item.status_service || 'Offline'}</span></td>
                <td>${item.port_used || '-'}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-action btn-action-edit" onclick="editBox(${item.id})" title="Editar Caja">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn-action btn-action-delete" onclick="deleteBox(${item.id})" title="Eliminar Caja">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        // --- Map Rendering of Page Markers ---
        if (!AppState.map) {
            initLeafletMap();
        }
        
        // Clear previous markers
        if (AppState.mapMarkers) {
            AppState.mapMarkers.forEach(m => m.remove());
        }
        AppState.mapMarkers = [];
        
        const bounds = [];
        result.data.forEach(item => {
            const lat = parseFloat(item.latitude);
            const lng = parseFloat(item.longitude);
            
            if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                const markerColor = AppState.boxes.selectedBoxId === item.id ? 'var(--color-success)' : 'var(--color-primary)';
                const customIcon = L.divIcon({
                    className: 'custom-map-marker',
                    html: `<div style="background-color: ${markerColor}; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 10px ${markerColor};" data-box-id="${item.id}"></div>`,
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                });
                
                const marker = L.marker([lat, lng], { icon: customIcon }).addTo(AppState.map);
                marker.boxId = item.id;
                marker.boxNodeCode = item.node_code;
                
                const showNames = document.getElementById('show-names-checkbox')?.checked || false;
                if (showNames) {
                    marker.bindTooltip(item.node_code, {
                        permanent: true,
                        direction: 'top',
                        className: 'custom-map-tooltip',
                        offset: [0, -5]
                    });
                }
                
                const popupContent = `
                    <div style="font-family: var(--font-main); color: #fff; font-size:12px;">
                        <strong style="color: var(--color-primary); font-size:14px;">${item.node_code}</strong><br>
                        <b>Zona:</b> ${item.zone || '-'}<br>
                        <b>Sucursal:</b> ${item.branch || '-'}<br>
                        <b>SITE:</b> ${item.site_logical || '-'}<br>
                        <b>Clase:</b> ${item.box_class || '-'}<br>
                        <b>Estado:</b> <span style="color: ${item.status_service === 'Online' ? '#10b981' : '#ef4444'}">${item.status_service || 'Offline'}</span><br>
                        <b>Puertos:</b> ${item.port_used || '-'}<br>
                        <b>OLT:</b> ${item.olt || '-'}<br>
                        <b>Notas:</b> ${item.note || '-'}
                    </div>
                `;
                
                marker.bindPopup(popupContent, { className: 'dark-map-popup' });
                
                marker.on('click', () => {
                    highlightTableRow(item.id);
                });
                
                AppState.mapMarkers.push(marker);
                bounds.push([lat, lng]);
            }
        });
        
        const fallback = document.getElementById('map-fallback');
        if (bounds.length > 0) {
            fallback.classList.add('hidden');
            AppState.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
            
            // If a box is selected, open its popup
            if (AppState.boxes.selectedBoxId) {
                const selectedMarker = AppState.mapMarkers.find(m => m.boxId === AppState.boxes.selectedBoxId);
                if (selectedMarker) {
                    selectedMarker.openPopup();
                }
            }
        } else {
            fallback.classList.remove('hidden');
            fallback.innerHTML = `
                <i class="fa-solid fa-map-location-dot fa-3x text-warning"></i>
                <p class="mt-2">Ninguna caja de esta página tiene coordenadas registradas.</p>
            `;
        }
        
        const start = (b.page - 1) * b.perPage + 1;
        const end = Math.min(start + result.data.length - 1, result.total);
        document.getElementById('boxes-pagination-info').textContent = `Mostrando ${start}-${end} de ${result.total} registros`;
        
        AppState.boxes.total = result.total;
        renderPagination('boxes-pagination', b.page, result.pages, result.total, handleBoxesPageChange);
        
    } catch (err) {
        showToast(`Error cargando cajas: ${err.message}`, 'error');
    }
}

function highlightTableRow(boxId) {
    document.querySelectorAll('#boxes-table-body tr').forEach(r => r.classList.remove('table-active-row'));
    const targetRow = Array.from(document.querySelectorAll('#boxes-table-body tr')).find(r => r.getAttribute('data-id') === String(boxId));
    if (targetRow) {
        targetRow.classList.add('table-active-row');
    }
    AppState.boxes.selectedBoxId = boxId;
    
    // Update marker styling: highlight the active one and unhighlight the others
    if (AppState.mapMarkers) {
        AppState.mapMarkers.forEach(marker => {
            const isSelected = marker.boxId === boxId;
            const markerColor = isSelected ? 'var(--color-success)' : 'var(--color-primary)';
            const newIcon = L.divIcon({
                className: 'custom-map-marker',
                html: `<div style="background-color: ${markerColor}; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 10px ${markerColor};" data-box-id="${marker.boxId}"></div>`,
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            });
            marker.setIcon(newIcon);
        });
    }
}

function handleBoxesPageChange(newPage) {
    AppState.boxes.page = newPage;
    loadBoxes();
}

// ==========================================
// STAFF DATA TABLE
// ==========================================
async function loadStaff() {
    const s = AppState.staff;
    const params = new URLSearchParams({
        page: s.page,
        per_page: s.perPage,
        search: s.search,
        branch: s.branch,
        partner: s.partner,
        sort_by: s.sortBy,
        sort_dir: s.sortDir
    });
    
    try {
        const response = await fetch(`/api/fbb/staff?${params.toString()}`);
        const result = await response.json();
        
        if (!response.ok) throw new Error(result.error);
        
        const tbody = document.getElementById('staff-table-body');
        tbody.innerHTML = '';
        
        if (result.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">No se encontraron asignaciones de personal.</td></tr>';
            document.getElementById('staff-pagination-info').textContent = 'Mostrando 0 de 0 registros';
            renderPagination('staff-pagination', 1, 1, 0, handleStaffPageChange);
            return;
        }
        
        result.data.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${item.staff_team}</strong></td>
                <td><span class="text-info">${item.zone}</span></td>
                <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
                <td><span class="badge badge-secondary" style="font-size:10px">${item.partner || '-'}</span></td>
                <td><code>${item.vtp_username || '-'}</code></td>
                <td>${item.olt || '-'}</td>
                <td><span class="badge badge-secondary" style="font-size:10px">${item.partner_incidence || '-'}</span></td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-action btn-action-edit" onclick="editStaff(${item.id})" title="Editar Personal">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn-action btn-action-delete" onclick="deleteStaff(${item.id})" title="Eliminar Personal">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        const start = (s.page - 1) * s.perPage + 1;
        const end = Math.min(start + result.data.length - 1, result.total);
        document.getElementById('staff-pagination-info').textContent = `Mostrando ${start}-${end} de ${result.total} registros`;
        
        AppState.staff.total = result.total;
        renderPagination('staff-pagination', s.page, result.pages, result.total, handleStaffPageChange);
        
    } catch (err) {
        showToast(`Error cargando personal: ${err.message}`, 'error');
    }
}

function handleStaffPageChange(newPage) {
    AppState.staff.page = newPage;
    loadStaff();
}

// ==========================================
// PARTNER CAPACITY REPORTING
// ==========================================
async function loadPartnerCapacityReport() {
    try {
        const tbodyPartners = document.getElementById('partner-capacity-table-body');
        const tbodyZones = document.getElementById('zone-capacity-table-body');
        
        tbodyPartners.innerHTML = '<tr><td colspan="10" class="text-center py-4"><i class="fa-solid fa-spinner fa-spin"></i> Cargando resumen...</td></tr>';
        tbodyZones.innerHTML = '<tr><td colspan="10" class="text-center py-4"><i class="fa-solid fa-spinner fa-spin"></i> Cargando análisis...</td></tr>';
        
        // Fetch Partners capacity summary
        const resPartners = await fetch('/api/fbb/partners/capacity');
        const dataPartners = await resPartners.json();
        if (!resPartners.ok) throw new Error(dataPartners.error || 'Error al obtener resumen de partners.');
        
        // Fetch Detailed zones load
        const resZones = await fetch('/api/fbb/zones/capacity-detail');
        const dataZones = await resZones.json();
        if (!resZones.ok) throw new Error(dataZones.error || 'Error al obtener análisis de zonas.');
        
        // Populate Partners capacity table
        tbodyPartners.innerHTML = '';
        if (dataPartners.length === 0) {
            tbodyPartners.innerHTML = '<tr><td colspan="10" class="text-center py-4">No se encontró información de capacidad de partners.</td></tr>';
        } else {
            dataPartners.forEach(item => {
                const tr = document.createElement('tr');
                let avgSat = item.avg_saturation_percent !== null && item.avg_saturation_percent !== undefined ? item.avg_saturation_percent : 0.0;
                let activeCust = item.total_active_customers !== null && item.total_active_customers !== undefined ? item.total_active_customers : 0;
                
                tr.innerHTML = `
                    <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
                    <td><strong>${item.partner || '-'}</strong></td>
                    <td><span class="text-info">${item.assigned_olts || 0}</span></td>
                    <td>${activeCust.toLocaleString()}</td>
                    <td>${item.teams_total !== null ? item.teams_total : '-'}</td>
                    <td>${item.ft_total !== null ? item.ft_total : '-'}</td>
                    <td>${item.teams_deploy !== null ? item.teams_deploy : '-'}</td>
                    <td>${item.teams_incidents !== null ? item.teams_incidents : '-'}</td>
                    <td>${item.teams_odn !== null ? item.teams_odn : '-'}</td>
                    <td><span class="${avgSat > 80 ? 'text-danger' : (avgSat > 50 ? 'text-warning' : 'text-success')}" style="font-weight:600;">${avgSat.toFixed(2)}%</span></td>
                `;
                tbodyPartners.appendChild(tr);
            });
        }
        
        // Populate Detailed zones table
        tbodyZones.innerHTML = '';
        if (dataZones.length === 0) {
            tbodyZones.innerHTML = '<tr><td colspan="10" class="text-center py-4">No hay datos de zonas.</td></tr>';
        } else {
            dataZones.forEach(item => {
                const tr = document.createElement('tr');
                
                // Load status badge color:
                let badgeClass = 'badge-success';
                let badgeText = 'Adecuado';
                let ratioVal = item.clients_per_team;
                
                if (ratioVal === null || ratioVal === undefined) {
                    badgeClass = 'badge-secondary';
                    badgeText = 'Sin Equipos';
                } else if (ratioVal > 250) {
                    badgeClass = 'badge-danger';
                    badgeText = 'Sobrecarga';
                } else if (ratioVal > 100) {
                    badgeClass = 'badge-warning';
                    badgeText = 'Carga Media';
                }
                
                let ratioText = ratioVal !== null ? `${ratioVal.toFixed(1)}/eq.` : '-';
                
                let activeCount = item.active_customers !== null && item.active_customers !== undefined ? item.active_customers : 0;
                let satPorts = item.saturation_ports_percent !== null && item.saturation_ports_percent !== undefined ? item.saturation_ports_percent : 0.0;
                let satClients = item.saturation_clients_percent !== null && item.saturation_clients_percent !== undefined ? item.saturation_clients_percent : 0.0;
                let cancelRate = item.cancel_rate_percent !== null && item.cancel_rate_percent !== undefined ? item.cancel_rate_percent : 0.0;
                
                tr.innerHTML = `
                    <td><strong>${item.zone}</strong></td>
                    <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
                    <td>${activeCount.toLocaleString()}</td>
                    <td>${satPorts.toFixed(2)}%</td>
                    <td><span class="${satClients > 80 ? 'text-danger' : (satClients > 50 ? 'text-warning' : 'text-success')}" style="font-weight:600;">${satClients.toFixed(2)}%</span></td>
                    <td><span class="${cancelRate > 15 ? 'text-danger' : 'text-muted'}">${cancelRate.toFixed(2)}%</span></td>
                    <td><span class="badge badge-secondary" style="font-size:10px">${item.partner_deploy || '-'}</span></td>
                    <td>${item.partner_teams_deploy !== null ? item.partner_teams_deploy : '-'}</td>
                    <td><strong class="${ratioVal > 250 ? 'text-danger' : (ratioVal > 100 ? 'text-warning' : 'text-success')}">${ratioText}</strong></td>
                    <td><span class="badge ${badgeClass}">${badgeText}</span></td>
                `;
                tbodyZones.appendChild(tr);
            });
        }
    } catch (err) {
        showToast(`Error cargando reporte de capacidad: ${err.message}`, 'error');
    }
}

// ==========================================
// PAGINATION COMPONENT GENERATOR
// ==========================================
function renderPagination(containerId, currentPage, totalPages, totalCount, onPageChange) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    if (totalCount === 0 || totalPages <= 1) return;
    
    const prevBtn = document.createElement('div');
    prevBtn.className = `pagination-btn ${currentPage === 1 ? 'disabled' : ''}`;
    prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    if (currentPage > 1) {
        prevBtn.addEventListener('click', () => onPageChange(currentPage - 1));
    }
    container.appendChild(prevBtn);
    
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    if (startPage > 1) {
        const firstBtn = document.createElement('div');
        firstBtn.className = 'pagination-btn';
        firstBtn.textContent = '1';
        firstBtn.addEventListener('click', () => onPageChange(1));
        container.appendChild(firstBtn);
        
        if (startPage > 2) {
            const dots = document.createElement('div');
            dots.className = 'pagination-btn disabled';
            dots.textContent = '...';
            container.appendChild(dots);
        }
    }
    
    for (let p = startPage; p <= endPage; p++) {
        const pBtn = document.createElement('div');
        pBtn.className = `pagination-btn ${p === currentPage ? 'active' : ''}`;
        pBtn.textContent = p;
        if (p !== currentPage) {
            pBtn.addEventListener('click', () => onPageChange(p));
        }
        container.appendChild(pBtn);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const dots = document.createElement('div');
            dots.className = 'pagination-btn disabled';
            dots.textContent = '...';
            container.appendChild(dots);
        }
        const lastBtn = document.createElement('div');
        lastBtn.className = 'pagination-btn';
        lastBtn.textContent = totalPages;
        lastBtn.addEventListener('click', () => onPageChange(totalPages));
        container.appendChild(lastBtn);
    }
    
    const nextBtn = document.createElement('div');
    nextBtn.className = `pagination-btn ${currentPage === totalPages ? 'disabled' : ''}`;
    nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    if (currentPage < totalPages) {
        nextBtn.addEventListener('click', () => onPageChange(currentPage + 1));
    }
    container.appendChild(nextBtn);
}

// ==========================================
// SORTING LOGIC FOR TABLES
// ==========================================
document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
        const col = th.getAttribute('data-col');
        
        let stateObj = null;
        let reloadFn = null;
        
        if (th.closest('#zones-section')) {
            stateObj = AppState.zones;
            reloadFn = loadZones;
        } else if (th.closest('#boxes-section')) {
            stateObj = AppState.boxes;
            reloadFn = loadBoxes;
        } else {
            stateObj = AppState.staff;
            reloadFn = loadStaff;
        }
        
        if (stateObj.sortBy === col) {
            stateObj.sortDir = stateObj.sortDir === 'ASC' ? 'DESC' : 'ASC';
        } else {
            stateObj.sortBy = col;
            stateObj.sortDir = 'ASC';
        }
        
        th.closest('tr').querySelectorAll('th.sortable i').forEach(icon => {
            icon.className = 'fa-solid fa-sort';
        });
        
        const currentIcon = th.querySelector('i');
        if (stateObj.sortDir === 'ASC') {
            currentIcon.className = 'fa-solid fa-sort-up';
        } else {
            currentIcon.className = 'fa-solid fa-sort-down';
        }
        
        stateObj.page = 1;
        reloadFn();
    });
});

// ==========================================
// LEAFLET MAP INTEGRATION
// ==========================================
function initLeafletMap() {
    const mapContainer = document.getElementById('map');
    
    const defaultLat = -9.19;
    const defaultLng = -75.0152;
    
    AppState.map = L.map(mapContainer).setView([defaultLat, defaultLng], 6);
    
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(AppState.map);
    
    document.getElementById('reset-map-btn').addEventListener('click', () => {
        if (AppState.mapMarkers && AppState.mapMarkers.length > 0) {
            const bounds = AppState.mapMarkers.map(m => m.getLatLng());
            AppState.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
        } else {
            AppState.map.setView([defaultLat, defaultLng], 6);
        }
    });
    
    // Bind click events on the map for measure and capture tools
    AppState.map.on('click', (e) => {
        if (isMeasuring) {
            handleMapMeasureClick(e);
        } else if (isCapturingCoords) {
            handleMapCaptureClick(e);
        }
    });
}

// Global state variables for ruler, capture and nearest search
let isMeasuring = false;
let measurePoints = [];
let measureMarkers = [];
let measureLine = null;

let isCapturingCoords = false;
let isNearestMode = false;

// --- KML LAYER TOGGLE LOGIC ---
async function toggleKMLLayer() {
    const checkbox = document.getElementById('kml-toggle-checkbox');
    if (checkbox.checked) {
        if (AppState.coverageLayer) {
            AppState.coverageLayer.addTo(AppState.map);
            return;
        }
        
        showToast('Cargando capa de cobertura KML...', 'info');
        
        try {
            const response = await fetch('/fbb-static/coverage.geojson');
            const data = await response.json();
            
            AppState.coverageLayer = L.geoJSON(data, {
                style: {
                    color: 'var(--color-primary)',
                    weight: 1.5,
                    fillColor: 'var(--color-primary)',
                    fillOpacity: 0.1,
                    dashArray: '3'
                },
                onEachFeature: function (feature, layer) {
                    if (feature.properties && feature.properties.name) {
                        layer.bindPopup(`<div style="font-family: var(--font-main); color: #fff; font-size:12px;"><strong>Área de Cobertura:</strong><br>${feature.properties.name}</div>`, {
                            className: 'dark-map-popup'
                        });
                    }
                }
            }).addTo(AppState.map);
            
            showToast('Cobertura KML cargada exitosamente.', 'success');
        } catch (err) {
            console.error('Error loading coverage geojson:', err);
            showToast('No se pudo cargar la cobertura KML.', 'error');
            checkbox.checked = false;
        }
    } else {
        if (AppState.coverageLayer) {
            AppState.coverageLayer.remove();
        }
    }
}

// --- MEASURING TOOL LOGIC ---
function toggleMeasureTool() {
    const btn = document.getElementById('measure-tool-btn');
    const clearBtn = document.getElementById('measure-clear-btn');
    
    isMeasuring = !isMeasuring;
    
    if (isMeasuring) {
        // Deactivate coordinates capture if active
        if (isCapturingCoords) {
            toggleCoordsCapture();
        }
        
        btn.classList.add('active-measure');
        btn.innerHTML = '<i class="fa-solid fa-square-poll-vertical"></i> Parar Regla';
        clearBtn.classList.remove('hidden');
        AppState.map.getContainer().style.cursor = 'crosshair';
        showToast('Regla activa. Haz clic en el mapa para marcar puntos.', 'info');
    } else {
        btn.classList.remove('active-measure');
        btn.innerHTML = '<i class="fa-solid fa-ruler"></i> Medir Distancia';
        AppState.map.getContainer().style.cursor = '';
    }
}

function handleMapMeasureClick(e) {
    if (!isMeasuring) return;
    
    const latlng = e.latlng;
    measurePoints.push(latlng);
    
    // Add circular point marker
    const marker = L.circleMarker(latlng, {
        color: 'var(--color-warning)',
        radius: 5,
        fillColor: '#fff',
        fillOpacity: 1,
        weight: 2
    }).addTo(AppState.map);
    
    measureMarkers.push(marker);
    
    // Update line
    if (measureLine) {
        measureLine.setLatLngs(measurePoints);
    } else {
        measureLine = L.polyline(measurePoints, {
            color: 'var(--color-warning)',
            weight: 3,
            dashArray: '5, 5'
        }).addTo(AppState.map);
    }
    
    // Calculate cumulative geodesic distance
    let totalDistance = 0;
    for (let i = 1; i < measurePoints.length; i++) {
        totalDistance += measurePoints[i-1].distanceTo(measurePoints[i]);
    }
    
    const output = document.getElementById('measure-result');
    if (totalDistance < 1000) {
        output.textContent = `${totalDistance.toFixed(1)} m`;
    } else {
        output.textContent = `${(totalDistance / 1000).toFixed(2)} km`;
    }
}

function clearMeasurements() {
    measureMarkers.forEach(m => m.remove());
    measureMarkers = [];
    measurePoints = [];
    
    if (measureLine) {
        measureLine.remove();
        measureLine = null;
    }
    
    document.getElementById('measure-result').textContent = '';
    
    if (isMeasuring) {
        toggleMeasureTool();
    }
    document.getElementById('measure-clear-btn').classList.add('hidden');
}

// --- COORDINATES CAPTURE LOGIC ---
function toggleCoordsCapture() {
    const btn = document.getElementById('map-capture-btn');
    isCapturingCoords = !isCapturingCoords;
    
    if (isCapturingCoords) {
        // Deactivate measure tool if active
        if (isMeasuring) {
            toggleMeasureTool();
        }
        
        btn.classList.add('active-capture');
        btn.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Cancelar';
        AppState.map.getContainer().style.cursor = 'cell';
        showToast('Captura activa. Haz clic en el mapa para capturar coordenadas.', 'info');
    } else {
        btn.classList.remove('active-capture');
        btn.innerHTML = '<i class="fa-solid fa-crosshairs"></i> Capturar';
        AppState.map.getContainer().style.cursor = '';
    }
}

function handleMapCaptureClick(e) {
    if (!isCapturingCoords) return;
    
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    
    document.getElementById('manual-coordinates').value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    
    toggleCoordsCapture();
    
    // Automatically trigger search
    searchNearestBoxes(lat, lng);
}

// --- NEAREST BOXES LOGIC ---
async function triggerNearestSearch() {
    const coordsInput = document.getElementById('manual-coordinates').value.trim();
    if (!coordsInput) {
        showToast('Ingresa coordenadas o usa "Capturar".', 'error');
        return;
    }
    
    const parts = coordsInput.split(',');
    if (parts.length !== 2) {
        showToast('Formato incorrecto. Debe ser: Latitud, Longitud (ej. -11.979557, -76.942322)', 'error');
        return;
    }
    
    const latVal = parseFloat(parts[0].trim());
    const lngVal = parseFloat(parts[1].trim());
    
    if (isNaN(latVal) || isNaN(lngVal)) {
        showToast('Coordenadas numéricas no válidas.', 'error');
        return;
    }
    
    await searchNearestBoxes(latVal, lngVal);
}

async function searchNearestBoxes(lat, lng) {
    showToast('Buscando las 12 cajas más cercanas...', 'info');
    try {
        const response = await fetch(`/api/fbb/boxes/nearest?latitude=${lat}&longitude=${lng}&limit=12`);
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error);
        
        isNearestMode = true;
        
        renderNearestBoxesTable(data, lat, lng);
        
    } catch (err) {
        showToast(`Error al buscar cajas: ${err.message}`, 'error');
    }
}

function renderNearestBoxesTable(data, searchLat, searchLng) {
    const tbody = document.getElementById('boxes-table-body');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">No se encontraron cajas cercanas.</td></tr>';
        document.getElementById('boxes-pagination-info').textContent = 'Mostrando 0 de 0 registros (Cercanas)';
        document.getElementById('boxes-pagination').innerHTML = '';
        return;
    }
    
    data.forEach(item => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.setAttribute('data-id', item.id);
        
        if (AppState.boxes.selectedBoxId === item.id) {
            tr.classList.add('table-active-row');
        }
        
        tr.addEventListener('click', (e) => {
            if (e.target.closest('.action-buttons')) return;
            
            highlightTableRow(item.id);
            
            const markerObj = AppState.mapMarkers.find(m => m.boxId === item.id);
            if (markerObj) {
                AppState.map.setView(markerObj.getLatLng(), 16);
                markerObj.openPopup();
            } else {
                showToast(`La caja ${item.node_code} no tiene coordenadas geográficas.`, 'info');
            }
        });
        
        let distStr = '';
        const dist = parseFloat(item.dist_meters);
        if (dist < 1000) {
            distStr = `a ${dist.toFixed(0)} m`;
        } else {
            distStr = `a ${(dist / 1000).toFixed(2)} km`;
        }
        
        tr.innerHTML = `
            <td>
                <strong>${item.node_code}</strong>
                <span class="nearest-distance-badge">${distStr}</span>
            </td>
            <td><span class="text-info">${item.zone || '-'}</span></td>
            <td><span class="badge badge-secondary">${item.branch || '-'}</span></td>
            <td><span class="text-muted" style="font-size:12px">${item.site_logical || '-'}</span></td>
            <td><span class="badge badge-secondary" style="font-size:10px">${item.box_class || '-'}</span></td>
            <td><span class="badge ${item.status_service === 'Online' ? 'badge-success' : 'badge-danger'}">${item.status_service || 'Offline'}</span></td>
            <td>${item.port_used || '-'}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action btn-action-edit" onclick="editBox(${item.id})" title="Editar Caja">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn-action btn-action-delete" onclick="deleteBox(${item.id})" title="Eliminar Caja">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    document.getElementById('boxes-pagination-info').textContent = `Mostrando las ${data.length} cajas más cercanas`;
    
    const pagContainer = document.getElementById('boxes-pagination');
    pagContainer.innerHTML = `
        <button id="clear-nearest-mode-btn" class="btn btn-secondary btn-xs" style="margin-top:10px;">
            <i class="fa-solid fa-arrow-left"></i> Volver a Lista General
        </button>
    `;
    document.getElementById('clear-nearest-mode-btn').addEventListener('click', () => {
        isNearestMode = false;
        loadBoxes();
    });
    
    // --- Plot on Map ---
    if (!AppState.map) {
        initLeafletMap();
    }
    
    if (AppState.mapMarkers) {
        AppState.mapMarkers.forEach(m => m.remove());
    }
    AppState.mapMarkers = [];
    
    const bounds = [];
    
    // Add reference center marker
    const refIcon = L.divIcon({
        className: 'ref-search-marker',
        html: `<div style="background-color: var(--color-danger); width: 16px; height: 16px; border-radius: 50%; border: 3px solid #fff; box-shadow: 0 0 12px var(--color-danger);"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });
    const refMarker = L.marker([searchLat, searchLng], { icon: refIcon }).addTo(AppState.map);
    refMarker.bindPopup(`<div style="font-family: var(--font-main); color: #fff; font-size:12px;"><strong>Punto de Búsqueda</strong><br>Lat: ${searchLat.toFixed(5)}<br>Lng: ${searchLng.toFixed(5)}</div>`, {
        className: 'dark-map-popup'
    }).openPopup();
    AppState.mapMarkers.push(refMarker);
    bounds.push([searchLat, searchLng]);
    
    // Add closest boxes markers
    data.forEach(item => {
        const lat = parseFloat(item.latitude);
        const lng = parseFloat(item.longitude);
        
        if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
            const markerColor = AppState.boxes.selectedBoxId === item.id ? 'var(--color-success)' : 'var(--color-primary)';
            const customIcon = L.divIcon({
                className: 'custom-map-marker',
                html: `<div style="background-color: ${markerColor}; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 10px ${markerColor};" data-box-id="${item.id}"></div>`,
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            });
            
            const marker = L.marker([lat, lng], { icon: customIcon }).addTo(AppState.map);
            marker.boxId = item.id;
            marker.boxNodeCode = item.node_code;
            
            const showNames = document.getElementById('show-names-checkbox')?.checked || false;
            if (showNames) {
                marker.bindTooltip(item.node_code, {
                    permanent: true,
                    direction: 'top',
                    className: 'custom-map-tooltip',
                    offset: [0, -5]
                });
            }
            
            let distStr = '';
            const dist = parseFloat(item.dist_meters);
            if (dist < 1000) {
                distStr = `${dist.toFixed(0)} metros`;
            } else {
                distStr = `${(dist / 1000).toFixed(2)} km`;
            }
            
            const popupContent = `
                <div style="font-family: var(--font-main); color: #fff; font-size:12px;">
                    <strong style="color: var(--color-primary); font-size:14px;">${item.node_code}</strong><br>
                    <b style="color: var(--color-success);">Distancia: ${distStr}</b><br>
                    <b>Zona:</b> ${item.zone || '-'}<br>
                    <b>Sucursal:</b> ${item.branch || '-'}<br>
                    <b>SITE:</b> ${item.site_logical || '-'}<br>
                    <b>Clase:</b> ${item.box_class || '-'}<br>
                    <b>Estado:</b> <span style="color: ${item.status_service === 'Online' ? '#10b981' : '#ef4444'}">${item.status_service || 'Offline'}</span><br>
                    <b>Puertos:</b> ${item.port_used || '-'}<br>
                    <b>OLT:</b> ${item.olt || '-'}<br>
                    <b>Notas:</b> ${item.note || '-'}
                </div>
            `;
            
            marker.bindPopup(popupContent, { className: 'dark-map-popup' });
            
            marker.on('click', () => {
                highlightTableRow(item.id);
            });
            
            AppState.mapMarkers.push(marker);
            bounds.push([lat, lng]);
        }
    });
    
    document.getElementById('map-fallback').classList.add('hidden');
    AppState.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
}

// --- INIT MAP CONTROLS DOM LISTENERS ---
function initMapControls() {
    const kmlCheckbox = document.getElementById('kml-toggle-checkbox');
    if (kmlCheckbox) {
        kmlCheckbox.addEventListener('change', toggleKMLLayer);
    }
    
    const measureBtn = document.getElementById('measure-tool-btn');
    if (measureBtn) {
        measureBtn.addEventListener('click', toggleMeasureTool);
    }
    
    const clearBtn = document.getElementById('measure-clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearMeasurements);
    }
    
    const captureBtn = document.getElementById('map-capture-btn');
    if (captureBtn) {
        captureBtn.addEventListener('click', toggleCoordsCapture);
    }
    
    const searchNearestBtn = document.getElementById('search-nearest-btn');
    if (searchNearestBtn) {
        searchNearestBtn.addEventListener('click', triggerNearestSearch);
    }

    // Toggle de Pantalla Completa para el Mapa
    const fullscreenBtn = document.getElementById('toggle-fullscreen-map-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            const mapCard = document.querySelector('.map-card');
            if (mapCard) {
                const isFullscreen = mapCard.classList.toggle('fullscreen');
                
                if (isFullscreen) {
                    fullscreenBtn.innerHTML = '<i class="fa-solid fa-compress"></i> Minimizar';
                } else {
                    fullscreenBtn.innerHTML = '<i class="fa-solid fa-expand"></i> Maximizar';
                }
                
                // Forzar a Leaflet a recalcular dimensiones
                setTimeout(() => {
                    if (AppState.map) {
                        AppState.map.invalidateSize();
                    }
                }, 100);
            }
        });
    }

    // Toggle de Mostrar Nombres en el Mapa
    const showNamesCheckbox = document.getElementById('show-names-checkbox');
    if (showNamesCheckbox) {
        showNamesCheckbox.addEventListener('change', toggleBoxNamesOnMap);
    }
}

function toggleBoxNamesOnMap() {
    const showNames = document.getElementById('show-names-checkbox')?.checked || false;
    
    if (AppState.mapMarkers) {
        AppState.mapMarkers.forEach(marker => {
            if (marker.boxNodeCode) {
                if (showNames) {
                    marker.bindTooltip(marker.boxNodeCode, {
                        permanent: true,
                        direction: 'top',
                        className: 'custom-map-tooltip',
                        offset: [0, -5]
                    }).openTooltip();
                } else {
                    marker.unbindTooltip();
                }
            }
        });
    }
}

// ==========================================
// ADD & EDIT MODAL OPERATIONAL LOGIC
// ==========================================
function initModals() {
    const closeBtns = document.querySelectorAll('.modal-close, .modal-close-btn');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal-overlay').forEach(overlay => {
                overlay.classList.remove('active');
            });
        });
    });
    
    // Save buttons
    document.getElementById('save-zone-btn').addEventListener('click', saveZone);
    document.getElementById('save-box-btn').addEventListener('click', saveBox);
    document.getElementById('save-staff-btn').addEventListener('click', saveStaff);
    
    // Add buttons
    document.getElementById('add-zone-btn').addEventListener('click', () => {
        document.getElementById('zone-form').reset();
        document.getElementById('zone-form-id').value = '';
        document.getElementById('zone-modal-title').textContent = 'Agregar Nueva Zona';
        
        // Clear assigned staff read-only inputs
        document.getElementById('zf-staff-team').value = 'No aplica (Nueva Zona)';
        document.getElementById('zf-staff-vtp').value = '-';
        document.getElementById('zf-staff-partner').value = '-';
        document.getElementById('zf-staff-partner-inc').value = '-';
        
        document.getElementById('zone-modal').classList.add('active');
    });
    
    document.getElementById('add-box-btn').addEventListener('click', () => {
        document.getElementById('box-form').reset();
        document.getElementById('box-form-id').value = '';
        document.getElementById('box-modal-title').textContent = 'Agregar Nueva Caja';
        document.getElementById('box-modal').classList.add('active');
    });
    
    document.getElementById('add-staff-btn').addEventListener('click', () => {
        document.getElementById('staff-form').reset();
        document.getElementById('staff-form-id').value = '';
        document.getElementById('staff-modal-title').textContent = 'Agregar Nuevo Personal';
        document.getElementById('staff-modal').classList.add('active');
    });

    // Exportar Plantilla Staff
    const exportBtn = document.getElementById('staff-export-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            window.location.href = '/api/fbb/staff/export';
        });
    }

    // Importar Datos Staff (disparar file input)
    const importBtn = document.getElementById('staff-import-btn');
    const importFile = document.getElementById('staff-import-file');
    if (importBtn && importFile) {
        importBtn.addEventListener('click', () => {
            importFile.click();
        });

        importFile.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            showToast('Importando plantilla de personal...', 'info');

            try {
                const response = await fetch('/api/fbb/staff/import', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (response.ok) {
                    let msg = `Plantilla procesada. Creados: ${result.created}, Actualizados: ${result.updated}.`;
                    if (result.errors && result.errors.length > 0) {
                        msg += ` Hubo ${result.errors.length} errores (ver detalles en consola).`;
                        console.error('Errores en importación:', result.errors);
                        showToast(msg, 'warning');
                    } else {
                        showToast(msg, 'success');
                    }
                    loadStaff();
                } else {
                    showToast(`Error al importar: ${result.error}`, 'error');
                }
            } catch (err) {
                showToast(`Error de conexión: ${err.message}`, 'error');
            } finally {
                importFile.value = '';
            }
        });
    }
}

// --- ZONE ACTIONS ---
async function editZone(zoneId) {
    try {
        const response = await fetch(`/api/fbb/zones/${zoneId}`);
        const zone = await response.json();
        
        if (!response.ok) throw new Error(zone.error);
        
        // Fill form
        document.getElementById('zone-form-id').value = zone.id;
        document.getElementById('zf-zone').value = zone.zone || '';
        document.getElementById('zf-branch').value = zone.branch || '';
        document.getElementById('zf-saturation').value = zone.saturation_percent || '';
        document.getElementById('zf-active').value = zone.active_customers || '';
        document.getElementById('zf-suspended').value = zone.suspended_customers || '';
        document.getElementById('zf-canceled').value = zone.canceled_customers || '';
        document.getElementById('zf-site-phys').value = zone.site_physical || '';
        document.getElementById('zf-site-log').value = zone.site_logical || '';
        document.getElementById('zf-olt').value = zone.olt || '';
        document.getElementById('zf-infrastructure').value = zone.type_infrastructure || '';
        document.getElementById('zf-status').value = zone.status_service || 'Online';
        document.getElementById('zf-boxes-count').value = zone.boxes_count || '';
        document.getElementById('zf-dept').value = zone.department || '';
        document.getElementById('zf-province').value = zone.province || '';
        document.getElementById('zf-district').value = zone.district || '';
        document.getElementById('zf-note').value = zone.note || '';
        
        // Fill assigned staff read-only info
        if (zone.staff) {
            document.getElementById('zf-staff-team').value = zone.staff.staff_team || 'Sin asignar';
            document.getElementById('zf-staff-vtp').value = zone.staff.vtp_username || '-';
            document.getElementById('zf-staff-partner').value = zone.staff.partner || '-';
            document.getElementById('zf-staff-partner-inc').value = zone.staff.partner_incidence || '-';
        } else {
            document.getElementById('zf-staff-team').value = 'Sin personal asignado';
            document.getElementById('zf-staff-vtp').value = '-';
            document.getElementById('zf-staff-partner').value = '-';
            document.getElementById('zf-staff-partner-inc').value = '-';
        }
        
        document.getElementById('zone-modal-title').textContent = 'Editar Zona';
        document.getElementById('zone-modal').classList.add('active');
        
    } catch (err) {
        showToast(`Error al cargar zona: ${err.message}`, 'error');
    }
}

async function saveZone() {
    const zoneId = document.getElementById('zone-form-id').value;
    const isEdit = zoneId !== '';
    
    const zoneName = document.getElementById('zf-zone').value.trim();
    const branchName = document.getElementById('zf-branch').value.trim();
    
    if (!zoneName || !branchName) {
        showToast('Por favor, completa los campos obligatorios (*)', 'error');
        return;
    }
    
    const data = {
        zone: zoneName,
        branch: branchName,
        saturation: document.getElementById('zf-saturation').value ? parseFloat(document.getElementById('zf-saturation').value) : null,
        active_customers: document.getElementById('zf-active').value ? parseInt(document.getElementById('zf-active').value) : null,
        suspended_customers: document.getElementById('zf-suspended').value ? parseInt(document.getElementById('zf-suspended').value) : null,
        canceled_customers: document.getElementById('zf-canceled').value ? parseInt(document.getElementById('zf-canceled').value) : null,
        site_physical: document.getElementById('zf-site-phys').value.trim(),
        site_logical: document.getElementById('zf-site-log').value.trim(),
        olt: document.getElementById('zf-olt').value.trim(),
        type_infrastructure: document.getElementById('zf-infrastructure').value.trim(),
        status_service: document.getElementById('zf-status').value,
        boxes_count: document.getElementById('zf-boxes-count').value ? parseInt(document.getElementById('zf-boxes-count').value) : null,
        department: document.getElementById('zf-dept').value.trim(),
        province: document.getElementById('zf-province').value.trim(),
        district: document.getElementById('zf-district').value.trim(),
        note: document.getElementById('zf-note').value.trim()
    };
    
    const url = isEdit ? `/api/fbb/zones/${zoneId}` : '/api/fbb/zones';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        
        if (response.ok) {
            showToast(isEdit ? 'Zona actualizada exitosamente' : 'Zona creada exitosamente', 'success');
            document.getElementById('zone-modal').classList.remove('active');
            loadDashboardStats();
            loadZones();
        } else {
            showToast(`Error al guardar: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

async function deleteZone(zoneId) {
    if (!confirm('¿Estás seguro de que deseas eliminar esta zona? Esta acción no se puede deshacer.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/fbb/zones/${zoneId}`, { method: 'DELETE' });
        const result = await response.json();
        
        if (response.ok) {
            showToast('Zona eliminada exitosamente', 'success');
            loadDashboardStats();
            loadZones();
        } else {
            showToast(`Error: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

// --- BOX ACTIONS ---
async function editBox(boxId) {
    try {
        const response = await fetch(`/api/fbb/boxes/${boxId}`);
        const box = await response.json();
        
        if (!response.ok) throw new Error(box.error);
        
        document.getElementById('box-form-id').value = box.id;
        document.getElementById('bf-node-code').value = box.node_code || '';
        document.getElementById('bf-zone').value = box.zone || '';
        document.getElementById('bf-branch').value = box.branch || '';
        document.getElementById('bf-class').value = box.box_class || '';
        document.getElementById('bf-type').value = box.box_type || '';
        document.getElementById('bf-status').value = box.status_service || 'Online';
        document.getElementById('bf-latitude').value = box.latitude || '';
        document.getElementById('bf-longitude').value = box.longitude || '';
        document.getElementById('bf-olt').value = box.olt || '';
        document.getElementById('bf-ports-used').value = box.port_used || '';
        document.getElementById('bf-infrastructure').value = box.infrastructure || '';
        document.getElementById('bf-site-phys').value = box.site_physical || '';
        document.getElementById('bf-site-log').value = box.site_logical || '';
        document.getElementById('bf-note').value = box.note || '';
        
        document.getElementById('box-modal-title').textContent = 'Editar Caja';
        document.getElementById('box-modal').classList.add('active');
        
    } catch (err) {
        showToast(`Error al cargar caja: ${err.message}`, 'error');
    }
}

async function saveBox() {
    const boxId = document.getElementById('box-form-id').value;
    const isEdit = boxId !== '';
    
    const nodeCode = document.getElementById('bf-node-code').value.trim();
    const zoneName = document.getElementById('bf-zone').value.trim();
    const branchName = document.getElementById('bf-branch').value.trim();
    
    if (!nodeCode || !zoneName || !branchName) {
        showToast('Por favor, completa los campos obligatorios (*)', 'error');
        return;
    }
    
    const data = {
        node_code: nodeCode,
        zone: zoneName,
        branch: branchName,
        box_class: document.getElementById('bf-class').value.trim(),
        box_type: document.getElementById('bf-type').value.trim(),
        status_service: document.getElementById('bf-status').value,
        latitude: document.getElementById('bf-latitude').value ? parseFloat(document.getElementById('bf-latitude').value) : null,
        longitude: document.getElementById('bf-longitude').value ? parseFloat(document.getElementById('bf-longitude').value) : null,
        olt: document.getElementById('bf-olt').value.trim(),
        port_used: document.getElementById('bf-ports-used').value.trim(),
        infrastructure: document.getElementById('bf-infrastructure').value.trim(),
        site_physical: document.getElementById('bf-site-phys').value.trim(),
        site_logical: document.getElementById('bf-site-log').value.trim(),
        note: document.getElementById('bf-note').value.trim()
    };
    
    const url = isEdit ? `/api/fbb/boxes/${boxId}` : '/api/fbb/boxes';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        
        if (response.ok) {
            showToast(isEdit ? 'Caja actualizada exitosamente' : 'Caja creada exitosamente', 'success');
            document.getElementById('box-modal').classList.remove('active');
            loadDashboardStats();
            loadBoxes();
        } else {
            showToast(`Error al guardar: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

async function deleteBox(boxId) {
    if (!confirm('¿Estás seguro de que deseas eliminar esta caja? Esta acción no se puede deshacer.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/fbb/boxes/${boxId}`, { method: 'DELETE' });
        const result = await response.json();
        
        if (response.ok) {
            showToast('Caja eliminada exitosamente', 'success');
            
            isNearestMode = false;
            if (AppState.boxes.selectedBoxId === boxId) {
                AppState.boxes.selectedBoxId = null;
            }
            
            loadDashboardStats();
            loadBoxes();
        } else {
            showToast(`Error: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

// --- STAFF ACTIONS ---
async function editStaff(staffId) {
    try {
        const response = await fetch(`/api/fbb/staff/${staffId}`);
        const member = await response.json();
        
        if (!response.ok) throw new Error(member.error);
        
        document.getElementById('staff-form-id').value = member.id;
        document.getElementById('sf-staff-team').value = member.staff_team || '';
        document.getElementById('sf-vtp-username').value = member.vtp_username || '';
        document.getElementById('sf-zone').value = member.zone || '';
        document.getElementById('sf-branch').value = member.branch || '';
        document.getElementById('sf-olt').value = member.olt || '';
        document.getElementById('sf-partner').value = member.partner || '';
        document.getElementById('sf-partner-incidence').value = member.partner_incidence || '';
        document.getElementById('sf-warranty').value = member.warranty_period || '';
        document.getElementById('sf-site').value = member.site || '';
        document.getElementById('sf-site-code').value = member.site_code || '';
        document.getElementById('sf-team-dist').value = member.team_distribution || '';
        document.getElementById('sf-incidents-dist').value = member.incidents_distribution || '';
        document.getElementById('sf-incidents-dist-team').value = member.incidents_distribution_by_team || '';
        
        document.getElementById('staff-modal-title').textContent = 'Editar Asignación de Personal';
        document.getElementById('staff-modal').classList.add('active');
        
    } catch (err) {
        showToast(`Error al cargar asignación: ${err.message}`, 'error');
    }
}

async function saveStaff() {
    const staffId = document.getElementById('staff-form-id').value;
    const isEdit = staffId !== '';
    
    const staffTeam = document.getElementById('sf-staff-team').value.trim();
    const zoneName = document.getElementById('sf-zone').value.trim();
    
    if (!staffTeam || !zoneName) {
        showToast('Por favor, completa los campos obligatorios (*)', 'error');
        return;
    }
    
    const data = {
        staff_team: staffTeam,
        zone: zoneName,
        branch: document.getElementById('sf-branch').value.trim(),
        olt: document.getElementById('sf-olt').value.trim(),
        vtp_username: document.getElementById('sf-vtp-username').value.trim(),
        partner: document.getElementById('sf-partner').value.trim(),
        partner_incidence: document.getElementById('sf-partner-incidence').value.trim(),
        warranty_period: document.getElementById('sf-warranty').value ? parseInt(document.getElementById('sf-warranty').value) : null,
        site: document.getElementById('sf-site').value.trim(),
        site_code: document.getElementById('sf-site-code').value.trim(),
        team_distribution: document.getElementById('sf-team-dist').value.trim(),
        incidents_distribution: document.getElementById('sf-incidents-dist').value.trim(),
        incidents_distribution_by_team: document.getElementById('sf-incidents-dist-team').value.trim()
    };
    
    const url = isEdit ? `/api/fbb/staff/${staffId}` : '/api/fbb/staff';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        
        if (response.ok) {
            showToast(isEdit ? 'Asignación actualizada' : 'Asignación creada', 'success');
            document.getElementById('staff-modal').classList.remove('active');
            loadStaff();
        } else {
            showToast(`Error al guardar: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

async function deleteStaff(staffId) {
    if (!confirm('¿Estás seguro de que deseas eliminar este registro de personal? Esta acción no se puede deshacer.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/fbb/staff/${staffId}`, { method: 'DELETE' });
        const result = await response.json();
        
        if (response.ok) {
            showToast('Asignación de personal eliminada', 'success');
            loadStaff();
        } else {
            showToast(`Error: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

// ==========================================
// UTILITIES
// ==========================================
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

async function loadStackedCapacityChart(branch = '', partner = '') {
    try {
        const params = new URLSearchParams();
        if (branch) params.append('branch', branch);
        if (partner) params.append('partner', partner);
        
        const response = await fetch(`/api/fbb/charts/branch-capacity-stacked?${params.toString()}`);
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Failed to fetch stacked capacity');
        
        const canvas = document.getElementById('chart-branch-capacity-stacked');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        if (AppState.charts.branchCapacityStacked) {
            AppState.charts.branchCapacityStacked.destroy();
        }
        
        const branches = data.map(item => item.branch);
        const activePcts = data.map(item => item.active_pct);
        const activeCounts = data.map(item => item.active);
        const suspendedPcts = data.map(item => item.suspended_pct);
        const suspendedCounts = data.map(item => item.suspended);
        const canceledPcts = data.map(item => item.canceled_pct);
        const canceledCounts = data.map(item => item.canceled);
        const freePcts = data.map(item => item.free_pct);
        const freeCounts = data.map(item => item.free_ports);
        
        AppState.charts.branchCapacityStacked = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: branches,
                datasets: [
                    {
                        label: 'Activos',
                        data: activePcts,
                        absoluteData: activeCounts,
                        backgroundColor: 'rgba(16, 185, 129, 0.75)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Suspendidos',
                        data: suspendedPcts,
                        absoluteData: suspendedCounts,
                        backgroundColor: 'rgba(245, 158, 11, 0.75)',
                        borderColor: 'rgba(245, 158, 11, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Cancelados',
                        data: canceledPcts,
                        absoluteData: canceledCounts,
                        backgroundColor: 'rgba(239, 68, 68, 0.75)',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Puertos Libres',
                        data: freePcts,
                        absoluteData: freeCounts,
                        backgroundColor: 'rgba(107, 114, 128, 0.5)',
                        borderColor: 'rgba(107, 114, 128, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (e, activeElements, chart) => {
                    if (activeElements && activeElements.length > 0) {
                        const firstPoint = activeElements[0];
                        const label = chart.data.labels[firstPoint.index];
                        
                        const stackedBranch = document.getElementById('stacked-filter-branch');
                        const stackedPartner = document.getElementById('stacked-filter-partner');
                        
                        if (stackedBranch && !stackedBranch.value) {
                            stackedBranch.value = label;
                            populateStackedPartners();
                            loadStackedCapacityChart(stackedBranch.value, '');
                        } else if (stackedPartner && !stackedPartner.value) {
                            stackedPartner.value = label;
                            loadStackedCapacityChart(stackedBranch ? stackedBranch.value : '', stackedPartner.value);
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y: {
                        stacked: true,
                        max: 100,
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: {
                            color: '#5B6577',
                            callback: function(value) { return value + '%'; }
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#5B6577', font: { family: 'Inter', size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                let pctValue = context.raw || 0;
                                let absValue = context.dataset.absoluteData[context.dataIndex] || 0;
                                return label + pctValue.toFixed(2) + '% (' + absValue.toLocaleString() + ')';
                            }
                        }
                    }
                }
            },
            plugins: [{
                id: 'barLabels',
                afterDatasetsDraw(chart, args, options) {
                    const { ctx } = chart;
                    chart.data.datasets.forEach((dataset, datasetIndex) => {
                        const meta = chart.getDatasetMeta(datasetIndex);
                        meta.data.forEach((element, index) => {
                            const value = dataset.data[index];
                            const height = Math.abs(element.base - element.y);
                            
                            // Only draw inside if segment is visible and percentage >= 5%
                            if (value >= 5 && height > 16) {
                                ctx.save();
                                ctx.fillStyle = '#ffffff';
                                ctx.font = 'bold 9px Inter';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                
                                const x = element.x;
                                const centerY = (element.y + element.base) / 2;
                                ctx.fillText(value.toFixed(0) + '%', x, centerY);
                                ctx.restore();
                            }
                        });
                    });
                }
            }]
        });
    } catch (err) {
        console.error('Error rendering stacked capacity chart:', err);
    }
}

async function loadIncidentsMonthsOptions() {
    try {
        const monthSel = document.getElementById('incidents-filter-month');
        if (!monthSel || monthSel.options.length > 1) return;
        
        const response = await fetch('/api/fbb/incidents/months');
        const months = await response.json();
        
        monthSel.innerHTML = '<option value="">Todos los meses</option>';
        months.forEach(m => {
            monthSel.insertAdjacentHTML('beforeend', `<option value="${m}">${m}</option>`);
        });
    } catch (err) {
        console.error('Error loading months:', err);
    }
}

async function loadIncidentsWeeksOptions() {
    try {
        const weekSel = document.getElementById('incidents-filter-week');
        if (!weekSel || weekSel.options.length > 1) return;
        
        const response = await fetch('/api/fbb/incidents/weeks');
        const weeks = await response.json();
        
        weekSel.innerHTML = '<option value="">Todas las semanas</option>';
        weeks.forEach(w => {
            weekSel.insertAdjacentHTML('beforeend', `<option value="${w}">${w}</option>`);
        });
    } catch (err) {
        console.error('Error loading weeks:', err);
    }
}

async function loadIncidentsSiteOptions(branch = '') {
    try {
        const siteSel = document.getElementById('incidents-filter-site');
        if (!siteSel) return;
        
        const response = await fetch(`/api/fbb/incidents/sites?branch=${encodeURIComponent(branch)}`);
        const sites = await response.json();
        
        siteSel.innerHTML = '<option value="">Todos los Sites</option>';
        sites.forEach(s => {
            siteSel.insertAdjacentHTML('beforeend', `<option value="${s}">${s}</option>`);
        });
    } catch (err) {
        console.error('Error loading incidents sites:', err);
    }
}

async function loadIncidents() {
    try {
        const branchVal = document.getElementById('incidents-filter-branch')?.value || '';
        const monthVal = document.getElementById('incidents-filter-month')?.value || '';
        const weekVal = document.getElementById('incidents-filter-week')?.value || '';
        const siteVal = document.getElementById('incidents-filter-site')?.value || '';
        
        const params = new URLSearchParams();
        if (branchVal) params.append('branch', branchVal);
        if (weekVal) {
            params.append('week', weekVal);
        } else if (monthVal) {
            params.append('month', monthVal);
        }
        if (siteVal) params.append('site', siteVal);
        
        const response = await fetch(`/api/fbb/incidents/stats?${params.toString()}`);
        const result = await response.json();
        
        if (!response.ok) throw new Error(result.error || 'Failed to fetch incident stats');
        
        // 1. Populate KPIs
        document.getElementById('incidents-stat-total').textContent = result.kpis.total_incidents.toLocaleString();
        document.getElementById('incidents-stat-clients').textContent = result.kpis.unique_clients.toLocaleString();
        document.getElementById('incidents-stat-frequent').textContent = result.kpis.most_frequent_status;
        document.getElementById('incidents-stat-frequent').title = result.kpis.most_frequent_status;
        
        // 2. Populate Failure Types Table
        const typesTbody = document.getElementById('incidents-types-table-body');
        typesTbody.innerHTML = '';
        if (result.status.length === 0) {
            typesTbody.innerHTML = '<tr><td colspan="3" class="text-center">No hay datos de averías.</td></tr>';
        } else {
            result.status.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${item.status_desc}</strong></td>
                    <td>${item.count.toLocaleString()}</td>
                    <td>
                        <span class="text-info" style="font-weight:600;">${item.percentage.toFixed(2)}%</span>
                    </td>
                `;
                typesTbody.appendChild(tr);
            });
        }
        
        // 3. Populate Sites Ranking Table
        const rankingTbody = document.getElementById('incidents-ranking-table-body');
        rankingTbody.innerHTML = '';
        if (result.ranking.length === 0) {
            rankingTbody.innerHTML = '<tr><td colspan="3" class="text-center">No hay datos de ranking.</td></tr>';
        } else {
            result.ranking.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${item.site}</strong></td>
                    <td>${item.total_incidents.toLocaleString()}</td>
                    <td>${item.unique_clients.toLocaleString()}</td>
                `;
                rankingTbody.appendChild(tr);
            });
        }
        
        // 4. Render Failure Types Comparison Chart (Filtro Activo)
        renderIncidentTypesComparisonChart(result.status);
        
        // 5. Render Stacked Failure Types per Site Chart (Top 10 Sites)
        renderStackedIncidentChart('chart-incidents-site', result.site_breakdown, 'station_code', 'incidentsSite');
        
        // 6. Load Outages & Cancellations Report (FTTH)
        await loadSiteOutagesReport(branchVal, monthVal, siteVal, weekVal);
        
    } catch (err) {
        showToast(`Error cargando reportes de incidentes: ${err.message}`, 'error');
    }
}

function renderStackedIncidentChart(canvasId, rawData, keyField, chartInstanceKey) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    if (AppState.charts[chartInstanceKey]) {
        AppState.charts[chartInstanceKey].destroy();
    }
    
    const labels = [...new Set(rawData.map(item => item[keyField]))];
    const statuses = [...new Set(rawData.map(item => item.status_desc))];
    
    const colors = [
        'rgba(239, 68, 68, 0.75)',   // red
        'rgba(59, 130, 246, 0.75)',  // blue
        'rgba(245, 158, 11, 0.75)',  // orange
        'rgba(16, 185, 129, 0.75)',  // green
        'rgba(139, 92, 246, 0.75)',  // purple
        'rgba(236, 72, 153, 0.75)',  // pink
        'rgba(20, 184, 166, 0.75)',  // teal
        'rgba(156, 163, 175, 0.75)'  // grey
    ];
    
    const datasets = statuses.map((status, index) => {
        const color = colors[index % colors.length];
        const datasetData = labels.map(label => {
            const match = rawData.find(item => item[keyField] === label && item.status_desc === status);
            return match ? match.count : 0;
        });
        return {
            label: status,
            data: datasetData,
            backgroundColor: color,
            borderColor: color.replace('0.75', '1'),
            borderWidth: 1
        };
    });
    
    AppState.charts[chartInstanceKey] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            indexAxis: canvasId === 'chart-incidents-site' ? 'y' : 'x',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                    grid: { color: 'rgba(15, 23, 42, 0.05)' },
                    ticks: { color: '#5B6577' }
                },
                y: {
                    stacked: true,
                    grid: { color: 'rgba(15, 23, 42, 0.05)' },
                    ticks: { color: '#5B6577' }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { 
                        color: '#5B6577', 
                        font: { family: 'Inter', size: 10 },
                        boxWidth: 12
                    }
                }
            }
        }
    });
}

function renderIncidentTypesComparisonChart(statusData) {
    const canvas = document.getElementById('chart-incidents-types-comparison');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (AppState.charts.incidentsComparison) {
        AppState.charts.incidentsComparison.destroy();
    }

    const labels = statusData.map(item => item.status_desc);
    const data = statusData.map(item => item.count);

    const colors = [
        'rgba(239, 68, 68, 0.75)',   // red
        'rgba(59, 130, 246, 0.75)',  // blue
        'rgba(245, 158, 11, 0.75)',  // orange
        'rgba(16, 185, 129, 0.75)',  // green
        'rgba(139, 92, 246, 0.75)',  // purple
        'rgba(236, 72, 153, 0.75)',  // pink
        'rgba(20, 184, 166, 0.75)',  // teal
        'rgba(156, 163, 175, 0.75)'  // grey
    ];
    
    const backgroundColors = labels.map((_, index) => colors[index % colors.length]);
    const borderColors = backgroundColors.map(c => c.replace('0.75', '1'));

    AppState.charts.incidentsComparison = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cantidad de Averías',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let val = context.raw || 0;
                            let sum = data.reduce((a, b) => a + b, 0);
                            let pct = sum > 0 ? ((val / sum) * 100).toFixed(2) + '%' : '0.00%';
                            return val.toLocaleString() + ' (' + pct + ')';
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(15, 23, 42, 0.05)' },
                    ticks: { color: '#5B6577' }
                },
                y: {
                    grid: { display: false },
                    ticks: { 
                        color: '#5B6577', 
                        font: { family: 'Inter', size: 9 },
                        autoSkip: false
                    }
                }
            }
        }
    });
}

let currentOutagesData = [];

async function loadSiteOutagesReport(branch, month, site, week) {
    try {
        const params = new URLSearchParams();
        if (branch) params.append('branch', branch);
        if (week) {
            params.append('week', week);
        } else if (month) {
            params.append('month', month);
        }
        if (site) params.append('site', site);
        
        const response = await fetch(`/api/fbb/incidents/outages?${params.toString()}`);
        const result = await response.json();
        
        if (!response.ok) throw new Error(result.error || 'Failed to fetch outages data');
        
        // Populate KPIs
        document.getElementById('outages-stat-energy-cuts').textContent = (result.kpis.total_energy_cuts || 0).toLocaleString();
        document.getElementById('outages-stat-energy-affected').textContent = (result.kpis.total_energy_affected || 0).toLocaleString();
        document.getElementById('outages-stat-odn-cuts').textContent = (result.kpis.total_odn_cuts || 0).toLocaleString();
        document.getElementById('outages-stat-odn-affected').textContent = (result.kpis.total_odn_affected || 0).toLocaleString();
        document.getElementById('outages-stat-wos').textContent = (result.kpis.total_wos || 0).toLocaleString();
        
        // Save to global state
        currentOutagesData = result.outages_ranking;
        
        // Render detailed table
        renderOutagesTable(currentOutagesData);
        
        // Render charts
        renderOutagesCharts(result);
        
    } catch (err) {
        console.error('Error loading outages report:', err);
    }
}

function renderOutagesTable(data) {
    const tbody = document.getElementById('outages-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No hay datos de caídas para el filtro seleccionado.</td></tr>';
        return;
    }
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${row.site}</strong></td>
            <td><span class="badge badge-secondary">${row.branch}</span></td>
            <td>${row.month_year}</td>
            <td>${(row.energy_cuts || 0).toLocaleString()}</td>
            <td>${(row.energy_affected || 0).toLocaleString()}</td>
            <td>${(row.odn_cuts || 0).toLocaleString()}</td>
            <td>${(row.odn_affected || 0).toLocaleString()}</td>
            <td>${(row.total_wos || 0).toLocaleString()}</td>
        `;
        tbody.appendChild(tr);
    });
}

let outagesSortCol = '';
let outagesSortDir = 'desc';

function sortOutagesTable(column) {
    if (outagesSortCol === column) {
        outagesSortDir = outagesSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        outagesSortCol = column;
        outagesSortDir = 'desc';
    }
    
    currentOutagesData.sort((a, b) => {
        let valA = a[column];
        let valB = b[column];
        
        if (typeof valA === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }
        
        if (valA < valB) return outagesSortDir === 'asc' ? -1 : 1;
        if (valA > valB) return outagesSortDir === 'asc' ? 1 : -1;
        return 0;
    });
    
    renderOutagesTable(currentOutagesData);
}

window.sortOutagesTable = sortOutagesTable;

function renderOutagesCharts(result) {
    // Chart 1: Outages vs Calls (Grouped Bar Chart)
    const compCtx = document.getElementById('chart-outages-cancellations-comparison');
    if (compCtx) {
        const compContext = compCtx.getContext('2d');
        if (AppState.charts.outagesComparison) AppState.charts.outagesComparison.destroy();
        
        const topSites = result.outages_ranking.slice(0, 10);
        const labels = topSites.map(s => s.site);
        const energyCuts = topSites.map(s => s.energy_cuts);
        const odnCuts = topSites.map(s => s.odn_cuts);
        const wosData = topSites.map(s => s.total_wos);
        
        AppState.charts.outagesComparison = new Chart(compContext, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Cortes Energía (Cant.)',
                        data: energyCuts,
                        backgroundColor: 'rgba(239, 68, 68, 0.75)',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Cortes ODN/Fibra (Cant.)',
                        data: odnCuts,
                        backgroundColor: 'rgba(245, 158, 11, 0.75)',
                        borderColor: 'rgba(245, 158, 11, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Averías WO',
                        data: wosData,
                        backgroundColor: 'rgba(59, 130, 246, 0.75)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (e, activeElements, chart) => {
                    if (activeElements && activeElements.length > 0) {
                        const firstPoint = activeElements[0];
                        const site = chart.data.labels[firstPoint.index];
                        const datasetIndex = firstPoint.datasetIndex;
                        if (datasetIndex === 2) {
                            showWoDetailsModal(site);
                        } else {
                            showOutageDetailsModal(site);
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#5B6577', font: { family: 'Inter', size: 10 } }
                    }
                }
            }
        });
    }
    
    // Chart 2: Outage Causes breakdown (Horizontal Bar Chart)
    const causesCtx = document.getElementById('chart-outage-causes');
    if (causesCtx) {
        const causesContext = causesCtx.getContext('2d');
        if (AppState.charts.outagesCauses) AppState.charts.outagesCauses.destroy();
        
        const labels = result.causes.map(c => c.causa);
        const affectedData = result.causes.map(c => c.total_affected_onus);
        const cutsData = result.causes.map(c => c.total_cuts);
        
        AppState.charts.outagesCauses = new Chart(causesContext, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Clientes Afectados',
                        data: affectedData,
                        backgroundColor: 'rgba(16, 185, 129, 0.75)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const idx = context.dataIndex;
                                const cuts = cutsData[idx] || 0;
                                const affected = context.raw || 0;
                                return affected.toLocaleString() + ' afectados en ' + cuts.toLocaleString() + ' cortes';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#5B6577', font: { family: 'Inter', size: 11 } }
                    }
                }
            }
        });
    }
}

async function showOutageDetailsModal(site) {
    try {
        const branchVal = document.getElementById('incidents-filter-branch')?.value || '';
        const monthVal = document.getElementById('incidents-filter-month')?.value || '';
        const weekVal = document.getElementById('incidents-filter-week')?.value || '';
        
        const params = new URLSearchParams();
        params.append('site', site);
        if (branchVal) params.append('branch', branchVal);
        if (weekVal) {
            params.append('week', weekVal);
        } else if (monthVal) {
            params.append('month', monthVal);
        }
        
        const response = await fetch(`/api/fbb/incidents/outages/details?${params.toString()}`);
        const details = await response.json();
        
        if (!response.ok) throw new Error(details.error || 'Failed to fetch details');
        
        document.getElementById('outage-modal-title-site').textContent = site;
        const tbody = document.getElementById('outage-details-table-body');
        tbody.innerHTML = '';
        
        if (details.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">No hay registros de cortes para este periodo.</td></tr>';
        } else {
            details.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${item.olt_name || '-'}</td>
                    <td>${item.pon || '-'}</td>
                    <td>
                        <span style="padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: ${item.tipo_corte === 'CORTE-ENERGIA' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)'}; color: ${item.tipo_corte === 'CORTE-ENERGIA' ? '#f87171' : '#fbbf24'};">${item.tipo_corte || '-'}</span>
                    </td>
                    <td>${item.hora_corte || '-'}</td>
                    <td><strong>${(item.onus_afectadas || 0).toLocaleString()}</strong></td>
                    <td><strong>${(item.wos_created || 0).toLocaleString()}</strong></td>
                    <td>${item.causa || '-'}</td>
                    <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.onus_ids || ''}">${item.onus_ids || '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        const modal = document.getElementById('outage-details-modal');
        if (modal) {
            modal.classList.add('active');
        }
    } catch (err) {
        showToast(`Error al obtener detalles del site: ${err.message}`, 'error');
    }
}

async function showWoDetailsModal(site) {
    try {
        const branchVal = document.getElementById('incidents-filter-branch')?.value || '';
        const monthVal = document.getElementById('incidents-filter-month')?.value || '';
        const weekVal = document.getElementById('incidents-filter-week')?.value || '';
        
        const params = new URLSearchParams();
        params.append('site', site);
        if (branchVal) params.append('branch', branchVal);
        if (weekVal) {
            params.append('week', weekVal);
        } else if (monthVal) {
            params.append('month', monthVal);
        }
        
        const response = await fetch(`/api/fbb/incidents/wos/details?${params.toString()}`);
        const details = await response.json();
        
        if (!response.ok) throw new Error(details.error || 'Failed to fetch details');
        
        document.getElementById('wo-modal-title-site').textContent = site;
        const tbody = document.getElementById('wo-details-table-body');
        tbody.innerHTML = '';
        
        if (details.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No hay registros de WOs correlacionadas para este periodo.</td></tr>';
        } else {
            details.forEach(item => {
                const isRec = item.qty_repeat && item.qty_repeat > 1;
                const recBadge = isRec 
                    ? `<span style="padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: rgba(239,68,68,0.2); color: #f87171;">Sí (${item.qty_repeat})</span>`
                    : `<span style="padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: rgba(107,114,128,0.2); color: #5B6577;">No</span>`;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${item.wo_code || '-'}</strong></td>
                    <td>${item.subscriber || '-'}</td>
                    <td>${item.create_time || '-'}</td>
                    <td><span class="badge badge-secondary">${item.partner_close || '-'}</span></td>
                    <td>${recBadge}</td>
                    <td>${item.status_desc || '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        const modal = document.getElementById('wo-details-modal');
        if (modal) {
            modal.classList.add('active');
        }
    } catch (err) {
        showToast(`Error al obtener detalles de WOs: ${err.message}`, 'error');
    }
}

// ==========================================
// DEPLOYMENTS SECTION
// ==========================================
let currentDeploymentsData = [];
let deploymentsSortCol = '';
let deploymentsSortDir = 'desc';

// Dropdown population helpers for Stacked Capacity Cascading Filters
function populateStackedPartners() {
    const branchSel = document.getElementById('stacked-filter-branch');
    const partnerSel = document.getElementById('stacked-filter-partner');
    if (!partnerSel) return;
    
    const branchVal = branchSel ? branchSel.value : '';
    partnerSel.innerHTML = '<option value="">Partner</option>';
    
    let activePartners = new Set();
    if (AppState.filters && AppState.filters.zone_assignments) {
        AppState.filters.zone_assignments.forEach(za => {
            if (!branchVal || za.branch === branchVal) {
                if (za.partner && za.partner !== 'nan') {
                    activePartners.add(za.partner);
                }
            }
        });
    }
    
    Array.from(activePartners).sort().forEach(p => {
        partnerSel.insertAdjacentHTML('beforeend', `<option value="${p}">${p}</option>`);
    });
}

// Bind to window for global access from HTML onclick event
window.populateStackedPartners = populateStackedPartners;

async function loadDeploymentsReport() {
    const branchSel = document.getElementById('deployments-filter-branch');
    const monthSel = document.getElementById('deployments-filter-month');
    
    const branch = branchSel ? branchSel.value : '';
    const month = monthSel ? monthSel.value : '';
    
    try {
        const params = new URLSearchParams();
        if (branch) params.append('branch', branch);
        if (month) params.append('month', month);
        
        const response = await fetch(`/api/fbb/deployments/stats?${params.toString()}`);
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Failed to fetch deployments data');
        
        // Save to state
        currentDeploymentsData = data.detail_table;
        
        // 1. Populate KPIs
        const overall = data.overall;
        document.getElementById('deployments-stat-total').textContent = (overall.total_tasks || 0).toLocaleString();
        document.getElementById('deployments-stat-sla24').textContent = (overall.sla_24h_pct || 0).toFixed(2) + '%';
        document.getElementById('deployments-stat-teams').textContent = (overall.teams_deploy || 0).toLocaleString();
        document.getElementById('deployments-stat-techs').textContent = (overall.ft_total || 0).toLocaleString();
        document.getElementById('deployments-stat-zones').textContent = (overall.assigned_zones || 0).toLocaleString();
        
        // 2. Populate Ratios
        document.getElementById('deployments-ratio-tasks-team').textContent = 
            overall.tasks_per_team ? overall.tasks_per_team.toFixed(1) + ' tar/eq' : '-';
        document.getElementById('deployments-ratio-zones-team').textContent = 
            overall.zones_per_team ? overall.zones_per_team.toFixed(1) + ' zon/eq' : '-';
        document.getElementById('deployments-ratio-techs-zone').textContent = 
            overall.techs_per_zone ? overall.techs_per_zone.toFixed(1) + ' téc/zon' : '-';
        document.getElementById('deployments-ratio-avg-time').textContent = 
            overall.avg_close_time_hrs ? overall.avg_close_time_hrs.toFixed(1) + ' hrs' : '-';
        document.getElementById('deployments-ratio-tasks-day-team').textContent = 
            overall.deployments_per_day_per_team ? overall.deployments_per_day_per_team.toFixed(2) + ' tar/eq/día' : '-';
            
        // 3. Render Table
        renderDeploymentsTable(currentDeploymentsData);
        
        // 4. Render Charts
        renderDeploymentsCharts(data);
        
        // 5. Dynamic Analysis Summary
        generateDeploymentsAnalysis(data);
        
        // Bind Filter Listeners on first run
        initDeploymentsListeners();
        
    } catch (err) {
        console.error('Error loading deployments report:', err);
    }
}

function initDeploymentsListeners() {
    const branchSel = document.getElementById('deployments-filter-branch');
    const monthSel = document.getElementById('deployments-filter-month');
    
    if (branchSel && !branchSel.dataset.listenerBound) {
        branchSel.addEventListener('change', loadDeploymentsReport);
        branchSel.dataset.listenerBound = 'true';
    }
    if (monthSel && !monthSel.dataset.listenerBound) {
        monthSel.addEventListener('change', loadDeploymentsReport);
        monthSel.dataset.listenerBound = 'true';
    }
}

function renderDeploymentsTable(data) {
    const tbody = document.getElementById('deployments-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center">No hay datos de despliegue para el filtro seleccionado.</td></tr>';
        return;
    }
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${row.partner}</strong></td>
            <td><span class="badge badge-secondary">${row.branch}</span></td>
            <td>${(row.total_tasks || 0).toLocaleString()}</td>
            <td>
                <span class="badge ${row.sla_24h_pct >= 80 ? 'badge-success' : row.sla_24h_pct >= 50 ? 'badge-warning' : 'badge-danger'}">
                    ${row.sla_24h_pct.toFixed(2)}%
                </span>
            </td>
            <td>${row.sla_48h_pct.toFixed(2)}%</td>
            <td>${row.teams_deploy || 0}</td>
            <td>${row.ft_total || 0}</td>
            <td>${row.tasks_per_team !== null ? row.tasks_per_team.toFixed(1) : '-'}</td>
            <td>${row.zones_per_team !== null ? row.zones_per_team.toFixed(1) : '-'}</td>
            <td>${row.techs_per_zone !== null ? row.techs_per_zone.toFixed(1) : '-'}</td>
            <td>${row.avg_close_time_hrs !== null && row.avg_close_time_hrs !== undefined ? row.avg_close_time_hrs.toFixed(1) + ' hrs' : '-'}</td>
            <td>${row.deployments_per_day_per_team !== null && row.deployments_per_day_per_team !== undefined ? row.deployments_per_day_per_team.toFixed(2) : '-'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function sortDeploymentsTable(column) {
    if (deploymentsSortCol === column) {
        deploymentsSortDir = deploymentsSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        deploymentsSortCol = column;
        deploymentsSortDir = 'desc';
    }
    
    currentDeploymentsData.sort((a, b) => {
        let valA = a[column];
        let valB = b[column];
        
        if (valA === null || valA === undefined) valA = -1;
        if (valB === null || valB === undefined) valB = -1;
        
        if (typeof valA === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }
        
        if (valA < valB) return deploymentsSortDir === 'asc' ? -1 : 1;
        if (valA > valB) return deploymentsSortDir === 'asc' ? 1 : -1;
        return 0;
    });
    
    renderDeploymentsTable(currentDeploymentsData);
}

window.sortDeploymentsTable = sortDeploymentsTable;

function renderDeploymentsCharts(data) {
    // Chart 1: Partner Efficiency Horizontal Bar Chart
    const effCtx = document.getElementById('chart-deployments-partner-efficiency');
    if (effCtx) {
        const effContext = effCtx.getContext('2d');
        if (AppState.charts.deployPartnerEfficiency) AppState.charts.deployPartnerEfficiency.destroy();
        
        const sortedPartners = data.partner_stats
            .filter(p => p.total_tasks > 0)
            .sort((a, b) => b.sla_24h_pct - a.sla_24h_pct)
            .slice(0, 15);
            
        const labels = sortedPartners.map(p => p.partner);
        const slaData = sortedPartners.map(p => p.sla_24h_pct);
        const tasksData = sortedPartners.map(p => p.total_tasks);
        
        AppState.charts.deployPartnerEfficiency = new Chart(effContext, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Eficiencia SLA <24H (%)',
                    data: slaData,
                    tasksData: tasksData,
                    backgroundColor: 'rgba(16, 185, 129, 0.75)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const idx = context.dataIndex;
                                const val = context.raw || 0;
                                const tasks = context.dataset.tasksData[idx] || 0;
                                return val.toFixed(2) + '% (' + tasks.toLocaleString() + ' tareas)';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577', callback: function(value) { return value + '%'; } },
                        max: 100
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#5B6577', font: { family: 'Inter', size: 9 }, autoSkip: false }
                    }
                }
            }
        });
    }

    // Chart 2: Workload vs Efficiency Dual Axis Chart
    const wlCtx = document.getElementById('chart-deployments-workload-vs-efficiency');
    if (wlCtx) {
        const wlContext = wlCtx.getContext('2d');
        if (AppState.charts.deployWorkloadVsEfficiency) AppState.charts.deployWorkloadVsEfficiency.destroy();
        
        const sortedPartners = data.partner_stats
            .filter(p => p.teams_deploy > 0)
            .sort((a, b) => (b.total_tasks / b.teams_deploy) - (a.total_tasks / a.teams_deploy))
            .slice(0, 12);
            
        const labels = sortedPartners.map(p => p.partner);
        const workloadData = sortedPartners.map(p => p.tasks_per_team);
        const efficiencyData = sortedPartners.map(p => p.sla_24h_pct);
        const totalTasks = sortedPartners.map(p => p.total_tasks);
        const totalTeams = sortedPartners.map(p => p.teams_deploy);
        
        AppState.charts.deployWorkloadVsEfficiency = new Chart(wlContext, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Carga de Trabajo (Tareas/Equipo)',
                        data: workloadData,
                        totalTasks: totalTasks,
                        totalTeams: totalTeams,
                        backgroundColor: 'rgba(245, 158, 11, 0.6)',
                        borderColor: 'rgba(245, 158, 11, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        type: 'line',
                        label: 'Eficiencia SLA <24H (%)',
                        data: efficiencyData,
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Tareas por Equipo',
                            color: '#5B6577'
                        },
                        grid: { color: 'rgba(15, 23, 42, 0.05)' },
                        ticks: { color: '#5B6577' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Eficiencia SLA (%)',
                            color: '#5B6577'
                        },
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#5B6577', callback: function(value) { return value + '%'; } },
                        min: 0,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#5B6577', font: { family: 'Inter', size: 10 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    const idx = context.dataIndex;
                                    if (context.datasetIndex === 0) {
                                        const tasks = context.dataset.totalTasks[idx] || 0;
                                        const teams = context.dataset.totalTeams[idx] || 0;
                                        label += context.parsed.y.toFixed(1) + ' (' + tasks.toLocaleString() + ' tareas / ' + teams + ' eq)';
                                    } else {
                                        label += context.parsed.y.toFixed(2) + '%';
                                    }
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
}

function generateDeploymentsAnalysis(data) {
    const analysisEl = document.getElementById('deployments-analysis-content');
    if (!analysisEl) return;
    
    const overall = data.overall;
    // Filter active partner-branch combinations from detail_table
    const activeRows = data.detail_table.filter(p => p.total_tasks > 10 && p.teams_deploy > 0);
    
    // Sort by workload (tasks per team)
    let highWorkloadRows = [...activeRows]
        .sort((a, b) => b.tasks_per_team - a.tasks_per_team)
        .slice(0, 3);
        
    // Sort by lowest SLA 24H
    let lowSlaRows = [...activeRows]
        .sort((a, b) => a.sla_24h_pct - b.sla_24h_pct)
        .slice(0, 4);

    const getPartnerLabel = (r) => {
        const pName = r.partner.toUpperCase().trim();
        if (pName === 'BITEL') {
            return `BITEL (${r.branch})`;
        }
        return `${r.partner} (${r.branch})`;
    };

    // Calculate count of critical partners
    const overloadedCount = activeRows.filter(r => r.tasks_per_team > 150).length;
    const underStaffedCount = activeRows.filter(r => r.techs_per_zone !== null && r.techs_per_zone < 0.5).length;

    let html = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; line-height: 1.6;">
            <div>
                <h4 style="font-weight: 600; color: var(--color-primary); margin-bottom: 10px; font-size: 15px;">
                    <i class="fa-solid fa-gauge-high"></i> Estado de Eficiencia y Productividad Operativa
                </h4>
                <p style="margin-bottom: 12px; text-align: justify;">
                    El análisis consolidado indica que a nivel general, se completó el <strong>${overall.sla_24h_pct.toFixed(2)}%</strong> de las tareas dentro del SLA de 24 horas, acumulando un promedio de <strong>${overall.avg_close_time_hrs ? overall.avg_close_time_hrs.toFixed(1) : '-'} horas</strong> para el cierre de las órdenes de despliegue. 
                    El volumen total de actividad registrado en el período es de <strong>${(overall.total_tasks || 0).toLocaleString()} tareas</strong> de despliegue, atendidas por un equipo compuesto por <strong>${overall.teams_deploy || 0} cuadrillas</strong> de trabajo. Esto representa una carga nacional promedio de <strong>${overall.tasks_per_team ? overall.tasks_per_team.toFixed(1) : '-'} tareas por equipo</strong> y una tasa de ejecución diaria de <strong>${overall.deployments_per_day_per_team ? overall.deployments_per_day_per_team.toFixed(2) : '-'} tareas/equipo/día</strong>.
                </p>
                
                <h5 style="font-weight: 600; color: var(--color-warning); margin-bottom: 8px; font-size: 13px;">Socios Críticos con Mayor Carga de Trabajo (Tareas/Equipo):</h5>
                <p style="margin-bottom: 8px; color: var(--color-text-muted); font-size: 12px; font-style: italic;">
                    Un volumen elevado de tareas por equipo diluye la capacidad de respuesta inmediata.
                </p>
                <ul style="padding-left: 18px; margin-bottom: 12px;">
    `;
    
    highWorkloadRows.forEach(r => {
        const label = getPartnerLabel(r);
        html += `<li style="margin-bottom: 6px;">
            <strong>${label}</strong>: 
            <span style="color: var(--color-warning); font-weight: bold;">${r.tasks_per_team.toFixed(1)} tar/eq</span> 
            (SLA 24H: ${r.sla_24h_pct.toFixed(1)}%, T. Promedio: ${r.avg_close_time_hrs ? r.avg_close_time_hrs.toFixed(1) : '-'} hrs)
        </li>`;
    });
    
    html += `
                </ul>
            </div>
            
            <div>
                <h4 style="font-weight: 600; color: var(--color-danger); margin-bottom: 10px; font-size: 15px;">
                    <i class="fa-solid fa-triangle-exclamation"></i> Cuellos de Botella y Diagnóstico de Staffing
                </h4>
                <p style="margin-bottom: 12px; text-align: justify;">
                    La densidad nacional de técnicos por zona asignada se ubica en <strong>${overall.techs_per_zone ? overall.techs_per_zone.toFixed(2) : '-'} técnicos por zona</strong> (lo que equivale a un promedio de <strong>${overall.zones_per_team ? overall.zones_per_team.toFixed(1) : '-'} zonas por equipo</strong>).
                    Detectamos <strong>${overloadedCount} contratas</strong> que superan el límite de saturación operativa (>150 tareas/equipo) y <strong>${underStaffedCount} contratas</strong> con un déficit severo de personal de campo (<0.5 técnicos por zona). Estos ratios bajos obligan a las cuadrillas a trasladarse entre múltiples distritos, incrementando los tiempos de traslado y castigando el SLA.
                </p>
                
                <h5 style="font-weight: 600; color: var(--color-danger); margin-bottom: 8px; font-size: 13px;">Contratas con Menor Eficiencia (SLA <24H):</h5>
                <p style="margin-bottom: 8px; color: var(--color-text-muted); font-size: 12px; font-style: italic;">
                    Estas contratas representan los mayores desvíos en el tiempo de entrega del servicio.
                </p>
                <ul style="padding-left: 18px; margin-bottom: 0;">
    `;
    
    lowSlaRows.forEach(r => {
        const label = getPartnerLabel(r);
        const staffingVal = r.techs_per_zone !== null ? `${r.techs_per_zone.toFixed(2)} téc/zona` : 'sin asignación';
        html += `<li style="margin-bottom: 6px;">
            <strong>${label}</strong>: 
            SLA 24H de <span style="color: var(--color-danger); font-weight: bold;">${r.sla_24h_pct.toFixed(1)}%</span> 
            (${r.total_tasks} tareas, staffing de ${staffingVal}, T. Promedio: ${r.avg_close_time_hrs ? r.avg_close_time_hrs.toFixed(1) : '-'} hrs)
        </li>`;
    });
    
    html += `
                </ul>
            </div>
        </div>
        
        <div style="margin-top: 18px; border-top: 1px solid var(--border-color); padding-top: 14px; font-size: 12.5px;">
            <div style="font-weight: bold; color: var(--color-primary); margin-bottom: 6px;">
                <i class="fa-solid fa-lightbulb"></i> Recomendaciones Operativas para la Toma de Decisiones:
            </div>
            <ul style="padding-left: 18px; margin-top: 0; margin-bottom: 0; line-height: 1.5; color: var(--color-text-muted);">
                <li style="margin-bottom: 4px;">
                    <strong>Redistribución de Zonas Geográficas</strong>: Las contratas sobrecargadas deben transferir temporalmente la atención de zonas adyacentes a socios con mayor capacidad o menor densidad de tareas por equipo.
                </li>
                <li style="margin-bottom: 4px;">
                    <strong>Auditoría de Personal Técnico</strong>: En los casos donde el ratio de Técnicos/Zona sea inferior a 0.5 (como ocurre en las contratas críticas listadas), se debe exigir contractualmente un incremento del personal (Full-Time) asignado o la creación de nuevas cuadrillas dedicadas únicamente a despliegues para desfogar a las de incidentes.
                </li>
                <li>
                    <strong>Sanciones de SLA y Compensaciones</strong>: Establecer penalizaciones a contratas que de manera recurrentrente mantengan un SLA inferior al 60% en despliegues, priorizando la reasignación de órdenes hacia contratas más eficientes dentro de la misma sucursal.
                </li>
            </ul>
        </div>
    `;
    
    analysisEl.innerHTML = html;
}

window.loadDeploymentsReport = loadDeploymentsReport;


// ============================================================
// FBB DATA — integracion con la navegacion unificada
// (nav-item / page-section / switchPage) del dashboard principal.
// Los data-target="*-section" originales de este modulo ya no
// existen en el DOM unificado (se uso nav-item/data-page en su lugar),
// asi que initNavigation() de arriba queda inerte; esta seccion
// dispara la carga de datos de cada pestaña FBB cuando se hace click
// en su nav-item, re-creando charts/mapa para que Chart.js y Leaflet
// midan un contenedor ya visible (si se crean con el tab oculto,
// quedan con tamaño 0).
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const fbbNavItems = document.querySelectorAll('.nav-item[data-page^="fbb-"]');
    fbbNavItems.forEach(item => {
        item.addEventListener('click', () => {
            const target = item.dataset.page;

            if (target === 'fbb-dashboard') {
                loadDashboardStats();
                loadStackedCapacityChart();
            } else if (target === 'fbb-zones') {
                loadZones();
            } else if (target === 'fbb-boxes') {
                setTimeout(() => {
                    if (AppState.map) {
                        AppState.map.invalidateSize();
                    } else {
                        initLeafletMap();
                    }
                }, 100);
            } else if (target === 'fbb-staff') {
                loadStaff();
            } else if (target === 'fbb-partner-capacity') {
                loadPartnerCapacityReport();
            } else if (target === 'fbb-incidents') {
                const branchSel = document.getElementById('incidents-filter-branch');
                if (branchSel && branchSel.options.length <= 1) {
                    branchSel.innerHTML = '<option value="">Todas</option>';
                    AppState.filters.branches.forEach(b => {
                        branchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
                    });
                }
                (async () => {
                    await loadIncidentsMonthsOptions();
                    await loadIncidentsWeeksOptions();
                    const bVal = branchSel ? branchSel.value : '';
                    await loadIncidentsSiteOptions(bVal);
                    loadIncidents();
                })();
            } else if (target === 'fbb-deployments') {
                const branchSel = document.getElementById('deployments-filter-branch');
                if (branchSel && branchSel.options.length <= 1) {
                    branchSel.innerHTML = '<option value="">Todas</option>';
                    AppState.filters.branches.forEach(b => {
                        branchSel.insertAdjacentHTML('beforeend', `<option value="${b}">${b}</option>`);
                    });
                }
                const monthSel = document.getElementById('deployments-filter-month');
                if (monthSel && monthSel.options.length <= 1) {
                    monthSel.innerHTML = '<option value="">Todos los meses</option>';
                    const months = ['01/2026', '02/2026', '03/2026', '04/2026', '05/2026', '06/2026'];
                    months.forEach(m => {
                        monthSel.insertAdjacentHTML('beforeend', `<option value="${m}">${m}</option>`);
                    });
                }
                loadDeploymentsReport();
            }
        });
    });
});
