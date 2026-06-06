import sys
import os
import sqlite3
import shutil
from datetime import datetime

class DatabaseManager:
    """Handles all SQLite interactions, auto-initialization, and transactions."""
    
    def __init__(self, db_path="business.db"):
        # Detect Vercel serverless / temporary environment
        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            tmp_dir = "/tmp"
            tmp_db_path = os.path.join(tmp_dir, "business.db")
            # Copy template db from project root to /tmp if it doesn't exist yet
            if not os.path.exists(tmp_db_path):
                src_db = os.path.abspath(db_path)
                if os.path.exists(src_db):
                    try:
                        shutil.copy2(src_db, tmp_db_path)
                    except Exception as e:
                        print(f"Error copying SQLite database to /tmp: {e}", file=sys.stderr)
            self.db_path = tmp_db_path
        else:
            self.db_path = db_path
            
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Creates tables if they do not exist and seeds default users."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL
                )
            """)
            
            # 2. Suppliers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT UNIQUE NOT NULL,
                    contact_name TEXT,
                    phone TEXT,
                    email TEXT,
                    address TEXT
                )
            """)

            # 3. Inventory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    sku TEXT UNIQUE NOT NULL,
                    quantity INTEGER NOT NULL,
                    purchase_price REAL NOT NULL,
                    selling_price REAL NOT NULL,
                    category TEXT DEFAULT 'Uncategorized',
                    subcategory TEXT DEFAULT 'None',
                    supplier_id INTEGER REFERENCES suppliers(id)
                )
            """)
            
            # Run ALTER queries just in case database exists without category/subcategory/supplier_id columns
            cursor.execute("PRAGMA table_info(inventory)")
            cols = [info[1] for info in cursor.fetchall()]
            if 'category' not in cols:
                cursor.execute("ALTER TABLE inventory ADD COLUMN category TEXT DEFAULT 'Uncategorized'")
            if 'subcategory' not in cols:
                cursor.execute("ALTER TABLE inventory ADD COLUMN subcategory TEXT DEFAULT 'None'")
            if 'supplier_id' not in cols:
                cursor.execute("ALTER TABLE inventory ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id)")
            
            # 4. Invoices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    party_name TEXT NOT NULL,
                    product_sku TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    total_amount REAL NOT NULL,
                    warranty TEXT,
                    date TEXT NOT NULL,
                    FOREIGN KEY (product_sku) REFERENCES inventory(sku)
                )
            """)
            
            # 5. Ledgers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ledgers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    party_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    debit REAL NOT NULL,
                    credit REAL NOT NULL
                )
            """)
            
            conn.commit()
            
            # Seed default users if empty
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO users (username, password, role) 
                    VALUES (?, ?, ?), (?, ?, ?)
                """, ("admin", "admin123", "Admin", "client", "client123", "Client"))
                
                # Seed default suppliers
                sample_suppliers = [
                    ("Global Tech Distributors", "John Doe", "123-456-7890", "john@globaltech.com", "123 Tech Way, Silicon Valley"),
                    ("Apex Components Ltd", "Jane Smith", "987-654-3210", "jane@apex.com", "456 Industry Ave, Seattle"),
                    ("Logitech Bulk Supply", "Bob Johnson", "555-019-2834", "bob@logitech-wholesale.com", "789 Logistics Blvd, Dallas")
                ]
                cursor.executemany("""
                    INSERT INTO suppliers (company_name, contact_name, phone, email, address)
                    VALUES (?, ?, ?, ?, ?)
                """, sample_suppliers)
                
                # Seed sample inventory items (including low-stock warnings)
                sample_items = [
                    ("Intel Core i7-13700K CPU", "880982", 12, 310.00, 380.00, "Processors", "Intel", 1),
                    ("NVIDIA RTX 4070 Ti GPU", "471120", 3, 680.00, 799.99, "Graphics Cards", "NVIDIA", 1),
                    ("Samsung 990 Pro 2TB SSD", "880609", 18, 110.00, 159.50, "Storage", "NVMe SSD", 2),
                    ("Corsair Vengeance 32GB RAM", "843591", 4, 75.00, 99.00, "Memory", "DDR5", 2),
                    ("Logitech MX Master 3S Mouse", "097855", 22, 55.00, 89.90, "Peripherals", "Mice", 3)
                ]
                for item in sample_items:
                    cursor.execute("""
                        INSERT INTO inventory (product_name, sku, quantity, purchase_price, selling_price, category, subcategory, supplier_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, item)
                
                # Seed initial transaction history
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                cursor.execute("""
                    INSERT INTO ledgers (party_name, date, description, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                """, ("client", now_str, "Opening Balance Deposit", 0.0, 500.00))
                
                conn.commit()
            else:
                # Ensure suppliers exist and are seeded even if users table is not empty
                cursor.execute("SELECT COUNT(*) FROM suppliers")
                if cursor.fetchone()[0] == 0:
                    sample_suppliers = [
                        ("Global Tech Distributors", "John Doe", "123-456-7890", "john@globaltech.com", "123 Tech Way, Silicon Valley"),
                        ("Apex Components Ltd", "Jane Smith", "987-654-3210", "jane@apex.com", "456 Industry Ave, Seattle"),
                        ("Logitech Bulk Supply", "Bob Johnson", "555-019-2834", "bob@logitech-wholesale.com", "789 Logistics Blvd, Dallas")
                    ]
                    cursor.executemany("""
                        INSERT INTO suppliers (company_name, contact_name, phone, email, address)
                        VALUES (?, ?, ?, ?, ?)
                    """, sample_suppliers)
                    conn.commit()
 
            # Associate existing items with first supplier if supplier_id is null and we have suppliers
            cursor.execute("SELECT id FROM suppliers LIMIT 1")
            first_supplier = cursor.fetchone()
            if first_supplier:
                cursor.execute("UPDATE inventory SET supplier_id = ? WHERE supplier_id IS NULL", (first_supplier[0],))
                conn.commit()

    # --- Auth Operations ---
    def authenticate(self, username, password):
        """Returns the role of the user if authentication succeeds, else None."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM users WHERE username = ? AND password = ?",
                (username, password)
            )
            row = cursor.fetchone()
            return row['role'] if row else None

    # --- Inventory Operations ---
    def get_inventory(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT inventory.*, suppliers.company_name as supplier_name 
                FROM inventory 
                LEFT JOIN suppliers ON inventory.supplier_id = suppliers.id
                ORDER BY inventory.product_name ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_inventory_item(self, sku):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT inventory.*, suppliers.company_name as supplier_name 
                FROM inventory 
                LEFT JOIN suppliers ON inventory.supplier_id = suppliers.id
                WHERE inventory.sku = ?
            """, (sku,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_inventory_item(self, name, sku, qty, purchase_price, selling_price, category='Uncategorized', subcategory='None', supplier_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inventory (product_name, sku, quantity, purchase_price, selling_price, category, subcategory, supplier_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, sku, qty, purchase_price, selling_price, category, subcategory, supplier_id))
            conn.commit()

    def update_inventory_item(self, item_id, name, sku, qty, purchase_price, selling_price, category='Uncategorized', subcategory='None', supplier_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE inventory 
                SET product_name = ?, sku = ?, quantity = ?, purchase_price = ?, selling_price = ?, category = ?, subcategory = ?, supplier_id = ?
                WHERE id = ?
            """, (name, sku, qty, purchase_price, selling_price, category, subcategory, supplier_id, item_id))
            conn.commit()

    def delete_inventory_item(self, item_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            conn.commit()

    def get_low_stock_items(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory WHERE quantity < 5 ORDER BY quantity ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_low_stock_count(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inventory WHERE quantity < 5")
            return cursor.fetchone()[0]

    # --- Billing & Ledger Transactions (ATOMIC) ---
    def create_invoice_cart_transaction(self, party_name, cart_items):
        """
        Executes invoice generation atomically:
        - Checks inventory levels
        - Decrements inventory stock
        - Adds invoice row
        - Posts a debit entry in ledgers for the party
        """
        conn = self.get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor = conn.cursor()
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            total_invoice_amount = 0.0
            descriptions = []
            
            for sku, qty, warranty in cart_items:
                # Retrieve item details
                cursor.execute(
                    "SELECT product_name, quantity, selling_price FROM inventory WHERE sku = ?", 
                    (sku,)
                )
                item = cursor.fetchone()
                if not item:
                    raise ValueError(f"SKU {sku} not found in inventory.")
                
                prod_name = item['product_name']
                curr_qty = item['quantity']
                price = item['selling_price']
                
                if qty <= 0:
                    raise ValueError(f"Quantity for {prod_name} must be greater than zero.")
                if curr_qty < qty:
                    raise ValueError(f"Insufficient stock for {prod_name}. Available: {curr_qty}, Requested: {qty}")
                
                # Update inventory quantity
                new_qty = curr_qty - qty
                cursor.execute(
                    "UPDATE inventory SET quantity = ? WHERE sku = ?", 
                    (new_qty, sku)
                )
                
                # Insert invoice
                line_total = qty * price
                total_invoice_amount += line_total
                cursor.execute("""
                    INSERT INTO invoices (party_name, product_sku, quantity, total_amount, warranty, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (party_name, sku, qty, line_total, warranty, date_str))
                
                descriptions.append(f"{prod_name} (x{qty})")
                
            # Post double-entry Ledger entry (Debit: party owes money)
            combined_desc = f"Purchase: " + ", ".join(descriptions)
            cursor.execute("""
                INSERT INTO ledgers (party_name, date, description, debit, credit)
                VALUES (?, ?, ?, ?, ?)
            """, (party_name, date_str, combined_desc, total_invoice_amount, 0.0))
            
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def create_collection_transaction(self, party_name, amount, description):
        """Posts manual cash receipts as a credit entry in the ledger."""
        conn = self.get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor = conn.cursor()
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            if amount <= 0:
                raise ValueError("Collection amount must be greater than zero.")
            
            # Post double-entry Ledger entry (Credit: party paid and reduced outstanding receivables)
            cursor.execute("""
                INSERT INTO ledgers (party_name, date, description, debit, credit)
                VALUES (?, ?, ?, ?, ?)
            """, (party_name, date_str, description, 0.0, amount))
            
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    # --- Financial Reports & Summaries ---
    def get_ledgers(self, party_name=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if party_name:
                cursor.execute("SELECT * FROM ledgers WHERE party_name = ? ORDER BY id ASC", (party_name,))
            else:
                cursor.execute("SELECT * FROM ledgers ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_ledger_summary(self, party_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(debit) as total_debit, SUM(credit) as total_credit 
                FROM ledgers 
                WHERE party_name = ?
            """, (party_name,))
            row = cursor.fetchone()
            debit = row['total_debit'] if row['total_debit'] else 0.0
            credit = row['total_credit'] if row['total_credit'] else 0.0
            return {
                'total_debit': debit,
                'total_credit': credit,
                'balance': debit - credit
            }

    def get_invoices(self, party_name=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if party_name:
                cursor.execute("""
                    SELECT invoices.*, inventory.product_name 
                    FROM invoices 
                    JOIN inventory ON invoices.product_sku = inventory.sku 
                    WHERE invoices.party_name = ? 
                    ORDER BY invoices.id DESC
                """, (party_name,))
            else:
                cursor.execute("""
                    SELECT invoices.*, inventory.product_name 
                    FROM invoices 
                    JOIN inventory ON invoices.product_sku = inventory.sku 
                    ORDER BY invoices.id DESC
                """)
            return [dict(r) for r in cursor.fetchall()]

    def get_total_sales(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_amount) FROM invoices")
            res = cursor.fetchone()[0]
            return res if res else 0.0

    def get_total_outstanding(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(debit) - SUM(credit) FROM ledgers")
            res = cursor.fetchone()[0]
            return res if res else 0.0

    def get_unique_parties(self):
        """Fetches list of all clients in system user table combined with existing ledger accounts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE role = 'Client'")
            parties = {r['username'] for r in cursor.fetchall()}
            
            cursor.execute("SELECT DISTINCT party_name FROM ledgers")
            for r in cursor.fetchall():
                parties.add(r['party_name'])
                
            cursor.execute("SELECT DISTINCT party_name FROM invoices")
            for r in cursor.fetchall():
                parties.add(r['party_name'])
                
            return sorted(list(parties))

    def get_client_stats(self, party_name):
        """Calculates specific stats card summary metrics for a client customer."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Total spent
            cursor.execute("SELECT SUM(total_amount) FROM invoices WHERE party_name = ?", (party_name,))
            res_spent = cursor.fetchone()[0]
            total_spent = res_spent if res_spent else 0.0
            
            # 2. Order count
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE party_name = ?", (party_name,))
            order_count = cursor.fetchone()[0]
            
            # 3. Balance sheet receivable
            summary = self.get_ledger_summary(party_name)
            
            return {
                'total_spent': total_spent,
                'order_count': order_count,
                'balance': summary['balance']
            }

    def get_invoice_items(self, party_name, date):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT invoices.*, inventory.product_name 
                FROM invoices 
                LEFT JOIN inventory ON invoices.product_sku = inventory.sku 
                WHERE invoices.party_name = ? AND invoices.date = ?
                ORDER BY invoices.id ASC
            """, (party_name, date))
            return [dict(r) for r in cursor.fetchall()]

    def get_invoice_by_item_id(self, item_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT party_name, date FROM invoices WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                return []
            return self.get_invoice_items(row['party_name'], row['date'])

    def get_last_invoice_by_party(self, party_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM invoices WHERE party_name = ?", (party_name,))
            row = cursor.fetchone()
            if not row or not row[0]:
                return []
            return self.get_invoice_items(party_name, row[0])

    def get_grouped_invoices(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MIN(id) as invoice_id, party_name, date, COUNT(*) as total_items, SUM(total_amount) as grand_total
                FROM invoices
                GROUP BY party_name, date
                ORDER BY invoice_id DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    # --- Supplier Operations ---
    def get_suppliers(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM suppliers ORDER BY company_name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def add_supplier(self, company_name, contact_name, phone, email, address):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO suppliers (company_name, contact_name, phone, email, address)
                VALUES (?, ?, ?, ?, ?)
            """, (company_name, contact_name, phone, email, address))
            conn.commit()

    def update_supplier(self, supplier_id, company_name, contact_name, phone, email, address):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE suppliers 
                SET company_name = ?, contact_name = ?, phone = ?, email = ?, address = ?
                WHERE id = ?
            """, (company_name, contact_name, phone, email, address, supplier_id))
            conn.commit()

    def delete_supplier(self, supplier_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            conn.commit()

    def get_or_create_supplier_id(self, company_name):
        """Finds supplier ID by company name, or creates it if it does not exist."""
        company_name = company_name.strip()
        if not company_name:
            return None
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM suppliers WHERE company_name = ?", (company_name,))
            row = cursor.fetchone()
            if row:
                return row['id']
                
            # Create a new supplier if not found
            cursor.execute("""
                INSERT INTO suppliers (company_name, contact_name, phone, email, address)
                VALUES (?, ?, ?, ?, ?)
            """, (company_name, "N/A", "N/A", "N/A", "N/A"))
            conn.commit()
            return cursor.lastrowid
