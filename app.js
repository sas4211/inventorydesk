// ==============================================================================
// APPLICATION STATE
// ==============================================================================

const state = {
    user: {
        username: null,
        role: null
    },
    inventory: [],
    suppliers: [],
    parties: [],
    cart: [] // Invoicing cashier cart items: { sku, product_name, qty, price, warranty }
};

const API_BASE = '/api';

// ==============================================================================
// APP INITIALIZATION & ROUTING
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkSession();
});

function setupEventListeners() {
    // Login form submit
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    
    // Tab switching
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const tabId = e.currentTarget.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Sub-tab switching in Reports
    document.querySelectorAll('.sub-tab').forEach(subTab => {
        subTab.addEventListener('click', (e) => {
            const subtabId = e.currentTarget.getAttribute('data-subtab');
            switchSubTab(subtabId);
        });
    });
    
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    
    // Sign out
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    // Stock Modal actions
    document.getElementById('add-stock-btn').addEventListener('click', () => openStockModal());
    document.getElementById('stock-form').addEventListener('submit', saveStockItem);
    
    // Supplier Modal actions
    document.getElementById('add-supplier-btn').addEventListener('click', () => openSupplierModal());
    document.getElementById('supplier-form').addEventListener('submit', saveSupplier);
    
    // Modals close button
    document.querySelectorAll('.close-modal-btn, .close-modal-action').forEach(btn => {
        btn.addEventListener('click', closeAllModals);
    });

    // Stock Catalog Search
    document.getElementById('catalog-search').addEventListener('input', filterStockCatalog);

    // Cashier Invoicing: Cart additions
    document.getElementById('checkout-add-form').addEventListener('submit', addToCart);
    document.getElementById('clear-cart-btn').addEventListener('click', clearCart);
    document.getElementById('commit-checkout-btn').addEventListener('click', commitCheckout);

    // Cashier Invoicing: Barcode scanned (key enter) or product select synced
    document.getElementById('checkout-barcode').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleBarcodeScan();
        }
    });
    document.getElementById('checkout-item').addEventListener('change', (e) => {
        const sku = e.target.value;
        if (sku) {
            document.getElementById('checkout-barcode').value = sku;
        }
    });

    // Payments Collections: select party sync
    document.getElementById('collection-party').addEventListener('change', (e) => {
        const party = e.target.value;
        if (party) {
            updateCollectionSummary(party);
        }
    });

    // Party Ledgers: select party sync
    document.getElementById('ledger-party-select').addEventListener('change', (e) => {
        const party = e.target.value;
        if (party) {
            loadPartyLedger(party);
        }
    });

    // Invoice registry printing
    document.getElementById('print-selected-invoice-btn').addEventListener('click', printSelectedDashboardInvoice);
    document.getElementById('invoice-print-action-btn').addEventListener('click', printInvoiceFromModal);
}

// Check local storage session
function checkSession() {
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
        const parsed = JSON.parse(savedUser);
        state.user = parsed;
        setupUIForRole();
    }
}

// Show/Hide fields and tabs based on user role
function setupUIForRole() {
    document.getElementById('login-gateway').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
    
    const userBadge = document.getElementById('user-badge');
    userBadge.innerText = `Role: ${state.user.role} (${state.user.username})`;
    
    if (state.user.role === 'Admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
        document.getElementById('ledger-tab-btn').innerText = '📖 Party Ledgers';
        document.getElementById('ledger-party-selector-row').classList.remove('hidden');
        switchTab('dashboard-panel');
    } else {
        document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
        document.getElementById('ledger-tab-btn').innerText = '📖 Personal Ledger';
        document.getElementById('ledger-party-selector-row').classList.add('hidden');
        switchTab('dashboard-panel');
    }
}

// ==============================================================================
// NAVIGATION
// ==============================================================================

function switchTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        if (tab.getAttribute('data-tab') === tabId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    document.querySelectorAll('.tab-panel').forEach(panel => {
        if (panel.id === tabId) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });
    
    // Dispatch data loading based on active tab
    if (tabId === 'dashboard-panel') {
        loadDashboard();
    } else if (tabId === 'catalog-panel') {
        loadStockCatalog();
    } else if (tabId === 'invoicing-panel') {
        loadCashierCheckout();
    } else if (tabId === 'invoices-panel') {
        loadInvoiceRegistry();
    } else if (tabId === 'suppliers-panel') {
        loadSuppliers();
    } else if (tabId === 'ledger-panel') {
        if (state.user.role === 'Admin') {
            loadPartiesDropdown('ledger-party-select');
        } else {
            loadPartyLedger(state.user.username);
        }
    } else if (tabId === 'collections-panel') {
        loadCollections();
    } else if (tabId === 'reports-panel') {
        loadReports();
    }
}

function switchSubTab(subtabId) {
    document.querySelectorAll('.sub-tab').forEach(tab => {
        if (tab.getAttribute('data-subtab') === subtabId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    document.querySelectorAll('.sub-tab-content').forEach(content => {
        if (content.id === subtabId) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });
}

function showStatus(msg, isError = false) {
    const indicator = document.querySelector('.status-indicator');
    const msgLabel = document.getElementById('status-message');
    
    msgLabel.innerText = msg;
    if (isError) {
        indicator.style.backgroundColor = 'var(--color-danger)';
        indicator.style.boxShadow = '0 0 8px var(--color-danger)';
    } else {
        indicator.style.backgroundColor = 'var(--color-success)';
        indicator.style.boxShadow = '0 0 8px var(--color-success)';
    }
}

// ==============================================================================
// THEME MANAGEMENT
// ==============================================================================

function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('theme-toggle');
    if (body.classList.contains('dark-theme')) {
        body.classList.remove('dark-theme');
        body.classList.add('light-theme');
        btn.innerText = '🌙 Dark Mode';
    } else {
        body.classList.remove('light-theme');
        body.classList.add('dark-theme');
        btn.innerText = '☀️ Light Mode';
    }
}

// ==============================================================================
// AUTHENTICATION
// ==============================================================================

async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('login-username').value;
    const passwordInput = document.getElementById('login-password').value;
    const errBanner = document.getElementById('login-error');
    
    errBanner.classList.add('hidden');
    
    try {
        const res = await fetch(`${API_BASE}/auth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: usernameInput, password: passwordInput })
        });
        
        const data = await res.json();
        if (data.success) {
            state.user = { username: data.username, role: data.role };
            localStorage.setItem('user', JSON.stringify(state.user));
            setupUIForRole();
            showStatus("Login successful.");
        } else {
            errBanner.innerText = data.error || "Login failed.";
            errBanner.classList.remove('hidden');
        }
    } catch (err) {
        errBanner.innerText = "Connection error to the backend server API.";
        errBanner.classList.remove('hidden');
    }
}

function handleLogout() {
    localStorage.removeItem('user');
    state.user = { username: null, role: null };
    document.getElementById('app-container').classList.add('hidden');
    document.getElementById('login-gateway').classList.remove('hidden');
    document.getElementById('login-username').value = '';
    document.getElementById('login-password').value = '';
    showStatus("Logged out safely.");
}

// ==============================================================================
// DASHBOARD
// ==============================================================================

async function loadDashboard() {
    showStatus("Syncing dashboard statistics...");
    try {
        const res = await fetch(`${API_BASE}/dashboard/stats?role=${state.user.role}&username=${state.user.username}`);
        const data = await res.json();
        
        if (!data.success) {
            showStatus("Error: " + data.error, true);
            return;
        }

        const grid = document.getElementById('dashboard-stats-grid');
        const alertBanner = document.getElementById('dashboard-deficit-alert');
        const dataTable = document.getElementById('dashboard-data-table');
        const printContainer = document.getElementById('dashboard-print-container');
        
        grid.innerHTML = '';
        alertBanner.classList.add('hidden');
        dataTable.innerHTML = '';
        printContainer.classList.add('hidden');

        if (state.user.role === 'Admin') {
            // Stats cards
            grid.innerHTML = `
                <div class="stat-card glass-panel">
                    <span class="stat-title">Total Sales Revenue</span>
                    <span class="stat-value text-indigo">$${data.stats.sales.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                </div>
                <div class="stat-card glass-panel">
                    <span class="stat-title">Total Receivables Balance</span>
                    <span class="stat-value text-indigo">$${data.stats.outstanding.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                </div>
                <div class="stat-card glass-panel">
                    <span class="stat-title">Deficit Stock Lines</span>
                    <span class="stat-value text-emerald">${data.stats.lowStockCount}</span>
                </div>
            `;

            // Deficit Alert Banner
            if (data.stats.lowStockCount > 0) {
                document.getElementById('deficit-alert-text').innerText = `⚠️ CRITICAL DEFICIT: ${data.stats.lowStockCount} item(s) are below the low stock threshold (5 units)!`;
                alertBanner.classList.remove('hidden');
            }

            // Table headers
            document.getElementById('dashboard-table-title').innerText = 'Critical Low-Stock Inventory Alerts';
            document.getElementById('dashboard-table-subtitle').innerText = 'Stock quantities requiring immediate replenishment:';
            
            dataTable.innerHTML = `
                <thead>
                    <tr>
                        <th>SKU</th>
                        <th>Product Name</th>
                        <th>Units Left</th>
                        <th>Unit Price</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;

            const tbody = dataTable.querySelector('tbody');
            if (data.lowStockItems.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No stock deficits detected. All items healthy.</td></tr>`;
            } else {
                data.lowStockItems.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.classList.add('low-stock-row');
                    tr.innerHTML = `
                        <td>${item.sku}</td>
                        <td>${item.product_name}</td>
                        <td class="low-stock-cell">${item.quantity}</td>
                        <td>$${item.selling_price.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } else {
            // Client view
            grid.innerHTML = `
                <div class="stat-card glass-panel">
                    <span class="stat-title">Total Outbound Orders</span>
                    <span class="stat-value text-indigo">${data.stats.orderCount}</span>
                </div>
                <div class="stat-card glass-panel">
                    <span class="stat-title">Total Invoice Volume</span>
                    <span class="stat-value text-indigo">$${data.stats.totalSpent.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                </div>
                <div class="stat-card glass-panel">
                    <span class="stat-title">My Outstanding Balance</span>
                    <span class="stat-value text-emerald">$${data.stats.balance.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                </div>
            `;

            document.getElementById('dashboard-table-title').innerText = 'Order Dispatch History';
            document.getElementById('dashboard-table-subtitle').innerText = 'Your transaction records and invoice orders:';
            printContainer.classList.remove('hidden');

            dataTable.innerHTML = `
                <thead>
                    <tr>
                        <th>Invoice ID</th>
                        <th>Date</th>
                        <th>Product SKU / Description</th>
                        <th>Qty Ordered</th>
                        <th>Total Price</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;

            const tbody = dataTable.querySelector('tbody');
            if (data.invoices.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No order history found for your account.</td></tr>`;
            } else {
                data.invoices.forEach(inv => {
                    const tr = document.createElement('tr');
                    tr.style.cursor = 'pointer';
                    tr.setAttribute('data-id', inv.id);
                    tr.addEventListener('click', () => selectDashboardRow(tr));
                    tr.innerHTML = `
                        <td>INV#${inv.id}</td>
                        <td>${inv.date}</td>
                        <td>[${inv.product_sku}] ${inv.product_name}</td>
                        <td>${inv.quantity}</td>
                        <td>$${inv.total_amount.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }
        showStatus("Dashboard sync complete.");
    } catch (err) {
        showStatus("Error fetching dashboard statistics.", true);
    }
}

function selectDashboardRow(selectedTr) {
    selectedTr.parentNode.querySelectorAll('tr').forEach(tr => {
        tr.style.backgroundColor = 'transparent';
    });
    selectedTr.style.backgroundColor = 'var(--bg-surface-hover)';
    selectedTr.classList.add('selected-dashboard-row');
}

// ==============================================================================
// STOCK CATALOG
// ==============================================================================

async function loadStockCatalog() {
    showStatus("Syncing catalog inventory database...");
    try {
        const res = await fetch(`${API_BASE}/inventory`);
        const data = await res.json();
        
        if (data.success) {
            state.inventory = data.inventory;
            renderStockCatalogTable(state.inventory);
            showStatus("Catalog database synchronized.");
        }
    } catch (err) {
        showStatus("Error syncing inventory catalog.", true);
    }
}

function renderStockCatalogTable(items) {
    const tbody = document.querySelector('#catalog-table tbody');
    tbody.innerHTML = '';
    
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">No inventory catalog entries found.</td></tr>`;
        return;
    }
    
    items.forEach(item => {
        const tr = document.createElement('tr');
        if (item.quantity < 5) {
            tr.classList.add('low-stock-row');
        }
        
        tr.innerHTML = `
            <td><strong>${item.sku}</strong></td>
            <td>${item.product_name}</td>
            <td class="${item.quantity < 5 ? 'low-stock-cell' : ''}">${item.quantity}</td>
            <td>$${item.purchase_price.toFixed(2)}</td>
            <td>$${item.selling_price.toFixed(2)}</td>
            <td>${item.category}</td>
            <td>${item.subcategory || 'None'}</td>
            <td>${item.supplier_name || 'N/A'}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editStockItem(${item.id})">✏️ Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteStockItem(${item.id})">🗑️ Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterStockCatalog() {
    const query = document.getElementById('catalog-search').value.toLowerCase();
    const filtered = state.inventory.filter(item => 
        item.product_name.toLowerCase().includes(query) ||
        item.sku.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query)
    );
    renderStockCatalogTable(filtered);
}

function openStockModal(item = null) {
    const modal = document.getElementById('stock-modal');
    const title = document.getElementById('stock-modal-title');
    
    document.getElementById('stock-form').reset();
    document.getElementById('stock-id').value = '';
    
    if (item) {
        title.innerText = "Edit Catalog Item";
        document.getElementById('stock-id').value = item.id;
        document.getElementById('stock-name').value = item.product_name;
        document.getElementById('stock-sku').value = item.sku;
        document.getElementById('stock-qty').value = item.quantity;
        document.getElementById('stock-purchase').value = item.purchase_price;
        document.getElementById('stock-selling').value = item.selling_price;
        document.getElementById('stock-category').value = item.category;
        document.getElementById('stock-subcategory').value = item.subcategory || '';
        document.getElementById('stock-supplier').value = item.supplier_name || '';
    } else {
        title.innerText = "Add Stock Catalog Item";
    }
    
    modal.classList.remove('hidden');
}

function editStockItem(id) {
    const item = state.inventory.find(i => i.id === id);
    if (item) {
        openStockModal(item);
    }
}

async function saveStockItem(e) {
    e.preventDefault();
    const id = document.getElementById('stock-id').value;
    const itemData = {
        product_name: document.getElementById('stock-name').value,
        sku: document.getElementById('stock-sku').value,
        quantity: document.getElementById('stock-qty').value,
        purchase_price: document.getElementById('stock-purchase').value,
        selling_price: document.getElementById('stock-selling').value,
        category: document.getElementById('stock-category').value,
        subcategory: document.getElementById('stock-subcategory').value,
        supplier_name: document.getElementById('stock-supplier').value
    };
    
    const method = id ? 'PUT' : 'POST';
    if (id) {
        itemData.id = parseInt(id);
    }
    
    try {
        const res = await fetch(`${API_BASE}/inventory`, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(itemData)
        });
        const data = await res.json();
        if (data.success) {
            closeAllModals();
            loadStockCatalog();
            showStatus("Catalog item saved successfully.");
        } else {
            alert("Error: " + data.error);
        }
    } catch (err) {
        showStatus("Connection error saving stock item.", true);
    }
}

async function deleteStockItem(id) {
    if (!confirm("Are you sure you want to delete this inventory catalog item?")) return;
    try {
        const res = await fetch(`${API_BASE}/inventory/delete/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            loadStockCatalog();
            showStatus("Item deleted successfully.");
        } else {
            alert("Error deleting item: " + data.error);
        }
    } catch (err) {
        showStatus("Connection error deleting item.", true);
    }
}

// ==============================================================================
// CASHIER CHECKOUT TERMINAL
// ==============================================================================

async function loadCashierCheckout() {
    showStatus("Preparing Cashier Checkout Terminal...");
    await loadPartiesDropdown('checkout-party');
    
    // Populate products list
    try {
        const res = await fetch(`${API_BASE}/inventory`);
        const data = await res.json();
        if (data.success) {
            state.inventory = data.inventory;
            
            const prodSelect = document.getElementById('checkout-item');
            prodSelect.innerHTML = `<option value="" disabled selected>Select Product Catalog</option>`;
            data.inventory.forEach(item => {
                prodSelect.innerHTML += `<option value="${item.sku}">${item.product_name} (${item.sku}) - Price: $${item.selling_price.toFixed(2)} - Qty Left: ${item.quantity}</option>`;
            });
            
            // Clear checkout scanner focus timer equivalents
            document.getElementById('checkout-barcode').value = '';
            document.getElementById('checkout-barcode').focus();
            renderCart();
            showStatus("Checkout ready. Scanning focus established.");
        }
    } catch (err) {
        showStatus("Error loading cashier products dropdown.", true);
    }
}

async function loadPartiesDropdown(selectId) {
    try {
        const res = await fetch(`${API_BASE}/parties`);
        const data = await res.json();
        if (data.success) {
            state.parties = data.parties;
            const select = document.getElementById(selectId);
            const selectedVal = select.value;
            
            select.innerHTML = selectId === 'checkout-party' || selectId === 'collection-party'
                ? `<option value="" disabled selected>Select Customer Account</option>`
                : `<option value="" disabled selected>Select Account</option>`;
                
            data.parties.forEach(p => {
                select.innerHTML += `<option value="${p}">${p}</option>`;
            });
            if (selectedVal) {
                select.value = selectedVal;
            }
        }
    } catch (err) {
        showStatus("Error loading customer party profiles.", true);
    }
}

function handleBarcodeScan() {
    const sku = document.getElementById('checkout-barcode').value.trim();
    if (!sku) return;
    
    const item = state.inventory.find(i => i.sku === sku);
    if (item) {
        document.getElementById('checkout-item').value = sku;
        showStatus(`Barcode read success: ${item.product_name}`);
    } else {
        showStatus(`Unknown Barcode SKU scanned: ${sku}`, true);
    }
}

function addToCart(e) {
    e.preventDefault();
    const sku = document.getElementById('checkout-barcode').value.trim();
    const qty = parseInt(document.getElementById('checkout-qty').value);
    const warranty = document.getElementById('checkout-warranty').value;
    
    if (!sku) {
        alert("Please scan a barcode SKU or select a product first.");
        return;
    }
    
    const item = state.inventory.find(i => i.sku === sku);
    if (!item) {
        alert("Product with scanned SKU not found in catalog database.");
        return;
    }
    
    if (item.quantity < qty) {
        alert(`Insufficient stock. Requested: ${qty}, Available: ${item.quantity}`);
        return;
    }
    
    // Check if item already exists in cart
    const existing = state.cart.find(c => c.sku === sku);
    if (existing) {
        if (item.quantity < (existing.qty + qty)) {
            alert(`Insufficient stock to add more. Cart holds: ${existing.qty}, Catalog: ${item.quantity}`);
            return;
        }
        existing.qty += qty;
        existing.total = existing.qty * existing.price;
    } else {
        state.cart.push({
            sku: item.sku,
            product_name: item.product_name,
            qty: qty,
            price: item.selling_price,
            total: qty * item.selling_price,
            warranty: warranty
        });
    }
    
    renderCart();
    document.getElementById('checkout-barcode').value = '';
    document.getElementById('checkout-item').value = '';
    document.getElementById('checkout-qty').value = 1;
    document.getElementById('checkout-barcode').focus();
    showStatus("Product added to cashier sales cart.");
}

function renderCart() {
    const tbody = document.querySelector('#cart-table tbody');
    tbody.innerHTML = '';
    let total = 0;
    
    state.cart.forEach((item, index) => {
        total += item.total;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.sku}</td>
            <td>${item.product_name}</td>
            <td>${item.qty}</td>
            <td>$${item.price.toFixed(2)}</td>
            <td>$${item.total.toFixed(2)}</td>
            <td>${item.warranty}</td>
            <td><button class="btn btn-danger btn-sm" onclick="removeCartItem(${index})">×</button></td>
        `;
        tbody.appendChild(tr);
    });
    
    document.getElementById('cart-subtotal').innerText = `$${total.toFixed(2)}`;
    document.getElementById('cart-total').innerText = `$${total.toFixed(2)}`;
    document.getElementById('commit-checkout-btn').disabled = state.cart.length === 0;
}

function removeCartItem(index) {
    state.cart.splice(index, 1);
    renderCart();
    showStatus("Cart item removed.");
}

function clearCart() {
    state.cart = [];
    renderCart();
    showStatus("Sales cart cleared.");
}

async function commitCheckout() {
    const partySelect = document.getElementById('checkout-party');
    const partyName = partySelect.value;
    
    if (!partyName) {
        alert("Please select a customer profile to bill the invoice to.");
        return;
    }
    
    if (state.cart.length === 0) return;
    
    showStatus("Writing atomic checkout invoice ledger entries...");
    
    try {
        const res = await fetch(`${API_BASE}/invoices`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                party_name: partyName,
                cart: state.cart
            })
        });
        
        const data = await res.json();
        if (data.success) {
            clearCart();
            // Refresh catalog quantities
            loadCashierCheckout();
            showStatus("Invoice billing finalized. Stock & ledger synced.");
            alert("Invoice checkout committed successfully!");
        } else {
            showStatus("Checkout failed: " + data.error, true);
            alert("Error committing checkout: " + data.error);
        }
    } catch (err) {
        showStatus("Connection error during invoice checkout.", true);
    }
}

// ==============================================================================
// INVOICE REGISTRY
// ==============================================================================

async function loadInvoiceRegistry() {
    showStatus("Syncing invoices archive...");
    try {
        const res = await fetch(`${API_BASE}/invoices`);
        const data = await res.json();
        if (data.success) {
            renderInvoicesTable(data.invoices);
            showStatus("Invoice registry synchronized.");
        }
    } catch (err) {
        showStatus("Error fetching invoices registry.", true);
    }
}

function renderInvoicesTable(invoices) {
    const tbody = document.querySelector('#invoices-table tbody');
    tbody.innerHTML = '';
    
    if (invoices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No invoices recorded in ledger.</td></tr>`;
        return;
    }
    
    invoices.forEach(inv => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>INV#${inv.invoice_id}</strong></td>
            <td>${inv.date}</td>
            <td>${inv.party_name}</td>
            <td>${inv.total_items} items</td>
            <td>$${inv.grand_total.toFixed(2)}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="viewInvoiceDetails('${inv.party_name}', '${inv.date}')">👁️ View & Print</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function viewInvoiceDetails(partyName, date) {
    showStatus("Loading invoice details...");
    try {
        const res = await fetch(`${API_BASE}/invoices/items?party_name=${encodeURIComponent(partyName)}&date=${encodeURIComponent(date)}`);
        const data = await res.json();
        if (data.success && data.items.length > 0) {
            const html = generateInvoiceHtml(partyName, date, data.items);
            const canvas = document.getElementById('invoice-print-canvas');
            canvas.innerHTML = html;
            
            document.getElementById('invoice-detail-modal').classList.remove('hidden');
            showStatus("Invoice bill loaded.");
        } else {
            alert("Invoice items not found.");
        }
    } catch (err) {
        showStatus("Error loading invoice line items.", true);
    }
}

function generateInvoiceHtml(partyName, date, items) {
    const grandTotal = items.reduce((sum, item) => sum + item.total_amount, 0);
    const invoiceNum = items[0].id || 0;
    
    let rowsHtml = "";
    items.forEach(item => {
        const price = item.quantity > 0 ? (item.total_amount / item.quantity) : 0;
        rowsHtml += `
        <tr>
            <td>${item.product_sku}</td>
            <td>${item.product_name || 'Unknown Item'}</td>
            <td style="text-align: center;">${item.quantity}</td>
            <td>${item.warranty || 'None'}</td>
            <td style="text-align: right;">$${price.toFixed(2)}</td>
            <td style="text-align: right;">$${item.total_amount.toFixed(2)}</td>
        </tr>
        `;
    });
    
    return `
        <div class="header">
            <span class="brand">👔 Enterprise Operations Ledger</span>
            <span class="invoice-title">INVOICE</span>
            <div class="clear"></div>
        </div>
        
        <div class="details">
            <div class="details-col">
                <strong>Billed To:</strong><br>
                Customer Name: ${partyName}<br>
            </div>
            <div class="details-col-right">
                <strong>Invoice Details:</strong><br>
                Invoice #: INV-${String(invoiceNum).padStart(5, '0')}<br>
                Date: ${date}<br>
            </div>
            <div class="clear"></div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>SKU</th>
                    <th>Product Description</th>
                    <th style="text-align: center;">Qty</th>
                    <th>Warranty</th>
                    <th style="text-align: right;">Unit Price</th>
                    <th style="text-align: right;">Total Price</th>
                </tr>
            </thead>
            <tbody>
                ${rowsHtml}
                <tr class="total-row">
                    <td colspan="4"></td>
                    <td style="text-align: right;">Grand Total:</td>
                    <td style="text-align: right;">$${grandTotal.toFixed(2)}</td>
                </tr>
            </tbody>
        </table>
        
        <div class="footer">
            Thank you for your business! If you have any questions, please contact support.
        </div>
    `;
}

function printInvoiceFromModal() {
    const printContent = document.getElementById('invoice-print-canvas').innerHTML;
    const originalContent = document.body.innerHTML;
    
    // Simple window printing hack
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
        <head>
            <title>Print Invoice</title>
            <style>
                body { font-family: sans-serif; padding: 20px; color: #333; }
                .header { border-bottom: 2px solid #4f46e5; padding-bottom: 15px; margin-bottom: 25px; }
                .brand { font-size: 24px; font-weight: bold; color: #4f46e5; }
                .invoice-title { font-size: 20px; font-weight: bold; float: right; }
                .clear { clear: both; }
                .details { margin-bottom: 30px; }
                .details-col { width: 48%; float: left; }
                .details-col-right { width: 48%; float: right; text-align: right; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
                th { background-color: #f8fafc; text-align: left; padding: 12px; border-bottom: 2px solid #cbd5e1; }
                td { padding: 12px; border-bottom: 1px solid #e2e8f0; }
                .total-row { font-weight: bold; border-top: 2px solid #cbd5e1; }
                .footer { margin-top: 50px; text-align: center; color: #64748b; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
            </style>
        </head>
        <body onload="window.print();window.close();">
            ${printContent}
        </body>
        </html>
    `);
    printWindow.document.close();
}

async function printSelectedDashboardInvoice() {
    const selected = document.querySelector('.selected-dashboard-row');
    if (!selected) {
        alert("Please select an invoice from the history table first.");
        return;
    }
    const invId = selected.getAttribute('data-id');
    // Fetch detailed row items based on ID
    try {
        const res = await fetch(`${API_BASE}/invoices`);
        const data = await res.json();
        if (data.success) {
            const inv = data.invoices.find(i => i.invoice_id == invId);
            if (inv) {
                viewInvoiceDetails(inv.party_name, inv.date);
            }
        }
    } catch(err) {
        showStatus("Error looking up invoice references.", true);
    }
}

// ==============================================================================
// SUPPLIERS
// ==============================================================================

async function loadSuppliers() {
    showStatus("Syncing suppliers directory...");
    try {
        const res = await fetch(`${API_BASE}/suppliers`);
        const data = await res.json();
        if (data.success) {
            state.suppliers = data.suppliers;
            renderSuppliersTable(data.suppliers);
            showStatus("Suppliers directory synchronized.");
        }
    } catch (err) {
        showStatus("Error syncing suppliers.", true);
    }
}

function renderSuppliersTable(suppliers) {
    const tbody = document.querySelector('#suppliers-table tbody');
    tbody.innerHTML = '';
    
    if (suppliers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No suppliers recorded.</td></tr>`;
        return;
    }
    
    suppliers.forEach(sup => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${sup.id}</td>
            <td><strong>${sup.company_name}</strong></td>
            <td>${sup.contact_name || 'N/A'}</td>
            <td>${sup.phone || 'N/A'}</td>
            <td>${sup.email || 'N/A'}</td>
            <td>${sup.address || 'N/A'}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editSupplier(${sup.id})">✏️ Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteSupplier(${sup.id})">🗑️ Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function openSupplierModal(sup = null) {
    const modal = document.getElementById('supplier-modal');
    const title = document.getElementById('supplier-modal-title');
    
    document.getElementById('supplier-form').reset();
    document.getElementById('supplier-id').value = '';
    
    if (sup) {
        title.innerText = "Edit Supplier Vendor";
        document.getElementById('supplier-id').value = sup.id;
        document.getElementById('supplier-company').value = sup.company_name;
        document.getElementById('supplier-contact').value = sup.contact_name || '';
        document.getElementById('supplier-phone').value = sup.phone || '';
        document.getElementById('supplier-email').value = sup.email || '';
        document.getElementById('supplier-address').value = sup.address || '';
    } else {
        title.innerText = "Add Supplier Vendor";
    }
    
    modal.classList.remove('hidden');
}

function editSupplier(id) {
    const sup = state.suppliers.find(s => s.id === id);
    if (sup) {
        openSupplierModal(sup);
    }
}

async function saveSupplier(e) {
    e.preventDefault();
    const id = document.getElementById('supplier-id').value;
    const supData = {
        company_name: document.getElementById('supplier-company').value,
        contact_name: document.getElementById('supplier-contact').value,
        phone: document.getElementById('supplier-phone').value,
        email: document.getElementById('supplier-email').value,
        address: document.getElementById('supplier-address').value
    };
    
    const method = id ? 'PUT' : 'POST';
    if (id) {
        supData.id = parseInt(id);
    }
    
    try {
        const res = await fetch(`${API_BASE}/suppliers`, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(supData)
        });
        const data = await res.json();
        if (data.success) {
            closeAllModals();
            loadSuppliers();
            showStatus("Supplier database updated.");
        } else {
            alert("Error: " + data.error);
        }
    } catch (err) {
        showStatus("Connection error saving supplier details.", true);
    }
}

async function deleteSupplier(id) {
    if (!confirm("Are you sure you want to remove this supplier vendor from records?")) return;
    try {
        const res = await fetch(`${API_BASE}/suppliers/delete/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            loadSuppliers();
            showStatus("Supplier deleted.");
        } else {
            alert("Error deleting supplier: " + data.error);
        }
    } catch (err) {
        showStatus("Connection error removing supplier.", true);
    }
}

// ==============================================================================
// PARTY LEDGERS
// ==============================================================================

async function loadPartyLedger(partyName) {
    showStatus(`Syncing ledger journal for ${partyName}...`);
    try {
        const resLedger = await fetch(`${API_BASE}/ledgers?party_name=${encodeURIComponent(partyName)}`);
        const dataLedger = await resLedger.json();
        
        const resSummary = await fetch(`${API_BASE}/ledgers/summary/${encodeURIComponent(partyName)}`);
        const dataSummary = await resSummary.json();
        
        if (dataLedger.success && dataSummary.success) {
            // Update Stats cards
            const deb = dataSummary.summary.total_debit;
            const cred = dataSummary.summary.total_credit;
            const bal = dataSummary.summary.balance;
            
            document.getElementById('ledger-total-debit').innerText = `$${deb.toFixed(2)}`;
            document.getElementById('ledger-total-credit').innerText = `$${cred.toFixed(2)}`;
            
            const balVal = document.getElementById('ledger-net-balance');
            balVal.innerText = `$${bal.toFixed(2)}`;
            if (bal > 0) {
                balVal.className = 'stat-value text-indigo heavy-font';
            } else if (bal < 0) {
                balVal.className = 'stat-value text-emerald heavy-font';
            } else {
                balVal.className = 'stat-value heavy-font';
            }

            // Render table
            const tbody = document.querySelector('#ledger-table tbody');
            tbody.innerHTML = '';
            
            if (dataLedger.ledgers.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No ledger operations posted for this party.</td></tr>`;
            } else {
                dataLedger.ledgers.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.id}</td>
                        <td>${row.date}</td>
                        <td>${row.description}</td>
                        <td class="text-indigo">+ $${row.debit.toFixed(2)}</td>
                        <td class="text-emerald">- $${row.credit.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            showStatus(`Ledger for ${partyName} ready.`);
        }
    } catch (err) {
        showStatus("Error fetching party ledger summaries.", true);
    }
}

// ==============================================================================
// PAYMENTS & RECEIPTS (COLLECTIONS)
// ==============================================================================

async function loadCollections() {
    showStatus("Preparing Collections Gateway...");
    await loadPartiesDropdown('collection-party');
    
    // Reset collection fields
    document.getElementById('collection-form').reset();
    document.getElementById('collection-party-details').classList.add('hidden');
    document.querySelector('.select-party-prompt').classList.remove('hidden');
    
    showStatus("Collections ready.");
}

async function updateCollectionSummary(party) {
    try {
        const res = await fetch(`${API_BASE}/ledgers/summary/${encodeURIComponent(party)}`);
        const data = await res.json();
        
        if (data.success) {
            document.querySelector('.select-party-prompt').classList.add('hidden');
            document.getElementById('collection-party-details').classList.remove('hidden');
            
            document.getElementById('collection-party-name').innerText = `Customer Account: ${party}`;
            const bal = data.summary.balance;
            
            const balEl = document.getElementById('collection-outstanding');
            balEl.innerText = `$${bal.toFixed(2)}`;
            
            const alertOutstanding = document.getElementById('collection-alert-outstanding');
            const alertSettled = document.getElementById('collection-alert-settled');
            
            if (bal > 0) {
                balEl.className = 'heavy-font text-indigo';
                alertOutstanding.classList.remove('hidden');
                alertSettled.classList.add('hidden');
            } else {
                balEl.className = 'heavy-font text-emerald';
                alertOutstanding.classList.add('hidden');
                alertSettled.classList.remove('hidden');
            }
        }
    } catch (err) {
        showStatus("Error fetching outstanding balances.", true);
    }
}

document.getElementById('collection-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const party = document.getElementById('collection-party').value;
    const amount = document.getElementById('collection-amount').value;
    const description = document.getElementById('collection-desc').value;
    
    if (!party) {
        alert("Please select a customer party account.");
        return;
    }
    
    showStatus("Posting payment collection receipt...");
    try {
        const res = await fetch(`${API_BASE}/collections`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                party_name: party,
                amount: parseFloat(amount),
                description: description
            })
        });
        const data = await res.json();
        if (data.success) {
            updateCollectionSummary(party);
            document.getElementById('collection-amount').value = '';
            document.getElementById('collection-desc').value = '';
            showStatus("Collection credited atomically.");
            alert("Payment credited successfully!");
        } else {
            alert("Error posting collection: " + data.error);
        }
    } catch(err) {
        showStatus("Connection error posting payment.", true);
    }
});

// ==============================================================================
// REPORTS & ANALYTICS
// ==============================================================================

async function loadReports() {
    showStatus("Compiling business analytics and reports...");
    try {
        // 1. General stats cards
        const resStats = await fetch(`${API_BASE}/reports/stats`);
        const dataStats = await resStats.json();
        if (dataStats.success) {
            document.getElementById('report-revenue').innerText = `$${dataStats.stats.revenue.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            document.getElementById('report-cogs').innerText = `$${dataStats.stats.cogs.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            
            const profit = dataStats.stats.profit;
            const profitEl = document.getElementById('report-profit');
            profitEl.innerText = `$${profit.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            profitEl.className = profit >= 0 ? 'stat-value text-emerald' : 'stat-value text-indigo';
            
            document.getElementById('report-margin').innerText = `${dataStats.stats.margin_pct.toFixed(1)}%`;
        }
        
        // 2. Fetch margins profitability report table
        const resMargin = await fetch(`${API_BASE}/reports/margin`);
        const dataMargin = await resMargin.json();
        if (dataMargin.success) {
            const tbody = document.querySelector('#report-margin-table tbody');
            tbody.innerHTML = '';
            if (dataMargin.data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No sales records for profitability analysis.</td></tr>`;
            } else {
                dataMargin.data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${row.sku}</strong></td>
                        <td>${row.product_name || 'Unknown Item'}</td>
                        <td>${row.sales_qty}</td>
                        <td>$${row.gross_sales.toFixed(2)}</td>
                        <td class="${row.gross_profit >= 0 ? 'text-emerald' : 'text-indigo'}">$${row.gross_profit.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        // 3. Fetch Category distributions
        const resCat = await fetch(`${API_BASE}/reports/category`);
        const dataCat = await resCat.json();
        if (dataCat.success) {
            const tbody = document.querySelector('#report-category-table tbody');
            tbody.innerHTML = '';
            if (dataCat.data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No stock category data available.</td></tr>`;
            } else {
                dataCat.data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.category}</td>
                        <td>${row.product_count}</td>
                        <td>${row.stock_units || 0}</td>
                        <td>$${(row.asset_value || 0).toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        // 4. Fetch Supplier procurement details
        const resSup = await fetch(`${API_BASE}/reports/supplier`);
        const dataSup = await resSup.json();
        if (dataSup.success) {
            const tbody = document.querySelector('#report-supplier-table tbody');
            tbody.innerHTML = '';
            if (dataSup.data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No supplier stock data available.</td></tr>`;
            } else {
                dataSup.data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.company_name}</td>
                        <td>${row.product_count}</td>
                        <td>${row.stock_units || 0}</td>
                        <td>$${(row.asset_value || 0).toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        // 5. Receivables Aging
        const resAging = await fetch(`${API_BASE}/reports/aging`);
        const dataAging = await resAging.json();
        if (dataAging.success) {
            const tbody = document.querySelector('#report-aging-table tbody');
            tbody.innerHTML = '';
            if (dataAging.data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No outstanding accounts found.</td></tr>`;
            } else {
                dataAging.data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${row.party_name}</strong></td>
                        <td>$${row.total_debit.toFixed(2)}</td>
                        <td>$${row.total_credit.toFixed(2)}</td>
                        <td class="${row.balance > 0 ? 'text-indigo heavy-font' : (row.balance < 0 ? 'text-emerald heavy-font' : 'heavy-font')}">$${row.balance.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }
        showStatus("Business analytics compiled.");
    } catch (err) {
        showStatus("Error compilation reporting systems.", true);
    }
}

// ==============================================================================
// MODALS MANAGEMENT
// ==============================================================================

function closeAllModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.add('hidden'));
}
