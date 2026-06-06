import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add root directory to python path for db_manager import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_manager import DatabaseManager

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Requests for local testing

# Instantiate the shared DatabaseManager
db = DatabaseManager()

# --- Auth Endpoint ---
@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400
    
    role = db.authenticate(username, password)
    if role:
        return jsonify({"success": True, "role": role, "username": username})
    else:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401


# --- Dashboard & Overview Stats ---
@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    role = request.args.get('role')
    username = request.args.get('username')
    
    if not role or not username:
        return jsonify({"error": "Role and username parameters are required"}), 400
        
    if role == "Admin":
        low_stock_count = db.get_low_stock_count()
        sales = db.get_total_sales()
        outstanding = db.get_total_outstanding()
        low_items = db.get_low_stock_items()
        
        return jsonify({
            "success": True,
            "stats": {
                "sales": sales,
                "outstanding": outstanding,
                "lowStockCount": low_stock_count
            },
            "lowStockItems": low_items
        })
    else:
        # Client View
        stats = db.get_client_stats(username)
        invoices = db.get_invoices(username)
        
        return jsonify({
            "success": True,
            "stats": {
                "orderCount": stats['order_count'],
                "totalSpent": stats['total_spent'],
                "balance": stats['balance']
            },
            "invoices": invoices
        })


# --- Inventory CRUD ---
@app.route('/api/inventory', methods=['GET', 'POST', 'PUT'])
def handle_inventory():
    if request.method == 'GET':
        return jsonify({"success": True, "inventory": db.get_inventory()})
        
    data = request.json or {}
    name = data.get('product_name')
    sku = data.get('sku')
    qty = data.get('quantity')
    purchase_price = data.get('purchase_price')
    selling_price = data.get('selling_price')
    category = data.get('category', 'Uncategorized')
    subcategory = data.get('subcategory', 'None')
    supplier_company = data.get('supplier_name', '')
    
    if not name or not sku or qty is None or purchase_price is None or selling_price is None:
        return jsonify({"success": False, "error": "Missing required inventory fields"}), 400
        
    # Find or create supplier id from name
    supplier_id = None
    if supplier_company:
        supplier_id = db.get_or_create_supplier_id(supplier_company)
        
    try:
        if request.method == 'POST':
            db.add_inventory_item(name, sku, int(qty), float(purchase_price), float(selling_price), category, subcategory, supplier_id)
            return jsonify({"success": True, "message": "Item added successfully"})
            
        elif request.method == 'PUT':
            item_id = data.get('id')
            if not item_id:
                return jsonify({"success": False, "error": "Item ID required for update"}), 400
            db.update_inventory_item(item_id, name, sku, int(qty), float(purchase_price), float(selling_price), category, subcategory, supplier_id)
            return jsonify({"success": True, "message": "Item updated successfully"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory/delete/<int:item_id>', methods=['DELETE', 'POST'])
def delete_inventory(item_id):
    try:
        db.delete_inventory_item(item_id)
        return jsonify({"success": True, "message": "Item deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Suppliers CRUD ---
@app.route('/api/suppliers', methods=['GET', 'POST', 'PUT'])
def handle_suppliers():
    if request.method == 'GET':
        return jsonify({"success": True, "suppliers": db.get_suppliers()})
        
    data = request.json or {}
    company_name = data.get('company_name')
    contact_name = data.get('contact_name', 'N/A')
    phone = data.get('phone', 'N/A')
    email = data.get('email', 'N/A')
    address = data.get('address', 'N/A')
    
    if not company_name:
        return jsonify({"success": False, "error": "Company name is required"}), 400
        
    try:
        if request.method == 'POST':
            db.add_supplier(company_name, contact_name, phone, email, address)
            return jsonify({"success": True, "message": "Supplier added successfully"})
            
        elif request.method == 'PUT':
            supplier_id = data.get('id')
            if not supplier_id:
                return jsonify({"success": False, "error": "Supplier ID required for update"}), 400
            db.update_supplier(supplier_id, company_name, contact_name, phone, email, address)
            return jsonify({"success": True, "message": "Supplier updated successfully"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/suppliers/delete/<int:supplier_id>', methods=['DELETE', 'POST'])
def delete_supplier(supplier_id):
    try:
        db.delete_supplier(supplier_id)
        return jsonify({"success": True, "message": "Supplier deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Invoices ---
@app.route('/api/invoices', methods=['GET', 'POST'])
def handle_invoices():
    if request.method == 'GET':
        party = request.args.get('party_name')
        if party:
            return jsonify({"success": True, "invoices": db.get_invoices(party)})
        else:
            return jsonify({"success": True, "invoices": db.get_grouped_invoices()})
            
    # POST - Create Invoicing Cart Transaction
    data = request.json or {}
    party_name = data.get('party_name')
    cart = data.get('cart') # List of [sku, qty, warranty]
    
    if not party_name or not cart:
        return jsonify({"success": False, "error": "Party name and cart items are required"}), 400
        
    # Convert list of dicts to list of tuples if fronted sends it as objects
    processed_cart = []
    for item in cart:
        if isinstance(item, dict):
            processed_cart.append((item.get('sku'), int(item.get('qty', 0)), item.get('warranty', 'None')))
        else:
            processed_cart.append((item[0], int(item[1]), item[2]))
            
    success, err = db.create_invoice_cart_transaction(party_name, processed_cart)
    if success:
        return jsonify({"success": True, "message": "Invoice created successfully"})
    else:
        return jsonify({"success": False, "error": err}), 400

@app.route('/api/invoices/items', methods=['GET'])
def get_invoice_items():
    party_name = request.args.get('party_name')
    date = request.args.get('date')
    if not party_name or not date:
        return jsonify({"success": False, "error": "party_name and date required"}), 400
    try:
        items = db.get_invoice_items(party_name, date)
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Ledgers & Payments ---
@app.route('/api/ledgers', methods=['GET'])
def get_ledgers():
    party = request.args.get('party_name')
    return jsonify({"success": True, "ledgers": db.get_ledgers(party)})

@app.route('/api/ledgers/summary/<party_name>', methods=['GET'])
def get_ledger_summary(party_name):
    return jsonify({"success": True, "summary": db.get_ledger_summary(party_name)})

@app.route('/api/collections', methods=['POST'])
def handle_collections():
    data = request.json or {}
    party_name = data.get('party_name')
    amount = data.get('amount')
    description = data.get('description', 'Cash Receipt')
    
    if not party_name or amount is None:
        return jsonify({"success": False, "error": "Party name and amount required"}), 400
        
    success, err = db.create_collection_transaction(party_name, float(amount), description)
    if success:
        return jsonify({"success": True, "message": "Payment collected and posted successfully"})
    else:
        return jsonify({"success": False, "error": err}), 400


# --- Parties ---
@app.route('/api/parties', methods=['GET'])
def get_parties():
    return jsonify({"success": True, "parties": db.get_unique_parties()})


# --- Reports & Analytics ---
@app.route('/api/reports/stats', methods=['GET'])
def get_reports_stats():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 1. Revenue
        revenue = db.get_total_sales()
        
        # 2. COGS
        cursor.execute("""
            SELECT SUM(invoices.quantity * inventory.purchase_price) 
            FROM invoices 
            LEFT JOIN inventory ON invoices.product_sku = inventory.sku
        """)
        cogs_res = cursor.fetchone()[0]
        cogs = cogs_res if cogs_res else 0.0
        
        # 3. Calculation
        profit = revenue - cogs
        margin_pct = (profit / revenue * 100) if revenue > 0 else 0.0
        
        conn.close()
        return jsonify({
            "success": True,
            "stats": {
                "revenue": revenue,
                "cogs": cogs,
                "profit": profit,
                "margin_pct": margin_pct
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/margin', methods=['GET'])
def get_reports_margin():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT invoices.product_sku as sku, inventory.product_name, SUM(invoices.quantity) as sales_qty, 
                   SUM(invoices.total_amount) as gross_sales,
                   SUM(invoices.total_amount - invoices.quantity * inventory.purchase_price) as gross_profit
            FROM invoices
            LEFT JOIN inventory ON invoices.product_sku = inventory.sku
            GROUP BY invoices.product_sku
            ORDER BY gross_sales DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/category', methods=['GET'])
def get_reports_category():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as product_count, SUM(quantity) as stock_units,
                   SUM(quantity * purchase_price) as asset_value
            FROM inventory
            GROUP BY category
            ORDER BY asset_value DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/supplier', methods=['GET'])
def get_reports_supplier():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT suppliers.company_name, COUNT(inventory.id) as product_count, SUM(inventory.quantity) as stock_units,
                   SUM(inventory.quantity * inventory.purchase_price) as asset_value
            FROM suppliers
            LEFT JOIN inventory ON suppliers.id = inventory.supplier_id
            GROUP BY suppliers.id
            ORDER BY asset_value DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/aging', methods=['GET'])
def get_reports_aging():
    try:
        parties = db.get_unique_parties()
        data = []
        for party in parties:
            summary = db.get_ledger_summary(party)
            data.append({
                "party_name": party,
                "total_debit": summary['total_debit'],
                "total_credit": summary['total_credit'],
                "balance": summary['balance']
            })
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Vercel entrypoint compatibility
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
