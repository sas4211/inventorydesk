#!/usr/bin/env python3
"""
Inventory, Billing, and Double-entry Ledger Management System
Built with Python (PyQt6) and SQLite.

Author: Expert Desktop Application Software Engineer
A production-ready desktop solution featuring:
- Role-based Access Control (RBAC Login Dialog)
- Barcode Scanner Integration with automatic focus and transactional look-up
- Real-time Low Stock Warnings (Status banners, soft crimson highlights, popups)
- Atomic transactions for invoices and manual collections
- Premium Light and Dark mode stylesheets
"""

import sys
import os
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFormLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QDoubleSpinBox, QSpinBox, QGroupBox, QStatusBar, QFrame, QAbstractItemView,
    QSplitter, QScrollArea, QTextBrowser, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QColor, QFont, QPalette, QBrush, QIcon, QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

# ==============================================================================
# DATABASE MANAGER
# ==============================================================================

class DatabaseManager:
    """Handles all SQLite interactions, auto-initialization, and transactions."""
    
    def __init__(self, db_path="business.db"):
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


# ==============================================================================
# STYLE SHEETS (DESIGN SYSTEM)
# ==============================================================================

def get_light_theme():
    return """
    QMainWindow {
        background-color: #f1f5f9;
    }
    QWidget {
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        color: #0f172a;
        font-size: 13px;
    }
    QFrame#card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    QLabel#cardTitle {
        font-weight: bold;
        color: #64748b;
        font-size: 11px;
        text-transform: uppercase;
    }
    QLabel#cardValue {
        font-size: 22px;
        font-weight: bold;
        color: #1e1b4b;
    }
    QTabWidget::pane {
        border: 1px solid #e2e8f0;
        background-color: #ffffff;
        border-radius: 8px;
    }
    QTabBar::tab {
        background-color: #e2e8f0;
        border: 1px solid #cbd5e1;
        border-bottom: none;
        padding: 8px 18px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 4px;
        color: #475569;
        font-weight: 500;
    }
    QTabBar::tab:selected {
        background-color: #ffffff;
        color: #4f46e5;
        font-weight: bold;
        border-top: 3px solid #4f46e5;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px 12px;
        background-color: #ffffff;
        color: #0f172a;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
        border: 2px solid #4f46e5;
    }
    QLineEdit#barcodeScannerEntry {
        border: 2px solid #4f46e5;
        background-color: #eef2ff;
        font-weight: bold;
        font-size: 14px;
        color: #312e81;
    }
    QPushButton {
        background-color: #4f46e5;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #4338ca;
    }
    QPushButton:pressed {
        background-color: #3730a3;
    }
    QPushButton#dangerButton {
        background-color: #ef4444;
    }
    QPushButton#dangerButton:hover {
        background-color: #dc2626;
    }
    QPushButton#dangerButton:pressed {
        background-color: #b91c1c;
    }
    QPushButton#secondaryButton {
        background-color: #f8fafc;
        color: #334155;
        border: 1px solid #cbd5e1;
    }
    QPushButton#secondaryButton:hover {
        background-color: #f1f5f9;
    }
    QPushButton#secondaryButton:pressed {
        background-color: #e2e8f0;
    }
    QTableWidget {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        gridline-color: #f1f5f9;
        border-radius: 6px;
        selection-background-color: #e0e7ff;
        selection-color: #312e81;
    }
    QHeaderView::section {
        background-color: #f8fafc;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #e2e8f0;
        font-weight: bold;
        color: #475569;
    }
    QStatusBar {
        background-color: #f8fafc;
        color: #64748b;
        border-top: 1px solid #e2e8f0;
    }
    QGroupBox {
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        margin-top: 12px;
        font-weight: bold;
        padding-top: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 4px;
        color: #4f46e5;
    }
    """

def get_dark_theme():
    return """
    QMainWindow {
        background-color: #0f172a;
    }
    QWidget {
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        color: #f8fafc;
        font-size: 13px;
    }
    QFrame#card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
    }
    QLabel#cardTitle {
        font-weight: bold;
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
    }
    QLabel#cardValue {
        font-size: 22px;
        font-weight: bold;
        color: #2dd4bf;
    }
    QTabWidget::pane {
        border: 1px solid #334155;
        background-color: #1e293b;
        border-radius: 8px;
    }
    QTabBar::tab {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-bottom: none;
        padding: 8px 18px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 4px;
        color: #94a3b8;
        font-weight: 500;
    }
    QTabBar::tab:selected {
        background-color: #1e293b;
        color: #14b8a6;
        font-weight: bold;
        border-top: 3px solid #14b8a6;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 6px 12px;
        background-color: #0f172a;
        color: #f8fafc;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
        border: 2px solid #14b8a6;
    }
    QLineEdit#barcodeScannerEntry {
        border: 2px solid #14b8a6;
        background-color: #115e59;
        font-weight: bold;
        font-size: 14px;
        color: #f8fafc;
    }
    QPushButton {
        background-color: #14b8a6;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #0d9488;
    }
    QPushButton:pressed {
        background-color: #0f766e;
    }
    QPushButton#dangerButton {
        background-color: #f43f5e;
    }
    QPushButton#dangerButton:hover {
        background-color: #e11d48;
    }
    QPushButton#dangerButton:pressed {
        background-color: #be123c;
    }
    QPushButton#secondaryButton {
        background-color: #334155;
        color: #cbd5e1;
        border: 1px solid #475569;
    }
    QPushButton#secondaryButton:hover {
        background-color: #475569;
    }
    QPushButton#secondaryButton:pressed {
        background-color: #64748b;
    }
    QTableWidget {
        background-color: #1e293b;
        border: 1px solid #334155;
        gridline-color: #334155;
        border-radius: 6px;
        selection-background-color: #115e59;
        selection-color: #ffffff;
    }
    QHeaderView::section {
        background-color: #0f172a;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #334155;
        font-weight: bold;
        color: #cbd5e1;
    }
    QStatusBar {
        background-color: #0f172a;
        color: #94a3b8;
        border-top: 1px solid #334155;
    }
    QGroupBox {
        border: 1px solid #334155;
        border-radius: 8px;
        margin-top: 12px;
        font-weight: bold;
        padding-top: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 4px;
        color: #14b8a6;
    }
    """

# ==============================================================================
# INVOICE GENERATION & PRINT SUPPORT
# ==============================================================================

def generate_invoice_html(party_name, date, items):
    grand_total = sum(item['total_amount'] for item in items)
    invoice_num = items[0]['id'] if items else 0
    
    rows_html = ""
    for item in items:
        price = item['total_amount'] / item['quantity'] if item['quantity'] > 0 else 0
        rows_html += f"""
        <tr>
            <td>{item['product_sku']}</td>
            <td>{item['product_name']}</td>
            <td style="text-align: center;">{item['quantity']}</td>
            <td>{item['warranty'] or 'N/A'}</td>
            <td style="text-align: right;">${price:,.2f}</td>
            <td style="text-align: right;">${item['total_amount']:,.2f}</td>
        </tr>
        """
        
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #1e293b;
            margin: 30px;
            line-height: 1.6;
            background-color: #ffffff;
        }}
        .header {{
            border-bottom: 2px solid #4f46e5;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .brand {{
            font-size: 24px;
            font-weight: bold;
            color: #4f46e5;
        }}
        .invoice-title {{
            font-size: 20px;
            font-weight: bold;
            float: right;
            color: #1e1b4b;
        }}
        .clear {{
            clear: both;
        }}
        .details {{
            margin-bottom: 30px;
        }}
        .details-col {{
            width: 48%;
            float: left;
        }}
        .details-col-right {{
            width: 48%;
            float: right;
            text-align: right;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th {{
            background-color: #f8fafc;
            color: #475569;
            font-weight: bold;
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #cbd5e1;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .total-row {{
            font-weight: bold;
            font-size: 16px;
            border-top: 2px solid #cbd5e1;
            border-bottom: none;
        }}
        .footer {{
            margin-top: 50px;
            text-align: center;
            color: #64748b;
            font-size: 12px;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
        }}
    </style>
    </head>
    <body>
        <div class="header">
            <span class="brand">👔 Enterprise Operations Ledger</span>
            <span class="invoice-title">INVOICE</span>
            <div class="clear"></div>
        </div>
        
        <div class="details">
            <div class="details-col">
                <strong>Billed To:</strong><br>
                Customer Name: {party_name}<br>
            </div>
            <div class="details-col-right">
                <strong>Invoice Details:</strong><br>
                Invoice #: INV-{invoice_num:05d}<br>
                Date: {date}<br>
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
                {rows_html}
                <tr class="total-row">
                    <td colspan="4"></td>
                    <td style="text-align: right;">Grand Total:</td>
                    <td style="text-align: right;">${grand_total:,.2f}</td>
                </tr>
            </tbody>
        </table>
        
        <div class="footer">
            Thank you for your business! If you have any questions, please contact support.
        </div>
    </body>
    </html>
    """
    return html

class InvoicePrintDialog(QDialog):
    """Preview and Print/Save dialog for invoices."""
    
    def __init__(self, html_content, default_filename, parent=None):
        super().__init__(parent)
        self.html_content = html_content
        self.default_filename = default_filename
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Invoice Print Preview")
        self.resize(750, 800)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # QTextBrowser for previewing
        self.preview = QTextBrowser()
        self.preview.setHtml(self.html_content)
        self.preview.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        layout.addWidget(self.preview)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.print_btn = QPushButton("🖨️ Print Invoice")
        self.print_btn.clicked.connect(self.print_invoice)
        btn_layout.addWidget(self.print_btn)
        
        self.pdf_btn = QPushButton("💾 Save as PDF")
        self.pdf_btn.setObjectName("secondaryButton")
        self.pdf_btn.clicked.connect(self.save_as_pdf)
        btn_layout.addWidget(self.pdf_btn)
        
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("secondaryButton")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def print_invoice(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            doc = QTextDocument()
            doc.setHtml(self.html_content)
            doc.print(printer)
            QMessageBox.information(self, "Success", "Invoice sent to printer.")
            
    def save_as_pdf(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Invoice as PDF",
            self.default_filename,
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setPageSize(QPrinter.PageSize.A4)
            printer.setOutputFileName(file_path)
            
            doc = QTextDocument()
            doc.setHtml(self.html_content)
            doc.print(printer)
            QMessageBox.information(self, "Success", f"Invoice saved to:\n{file_path}")

# ==============================================================================
# SECURE ACCESS CONTROL LAYER (LOGIN GATEWAY)
# ==============================================================================

class LoginDialog(QDialog):
    """Modal Login Dialog that interrupts application initialization."""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.username = None
        self.role = None
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Secure Login Gateway")
        self.setFixedSize(380, 290)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header banner
        header = QLabel("Enterprise Business Suite")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4f46e5; margin-bottom: 4px;")
        # Set dynamic color based on theme
        layout.addWidget(header)
        
        subtitle = QLabel("Please sign in to access your dashboard")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #64748b; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(subtitle)
        
        # Input Form
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        self.user_input = QLineEdit()
        self.user_input.setText("admin")
        self.user_input.setPlaceholderText("Username")
        form_layout.addRow("Username:", self.user_input)
        
        self.pass_input = QLineEdit()
        self.pass_input.setText("admin123")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Password")
        form_layout.addRow("Password:", self.pass_input)
        
        layout.addLayout(form_layout)
        
        # Error text
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.login_btn = QPushButton("Sign In")
        self.login_btn.clicked.connect(self.handle_login)
        self.login_btn.setDefault(True)
        btn_layout.addWidget(self.login_btn)
        
        self.cancel_btn = QPushButton("Exit")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Highlighted line focus
        self.user_input.setFocus()

    def handle_login(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text().strip()
        
        if not username or not password:
            self.error_label.setText("Please fill in both fields.")
            return
            
        role = self.db.authenticate(username, password)
        if role:
            self.username = username
            self.role = role
            self.accept()
        else:
            self.error_label.setText("Invalid credentials. Please try again.")
            self.pass_input.clear()
            self.user_input.setFocus()

    def get_credentials(self):
        return self.username, self.role

# ==============================================================================
# DASHBOARD MODULE
# ==============================================================================

class DashboardTab(QWidget):
    """Dynamically generated Dashboard for Admin (full metrics) or Client (restricted orders)."""
    
    def __init__(self, db_manager, username, role, is_dark_mode_fn):
        super().__init__()
        self.db = db_manager
        self.username = username
        self.role = role
        self.is_dark_mode = is_dark_mode_fn
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(16)
        
        # Admin Banner Setup
        if self.role == "Admin":
            self.warning_banner = QLabel()
            self.warning_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.warning_banner.setWordWrap(True)
            self.warning_banner.hide()
            self.main_layout.addWidget(self.warning_banner)
            
        # Grid layout for summary stats
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(16)
        self.main_layout.addLayout(self.stats_layout)
        
        # Bottom area (Table for Orders / Alerts)
        self.table_group = QGroupBox()
        self.table_layout = QVBoxLayout()
        self.table_layout.setContentsMargins(12, 12, 12, 12)
        
        self.table_label = QLabel()
        self.table_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 6px;")
        self.table_layout.addWidget(self.table_label)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_layout.addWidget(self.table)
        
        if self.role != "Admin":
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            self.print_btn = QPushButton("🖨️ Print Selected Invoice")
            self.print_btn.clicked.connect(self.print_selected_invoice)
            btn_layout.addWidget(self.print_btn)
            self.table_layout.addLayout(btn_layout)
            
        self.table_group.setLayout(self.table_layout)
        self.main_layout.addWidget(self.table_group)
        
        self.setLayout(self.main_layout)
        self.refresh()

    def create_stat_card(self, title, value):
        frame = QFrame()
        frame.setObjectName("card")
        
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)
        
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        card_layout.addWidget(title_label)
        
        val_label = QLabel(value)
        val_label.setObjectName("cardValue")
        card_layout.addWidget(val_label)
        
        frame.setLayout(card_layout)
        return frame

    def refresh(self):
        # Clear stats layout
        for i in reversed(range(self.stats_layout.count())):
            self.stats_layout.itemAt(i).widget().setParent(None)
            
        if self.role == "Admin":
            # 1. Check low stock warning pipeline
            low_stock_count = self.db.get_low_stock_count()
            if low_stock_count > 0:
                self.warning_banner.setText(
                    f"⚠️ CRITICAL DEFICIT: {low_stock_count} item(s) are below the low stock threshold (5 units)!"
                )
                # Apply bright warning red background style
                bg_color = "#991b1b" if self.is_dark_mode() else "#fecaca"
                text_color = "#fecaca" if self.is_dark_mode() else "#991b1b"
                self.warning_banner.setStyleSheet(
                    f"background-color: {bg_color}; color: {text_color}; font-weight: bold; "
                    f"padding: 12px; border-radius: 8px; font-size: 13px;"
                )
                self.warning_banner.show()
            else:
                self.warning_banner.hide()
                
            # 2. Stats Cards
            sales = self.db.get_total_sales()
            outstanding = self.db.get_total_outstanding()
            
            self.stats_layout.addWidget(self.create_stat_card("Total Sales Revenue", f"${sales:,.2f}"))
            self.stats_layout.addWidget(self.create_stat_card("Total Receivables Balance", f"${outstanding:,.2f}"))
            self.stats_layout.addWidget(self.create_stat_card("Deficit Stock Lines", str(low_stock_count)))
            
            # 3. Alert Table Setup
            self.table_group.setTitle("Critical Low-Stock Inventory Alerts")
            self.table_label.setText("Stock quantities requiring immediate replenishment:")
            
            low_items = self.db.get_low_stock_items()
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["SKU", "Product Name", "Units Left", "Unit Price"])
            self.table.setRowCount(len(low_items))
            
            for row, item in enumerate(low_items):
                self.table.setItem(row, 0, QTableWidgetItem(item['sku']))
                self.table.setItem(row, 1, QTableWidgetItem(item['product_name']))
                
                qty_item = QTableWidgetItem(str(item['quantity']))
                # soft red cells background
                bg_color = QColor(127, 29, 29) if self.is_dark_mode() else QColor(254, 226, 226)
                text_color = QColor(254, 226, 226) if self.is_dark_mode() else QColor(153, 27, 27)
                qty_item.setBackground(QBrush(bg_color))
                qty_item.setForeground(QBrush(text_color))
                self.table.setItem(row, 2, qty_item)
                
                self.table.setItem(row, 3, QTableWidgetItem(f"${item['selling_price']:,.2f}"))
                
        else:
            # Client View Summary
            stats = self.db.get_client_stats(self.username)
            self.stats_layout.addWidget(self.create_stat_card("Total Outbound Orders", str(stats['order_count'])))
            self.stats_layout.addWidget(self.create_stat_card("Total Invoice Volume", f"${stats['total_spent']:,.2f}"))
            
            balance = stats['balance']
            bal_str = f"${balance:,.2f}" if balance >= 0 else f"-${abs(balance):,.2f}"
            self.stats_layout.addWidget(self.create_stat_card("My Outstanding Balance", bal_str))
            
            # 3. Client Orders Table
            self.table_group.setTitle("Order Dispatch History")
            self.table_label.setText("Your transaction records and invoice orders:")
            
            invoices = self.db.get_invoices(self.username)
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["Invoice ID", "Date", "Product SKU / Item Description", "Qty Ordered", "Total Price"])
            self.table.setRowCount(len(invoices))
            
            for row, inv in enumerate(invoices):
                self.table.setItem(row, 0, QTableWidgetItem(f"INV#{inv['id']}"))
                self.table.setItem(row, 1, QTableWidgetItem(inv['date']))
                self.table.setItem(row, 2, QTableWidgetItem(f"[{inv['product_sku']}] {inv['product_name']}"))
                self.table.setItem(row, 3, QTableWidgetItem(str(inv['quantity'])))
                self.table.setItem(row, 4, QTableWidgetItem(f"${inv['total_amount']:,.2f}"))

    def print_selected_invoice(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an invoice from the history table first.")
            return
            
        row = selected[0].row()
        inv_id_str = self.table.item(row, 0).text()
        try:
            inv_id = int(inv_id_str.replace("INV#", ""))
            items = self.db.get_invoice_by_item_id(inv_id)
            if not items:
                QMessageBox.warning(self, "Not Found", "Invoice details could not be found.")
                return
                
            party_name = items[0]['party_name']
            date = items[0]['date']
            
            html = generate_invoice_html(party_name, date, items)
            dialog = InvoicePrintDialog(html, f"invoice_{inv_id}.pdf", self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not print invoice: {str(e)}")

# ==============================================================================
# INVENTORY TAB (ADMIN ONLY)
# ==============================================================================

class InventoryTab(QWidget):
    """Inventory management panel including editing forms, categories, suppliers, and stock highlights."""
    
    def __init__(self, db_manager, is_dark_mode_fn, on_change_callback):
        super().__init__()
        self.db = db_manager
        self.is_dark_mode = is_dark_mode_fn
        self.on_change = on_change_callback
        
        self.selected_item_id = None
        self.view_mode = "List"  # Default view mode
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Left Panel - Inventory Views
        table_container = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(10)
        
        # Search layout with view toggle
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search stock:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by Name or SKU...")
        self.search_input.textChanged.connect(self.populate_views)
        search_layout.addWidget(self.search_input)
        
        self.toggle_btn = QPushButton("🌳 Switch to Hierarchy Tree")
        self.toggle_btn.setObjectName("secondaryButton")
        self.toggle_btn.setFixedWidth(200)
        self.toggle_btn.clicked.connect(self.toggle_view_mode)
        search_layout.addWidget(self.toggle_btn)
        
        table_layout.addLayout(search_layout)
        
        # Table View
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Product Name", "SKU", "Qty", "Purchase Price", "Selling Price", "Category", "Supplier"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.clicked.connect(self.on_row_selected)
        table_layout.addWidget(self.table)
        
        # Tree View (Hierarchy representation)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Catalog Hierarchy", "SKU / Code", "Qty in Stock", "Purchase Price", "Selling Price"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().resizeSection(0, 320)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.tree.hide()
        table_layout.addWidget(self.tree)
        
        table_container.setLayout(table_layout)
        layout.addWidget(table_container, stretch=3)
        
        # Right Panel - Action Form
        form_group = QGroupBox("Stock Form Editor")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.sku_input = QLineEdit()
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("e.g. Processors, Memory...")
        self.subcategory_input = QLineEdit()
        self.subcategory_input.setPlaceholderText("e.g. Intel, DDR5...")
        
        self.supplier_combo = QComboBox()
        
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 1000000)
        
        self.purchase_input = QDoubleSpinBox()
        self.purchase_input.setRange(0.0, 1000000.0)
        self.purchase_input.setDecimals(2)
        self.purchase_input.setPrefix("$")
        
        self.selling_input = QDoubleSpinBox()
        self.selling_input.setRange(0.0, 1000000.0)
        self.selling_input.setDecimals(2)
        self.selling_input.setPrefix("$")
        
        form_layout.addRow("Product Name:", self.name_input)
        form_layout.addRow("SKU / Barcode:", self.sku_input)
        form_layout.addRow("Category:", self.category_input)
        form_layout.addRow("Subcategory:", self.subcategory_input)
        form_layout.addRow("Supplier:", self.supplier_combo)
        form_layout.addRow("Qty in Stock:", self.qty_input)
        form_layout.addRow("Purchase Price:", self.purchase_input)
        form_layout.addRow("Selling Price:", self.selling_input)
        
        # Form buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        
        self.save_btn = QPushButton("Save Product")
        self.save_btn.clicked.connect(self.save_product)
        btn_layout.addWidget(self.save_btn)
        
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(self.clear_btn)
        
        self.delete_btn = QPushButton("Delete Product")
        self.delete_btn.setObjectName("dangerButton")
        self.delete_btn.clicked.connect(self.delete_product)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        form_layout.addRow(btn_layout)
        
        # Bulk CSV Group Box
        csv_group = QGroupBox("Bulk CSV Actions")
        csv_lay = QVBoxLayout()
        csv_lay.setSpacing(8)
        
        self.import_btn = QPushButton("📥 Import CSV...")
        self.import_btn.setObjectName("secondaryButton")
        self.import_btn.clicked.connect(self.import_csv)
        csv_lay.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("📤 Export CSV...")
        self.export_btn.setObjectName("secondaryButton")
        self.export_btn.clicked.connect(self.export_csv)
        csv_lay.addWidget(self.export_btn)
        
        csv_group.setLayout(csv_lay)
        form_layout.addRow(csv_group)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group, stretch=1)
        
        self.setLayout(layout)
        self.sync_suppliers()
        self.populate_views()

    def sync_suppliers(self):
        """Refreshes the supplier dropdown options."""
        self.supplier_combo.blockSignals(True)
        curr = self.supplier_combo.currentData()
        self.supplier_combo.clear()
        self.supplier_combo.addItem("Select Supplier...", "")
        suppliers = self.db.get_suppliers()
        for s in suppliers:
            self.supplier_combo.addItem(s['company_name'], s['id'])
        if curr is not None:
            idx = self.supplier_combo.findData(curr)
            if idx >= 0:
                self.supplier_combo.setCurrentIndex(idx)
        self.supplier_combo.blockSignals(False)

    def toggle_view_mode(self):
        if self.view_mode == "List":
            self.view_mode = "Tree"
            self.table.hide()
            self.tree.show()
            self.toggle_btn.setText("📋 Switch to Grid List")
        else:
            self.view_mode = "List"
            self.tree.hide()
            self.table.show()
            self.toggle_btn.setText("🌳 Switch to Hierarchy Tree")
        self.populate_views()

    def populate_views(self):
        self.sync_suppliers()
        if self.view_mode == "List":
            self.populate_table()
        else:
            self.populate_tree()

    def populate_table(self):
        self.table.setRowCount(0)
        items = self.db.get_inventory()
        query = self.search_input.text().strip().lower()
        
        filtered = []
        for item in items:
            if not query or query in item['product_name'].lower() or query in item['sku'].lower():
                filtered.append(item)
                
        self.table.setRowCount(len(filtered))
        
        low_stock_bg = QColor(127, 29, 29) if self.is_dark_mode() else QColor(254, 226, 226)
        low_stock_fg = QColor(254, 226, 226) if self.is_dark_mode() else QColor(153, 27, 27)
        
        for row, item in enumerate(filtered):
            is_low_stock = item['quantity'] < 5
            supplier_name = item['supplier_name'] or "N/A"
            
            for col in range(8):
                val = ""
                if col == 0: val = str(item['id'])
                elif col == 1: val = item['product_name']
                elif col == 2: val = item['sku']
                elif col == 3: val = str(item['quantity'])
                elif col == 4: val = f"${item['purchase_price']:,.2f}"
                elif col == 5: val = f"${item['selling_price']:,.2f}"
                elif col == 6: val = item['category'] or "Uncategorized"
                elif col == 7: val = supplier_name
                
                table_item = QTableWidgetItem(val)
                if is_low_stock:
                    table_item.setBackground(QBrush(low_stock_bg))
                    table_item.setForeground(QBrush(low_stock_fg))
                self.table.setItem(row, col, table_item)

    def populate_tree(self):
        self.tree.clear()
        items = self.db.get_inventory()
        query = self.search_input.text().strip().lower()
        
        filtered = []
        for item in items:
            if not query or query in item['product_name'].lower() or query in item['sku'].lower():
                filtered.append(item)
                
        # Group items by category -> subcategory
        hierarchy = {}
        for item in filtered:
            cat = item['category'] or "Uncategorized"
            subcat = item['subcategory'] or "None"
            
            if cat not in hierarchy:
                hierarchy[cat] = {}
            if subcat not in hierarchy[cat]:
                hierarchy[cat][subcat] = []
            hierarchy[cat][subcat].append(item)
            
        low_stock_bg = QColor(127, 29, 29) if self.is_dark_mode() else QColor(254, 226, 226)
        low_stock_fg = QColor(254, 226, 226) if self.is_dark_mode() else QColor(153, 27, 27)
        
        for cat, subcats in hierarchy.items():
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, cat)
            cat_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.tree.addTopLevelItem(cat_item)
            
            for subcat, products in subcats.items():
                sub_item = QTreeWidgetItem(cat_item)
                sub_item.setText(0, subcat)
                sub_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Medium))
                cat_item.addChild(sub_item)
                
                for prod in products:
                    prod_item = QTreeWidgetItem(sub_item)
                    prod_item.setText(0, prod['product_name'])
                    prod_item.setText(1, prod['sku'])
                    prod_item.setText(2, str(prod['quantity']))
                    prod_item.setText(3, f"${prod['purchase_price']:,.2f}")
                    prod_item.setText(4, f"${prod['selling_price']:,.2f}")
                    
                    # Store product ID as custom user data
                    prod_item.setData(0, Qt.ItemDataRole.UserRole, prod['id'])
                    
                    if prod['quantity'] < 5:
                        for c in range(5):
                            prod_item.setBackground(c, QBrush(low_stock_bg))
                            prod_item.setForeground(c, QBrush(low_stock_fg))
                            
                    sub_item.addChild(prod_item)
                    
        self.tree.expandAll()

    def on_row_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self.selected_item_id = int(self.table.item(row, 0).text())
        self.load_item_to_form(self.selected_item_id)

    def on_tree_item_clicked(self, item, column):
        prod_id = item.data(0, Qt.ItemDataRole.UserRole)
        if prod_id is not None:
            self.selected_item_id = int(prod_id)
            self.load_item_to_form(self.selected_item_id)
        else:
            self.clear_form()

    def load_item_to_form(self, item_id):
        items = self.db.get_inventory()
        target = next((item for item in items if item['id'] == item_id), None)
        
        if target:
            self.name_input.setText(target['product_name'])
            self.sku_input.setText(target['sku'])
            self.category_input.setText(target['category'] or "")
            self.subcategory_input.setText(target['subcategory'] or "")
            
            # Select supplier in combobox
            supplier_id = target['supplier_id']
            idx = self.supplier_combo.findData(supplier_id)
            if idx >= 0:
                self.supplier_combo.setCurrentIndex(idx)
            else:
                self.supplier_combo.setCurrentIndex(0)
                
            self.qty_input.setValue(target['quantity'])
            self.purchase_input.setValue(target['purchase_price'])
            self.selling_input.setValue(target['selling_price'])
            
            self.delete_btn.setEnabled(True)
            self.save_btn.setText("Update Product")

    def clear_form(self):
        self.selected_item_id = None
        self.name_input.clear()
        self.sku_input.clear()
        self.category_input.clear()
        self.subcategory_input.clear()
        self.supplier_combo.setCurrentIndex(0)
        self.qty_input.setValue(0)
        self.purchase_input.setValue(0.0)
        self.selling_input.setValue(0.0)
        
        self.delete_btn.setEnabled(False)
        self.save_btn.setText("Save Product")
        self.table.clearSelection()
        self.tree.clearSelection()

    def save_product(self):
        name = self.name_input.text().strip()
        sku = self.sku_input.text().strip()
        category = self.category_input.text().strip() or "Uncategorized"
        subcategory = self.subcategory_input.text().strip() or "None"
        supplier_id = self.supplier_combo.currentData()
        if supplier_id == "":
            supplier_id = None
            
        qty = self.qty_input.value()
        p_price = self.purchase_input.value()
        s_price = self.selling_input.value()
        
        if not name or not sku:
            QMessageBox.warning(self, "Validation Error", "Product Name and SKU are required fields.")
            return
            
        try:
            if self.selected_item_id:
                # Update item
                self.db.update_inventory_item(self.selected_item_id, name, sku, qty, p_price, s_price, category, subcategory, supplier_id)
                QMessageBox.information(self, "Success", "Product details updated successfully.")
            else:
                # Add item
                self.db.add_inventory_item(name, sku, qty, p_price, s_price, category, subcategory, supplier_id)
                QMessageBox.information(self, "Success", "Product added successfully.")
                
            self.clear_form()
            self.populate_views()
            self.on_change()  # Refresh other views
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"An item with SKU barcode '{sku}' already exists in inventory.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {str(e)}")

    def delete_product(self):
        if not self.selected_item_id:
            return
            
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            "Are you sure you want to delete this product? This may break historical barcode references in invoices.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_inventory_item(self.selected_item_id)
                QMessageBox.information(self, "Deleted", "Product deleted from inventory catalog.")
                self.clear_form()
                self.populate_views()
                self.on_change()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete product: {str(e)}")

    def export_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Inventory to CSV",
            "inventory_catalog.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            items = self.db.get_inventory()
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header row
                writer.writerow([
                    "Product Name", "SKU", "Quantity", 
                    "Purchase Price", "Selling Price", 
                    "Category", "Subcategory", "Supplier"
                ])
                for item in items:
                    writer.writerow([
                        item['product_name'],
                        item['sku'],
                        item['quantity'],
                        item['purchase_price'],
                        item['selling_price'],
                        item['category'] or "Uncategorized",
                        item['subcategory'] or "None",
                        item['supplier_name'] or "N/A"
                    ])
            QMessageBox.information(self, "Export Successful", f"Successfully exported {len(items)} catalog items to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred during CSV export:\n{str(e)}")

    def import_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Inventory from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    QMessageBox.warning(self, "Import Failed", "The CSV file is empty.")
                    return
                
                # Check headers (supporting flexible header names)
                # Map headers to column indices
                header_map = {}
                for idx, h in enumerate(header):
                    clean_h = h.strip().lower()
                    if "product" in clean_h or "name" in clean_h:
                        header_map["name"] = idx
                    elif "sku" in clean_h or "code" in clean_h or "barcode" in clean_h:
                        header_map["sku"] = idx
                    elif "qty" in clean_h or "quantity" in clean_h or "units" in clean_h:
                        header_map["qty"] = idx
                    elif "purchase" in clean_h or "cost" in clean_h:
                        header_map["purchase"] = idx
                    elif "selling" in clean_h or "price" in clean_h:
                        header_map["selling"] = idx
                    elif "category" in clean_h:
                        header_map["category"] = idx
                    elif "subcategory" in clean_h or "sub-category" in clean_h:
                        header_map["subcategory"] = idx
                    elif "supplier" in clean_h or "vendor" in clean_h:
                        header_map["supplier"] = idx
                
                # Validate critical headers (name and sku are required)
                if "name" not in header_map or "sku" not in header_map:
                    QMessageBox.critical(
                        self, 
                        "Import Failed", 
                        "CSV must contain 'Product Name' and 'SKU' columns.\n"
                        "Supported headers: Product Name, SKU, Quantity, Purchase Price, Selling Price, Category, Subcategory, Supplier."
                    )
                    return
                
                added_count = 0
                updated_count = 0
                errors = []
                
                for row_idx, row in enumerate(reader, 2):
                    if not row or all(cell.strip() == "" for cell in row):
                        continue # Skip empty rows
                        
                    try:
                        name = row[header_map["name"]].strip()
                        sku = row[header_map["sku"]].strip()
                        
                        if not name or not sku:
                            errors.append(f"Row {row_idx}: Product Name and SKU cannot be blank.")
                            continue
                            
                        # Default values for optional fields
                        qty = 0
                        if "qty" in header_map and len(row) > header_map["qty"]:
                            val = row[header_map["qty"]].strip()
                            qty = int(val) if val else 0
                            
                        purchase_price = 0.0
                        if "purchase" in header_map and len(row) > header_map["purchase"]:
                            val = row[header_map["purchase"]].strip().replace("$", "").replace(",", "")
                            purchase_price = float(val) if val else 0.0
                            
                        selling_price = 0.0
                        if "selling" in header_map and len(row) > header_map["selling"]:
                            val = row[header_map["selling"]].strip().replace("$", "").replace(",", "")
                            selling_price = float(val) if val else 0.0
                            
                        category = "Uncategorized"
                        if "category" in header_map and len(row) > header_map["category"]:
                            category = row[header_map["category"]].strip() or "Uncategorized"
                            
                        subcategory = "None"
                        if "subcategory" in header_map and len(row) > header_map["subcategory"]:
                            subcategory = row[header_map["subcategory"]].strip() or "None"
                            
                        supplier_id = None
                        if "supplier" in header_map and len(row) > header_map["supplier"]:
                            supplier_name = row[header_map["supplier"]].strip()
                            if supplier_name and supplier_name.upper() != "N/A":
                                supplier_id = self.db.get_or_create_supplier_id(supplier_name)
                                
                        # Check database for existing SKU
                        existing = self.db.get_inventory_item(sku)
                        if existing:
                            self.db.update_inventory_item(
                                existing['id'], name, sku, qty, purchase_price, 
                                selling_price, category, subcategory, supplier_id
                            )
                            updated_count += 1
                        else:
                            self.db.add_inventory_item(
                                name, sku, qty, purchase_price, 
                                selling_price, category, subcategory, supplier_id
                            )
                            added_count += 1
                            
                    except Exception as err:
                        errors.append(f"Row {row_idx}: Parsing error: {str(err)}")
                
                # Show results report
                report = f"Import Summary:\n- Added: {added_count} new products\n- Updated: {updated_count} existing products"
                if errors:
                    report += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
                    if len(errors) > 10:
                        report += f"\n...and {len(errors) - 10} more errors."
                        
                self.populate_views()
                self.on_change()
                
                if errors:
                    QMessageBox.warning(self, "Import Complete (With Warnings)", report)
                else:
                    QMessageBox.information(self, "Import Successful", report)
                    
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to read CSV file:\n{str(e)}")


# ==============================================================================
# INVOICING / BILLING MODULE
# ==============================================================================

class InvoicingTab(QWidget):
    """Billing Panel featuring hardware barcode scanner capture and cart checkout."""
    
    def __init__(self, db_manager, is_dark_mode_fn, on_change_callback):
        super().__init__()
        self.db = db_manager
        self.is_dark_mode = is_dark_mode_fn
        self.on_change = on_change_callback
        self.cart = []  # List of dicts representing cart items
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 3. Barcode Scanner Entry Container
        barcode_group = QGroupBox("HARDWARE BARCODE SCANNER ENTRY & FILE UPLOAD")
        barcode_layout = QHBoxLayout()
        barcode_layout.setContentsMargins(12, 12, 12, 12)
        
        self.barcode_input = QLineEdit()
        self.barcode_input.setObjectName("barcodeScannerEntry")
        self.barcode_input.setPlaceholderText("SCAN OR TYPE PRODUCT SKU HERE AND PRESS ENTER...")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        barcode_layout.addWidget(self.barcode_input, stretch=4)
        
        self.upload_btn = QPushButton("📁 Upload SKU File")
        self.upload_btn.setObjectName("secondaryButton")
        self.upload_btn.setToolTip("Upload TXT/CSV list of SKUs (one per line, or SKU,qty) to batch add to cart")
        self.upload_btn.clicked.connect(self.handle_file_upload)
        barcode_layout.addWidget(self.upload_btn, stretch=1)
        
        barcode_group.setLayout(barcode_layout)
        layout.addWidget(barcode_group)
        
        # Main Work Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel - Billing Forms
        billing_form_group = QGroupBox("Transaction Checkout Details")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # Party Selector (Client combobox)
        self.party_combo = QComboBox()
        self.party_combo.setEditable(True)
        form_layout.addRow("Customer / Party:", self.party_combo)
        
        # Product Dropdown Selector
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self.on_product_combo_changed)
        form_layout.addRow("Select Product:", self.product_combo)
        
        # Product details display labels
        self.stock_lbl = QLabel("Qty available: N/A")
        self.stock_lbl.setStyleSheet("font-weight: bold; color: #64748b;")
        form_layout.addRow("", self.stock_lbl)
        
        self.price_lbl = QLabel("Price: N/A")
        self.price_lbl.setStyleSheet("font-weight: bold; color: #64748b;")
        form_layout.addRow("", self.price_lbl)
        
        # Checkout Qty
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 10000)
        self.qty_spin.setValue(1)
        form_layout.addRow("Checkout Qty:", self.qty_spin)
        
        # Warranty field
        self.warranty_input = QLineEdit()
        self.warranty_input.setText("1 Year Parts & Labor")
        form_layout.addRow("Warranty Lifetime:", self.warranty_input)
        
        # Cart actions
        self.add_cart_btn = QPushButton("Add Item to Cart")
        self.add_cart_btn.clicked.connect(self.add_to_cart)
        form_layout.addRow(self.add_cart_btn)
        
        billing_form_group.setLayout(form_layout)
        splitter.addWidget(billing_form_group)
        
        # Right Panel - Cart Table
        cart_group = QGroupBox("Active Shopping Cart")
        cart_layout = QVBoxLayout()
        cart_layout.setContentsMargins(12, 12, 12, 12)
        
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(6)
        self.cart_table.setHorizontalHeaderLabels(["SKU", "Product Name", "Qty", "Unit Price", "Total Price", "Action"])
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cart_layout.addWidget(self.cart_table)
        
        # Bottom Summary & Checkout Button
        cart_bottom = QHBoxLayout()
        self.total_lbl = QLabel("Grand Total: $0.00")
        self.total_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #4f46e5;")
        cart_bottom.addWidget(self.total_lbl)
        
        self.checkout_btn = QPushButton("Complete Checkout & Generate Invoice")
        self.checkout_btn.clicked.connect(self.process_checkout)
        self.checkout_btn.setEnabled(False)
        cart_bottom.addWidget(self.checkout_btn)
        
        cart_layout.addLayout(cart_bottom)
        cart_group.setLayout(cart_layout)
        splitter.addWidget(cart_group)
        
        # Splitter sizing ratio
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)
        
        self.setLayout(layout)
        self.sync_combos()

    def sync_combos(self):
        """Populates and updates product and party dropdown selectors."""
        # Save current selections
        curr_party = self.party_combo.currentText()
        
        # Populate parties (customers)
        self.party_combo.clear()
        parties = self.db.get_unique_parties()
        self.party_combo.addItems(parties)
        if curr_party:
            self.party_combo.setEditText(curr_party)
        
        # Populate products dropdown
        self.product_combo.clear()
        self.product_combo.addItem("Select Product...", "")
        items = self.db.get_inventory()
        for item in items:
            self.product_combo.addItem(
                f"[{item['sku']}] {item['product_name']} ({item['quantity']} left)", 
                item['sku']
            )

    def on_product_combo_changed(self, index):
        if index <= 0:
            self.stock_lbl.setText("Qty available: N/A")
            self.price_lbl.setText("Price: N/A")
            return
            
        sku = self.product_combo.currentData()
        item = self.db.get_inventory_item(sku)
        
        if item:
            self.stock_lbl.setText(f"Qty available: {item['quantity']} units")
            self.price_lbl.setText(f"Price: ${item['selling_price']:,.2f}")
            self.qty_spin.setRange(1, item['quantity'] if item['quantity'] > 0 else 1)
            
            # 4. Proactive low stock warnings: trigger immediate popup warning
            if item['quantity'] < 5:
                QMessageBox.warning(
                    self,
                    "Low Stock Warning",
                    f"⚠️ PROACTIVE ALERT:\n"
                    f"The product '{item['product_name']}' is running critically low!\n"
                    f"Only {item['quantity']} unit(s) remain in stock."
                )

    def handle_barcode_scan(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return
            
        # Hook carriage return signal to run immediate lookup
        item = self.db.get_inventory_item(barcode)
        
        if item:
            # Select it in system dropdown
            idx = self.product_combo.findData(barcode)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)
                
            self.barcode_input.clear()
            # Focus on the QSpinBox for qty selection
            self.qty_spin.setFocus()
        else:
            # Critical warning dialogue and clear entry line
            QMessageBox.critical(
                self, 
                "Critical Scan Error", 
                f"Barcode string '{barcode}' did not match any SKU in the inventory database."
            )
            self.barcode_input.clear()
            self.barcode_input.setFocus()

    def handle_file_upload(self):
        """Allows uploading a text file (.txt/.csv) containing SKUs to batch import into cart."""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Upload Barcode File", 
            "", 
            "Text Files (*.txt *.csv);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            success_count = 0
            failed_skus = []
            low_stock_warnings = []
            
            for line_num, line in enumerate(lines, 1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith('#'):
                    continue
                
                # Support comma-separated format: SKU,quantity (e.g. 880982,3)
                parts = clean_line.split(',')
                sku = parts[0].strip()
                qty = 1
                if len(parts) > 1:
                    try:
                        qty = int(parts[1].strip())
                    except ValueError:
                        pass
                
                # Query item details
                item = self.db.get_inventory_item(sku)
                if not item:
                    failed_skus.append(f"Line {line_num}: SKU '{sku}' not found in database")
                    continue
                
                if item['quantity'] < qty:
                    failed_skus.append(f"Line {line_num}: SKU '{sku}' has insufficient stock (Requested {qty}, Available {item['quantity']})")
                    continue
                
                # Check if item is already in cart
                existing = next((i for i in self.cart if i['sku'] == sku), None)
                if existing:
                    new_qty = existing['quantity'] + qty
                    if new_qty > item['quantity']:
                        failed_skus.append(f"Line {line_num}: Adding '{sku}' to cart exceeds total stock")
                        continue
                    existing['quantity'] = new_qty
                    existing['total'] = new_qty * item['selling_price']
                else:
                    self.cart.append({
                        'sku': sku,
                        'name': item['product_name'],
                        'quantity': qty,
                        'price': item['selling_price'],
                        'total': qty * item['selling_price'],
                        'warranty': self.warranty_input.text().strip()
                    })
                
                if item['quantity'] < 5:
                    low_stock_warnings.append(f"'{item['product_name']}' has only {item['quantity']} units left")
                
                success_count += 1
                
            self.update_cart_table()
            
            # Show summary report
            report = f"Import Summary:\n- Successfully added {success_count} item(s) to the cart.\n"
            if failed_skus:
                report += f"\nFailed items / errors:\n" + "\n".join(failed_skus[:10])
                if len(failed_skus) > 10:
                    report += f"\n...and {len(failed_skus) - 10} more errors."
            
            if low_stock_warnings:
                report += f"\n\n⚠️ Low Stock Alerts:\n" + "\n".join(low_stock_warnings[:5])
                
            if failed_skus:
                QMessageBox.warning(self, "File Import Complete (With Warnings)", report)
            else:
                QMessageBox.information(self, "File Import Successful", report)
                
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read file:\n{str(e)}")
            
        self.barcode_input.setFocus()

    def add_to_cart(self):
        sku = self.product_combo.currentData()
        if not sku:
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid product.")
            return
            
        qty = self.qty_spin.value()
        item = self.db.get_inventory_item(sku)
        
        if not item:
            return
            
        if item['quantity'] < qty:
            QMessageBox.critical(
                self, 
                "Stock Deficit", 
                f"Cannot add to cart. Requesting {qty} units, but only {item['quantity']} remain."
            )
            return
            
        # Check if item is already in cart
        existing = next((i for i in self.cart if i['sku'] == sku), None)
        if existing:
            new_qty = existing['quantity'] + qty
            if new_qty > item['quantity']:
                QMessageBox.critical(
                    self, 
                    "Stock Deficit", 
                    f"Cannot add more units. Cart has {existing['quantity']}, adding {qty} exceeds stock limit."
                )
                return
            existing['quantity'] = new_qty
            existing['total'] = new_qty * item['selling_price']
        else:
            self.cart.append({
                'sku': sku,
                'name': item['product_name'],
                'quantity': qty,
                'price': item['selling_price'],
                'total': qty * item['selling_price'],
                'warranty': self.warranty_input.text().strip()
            })
            
        self.qty_spin.setValue(1)
        self.update_cart_table()
        
        # Refocus scanner entry for seamless workflow
        self.barcode_input.setFocus()

    def remove_cart_item(self, row):
        self.cart.pop(row)
        self.update_cart_table()
        self.barcode_input.setFocus()

    def update_cart_table(self):
        self.cart_table.setRowCount(0)
        self.cart_table.setRowCount(len(self.cart))
        
        grand_total = 0.0
        for row, item in enumerate(self.cart):
            self.cart_table.setItem(row, 0, QTableWidgetItem(item['sku']))
            self.cart_table.setItem(row, 1, QTableWidgetItem(item['name']))
            self.cart_table.setItem(row, 2, QTableWidgetItem(str(item['quantity'])))
            self.cart_table.setItem(row, 3, QTableWidgetItem(f"${item['price']:,.2f}"))
            self.cart_table.setItem(row, 4, QTableWidgetItem(f"${item['total']:,.2f}"))
            
            # Action button
            del_btn = QPushButton("Remove")
            del_btn.setObjectName("dangerButton")
            del_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
            # Connect row index properly
            del_btn.clicked.connect(lambda checked, r=row: self.remove_cart_item(r))
            self.cart_table.setCellWidget(row, 5, del_btn)
            
            grand_total += item['total']
            
        self.total_lbl.setText(f"Grand Total: ${grand_total:,.2f}")
        self.checkout_btn.setEnabled(len(self.cart) > 0)

    def process_checkout(self):
        party_name = self.party_combo.currentText().strip()
        if not party_name:
            QMessageBox.warning(self, "Required Input", "Please specify a customer/party name.")
            return
            
        # Structure payload
        items_payload = [(item['sku'], item['quantity'], item['warranty']) for item in self.cart]
        
        # Run atomic checkout transaction
        success, error_msg = self.db.create_invoice_cart_transaction(party_name, items_payload)
        
        if success:
            reply = QMessageBox.question(
                self,
                "Checkout Completed",
                f"Invoice generated successfully under customer profile '{party_name}'.\n\n"
                f"Would you like to print or save the invoice PDF?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # Fetch invoice items we just generated
                    items = self.db.get_last_invoice_by_party(party_name)
                    if items:
                        inv_id = items[0]['id']
                        date = items[0]['date']
                        html = generate_invoice_html(party_name, date, items)
                        dialog = InvoicePrintDialog(html, f"invoice_{inv_id}.pdf", self)
                        dialog.exec()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not print invoice: {str(e)}")
                    
            self.cart.clear()
            self.update_cart_table()
            self.on_change()  # Sync other modules
        else:
            QMessageBox.critical(
                self, 
                "Transaction Aborted", 
                f"Atomic invoicing transaction failed:\n{error_msg}"
            )
            
        self.barcode_input.setFocus()

# ==============================================================================
# LEDGER MODULE
# ==============================================================================

class LedgersTab(QWidget):
    """Financial Ledger Panel summarizing transactions and balance sheets."""
    
    def __init__(self, db_manager, username, role):
        super().__init__()
        self.db = db_manager
        self.username = username
        self.role = role
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header / Party Selection
        header_layout = QHBoxLayout()
        
        if self.role == "Admin":
            header_layout.addWidget(QLabel("Select Customer Account Ledger:"))
            self.party_combo = QComboBox()
            self.party_combo.currentIndexChanged.connect(self.populate_ledger)
            header_layout.addWidget(self.party_combo)
        else:
            lbl = QLabel(f"Personal Financial Ledger: <b>{self.username}</b>")
            lbl.setStyleSheet("font-size: 15px;")
            header_layout.addWidget(lbl)
            
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Summary outstanding card
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("card")
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(16, 16, 16, 16)
        
        self.debit_lbl = QLabel("Total Debits: $0.00")
        self.debit_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #475569;")
        summary_layout.addWidget(self.debit_lbl)
        
        self.credit_lbl = QLabel("Total Credits: $0.00")
        self.credit_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #475569;")
        summary_layout.addWidget(self.credit_lbl)
        
        self.balance_lbl = QLabel("Net Balance: $0.00")
        self.balance_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #4f46e5;")
        summary_layout.addWidget(self.balance_lbl)
        
        self.summary_frame.setLayout(summary_layout)
        layout.addWidget(self.summary_frame)
        
        # Ledger table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Timestamp", "Audit Description", "Debit (+)", "Credit (-)", "Running Balance"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().resizeSection(2, 350)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        self.sync_parties()

    def sync_parties(self):
        if self.role == "Admin":
            self.party_combo.blockSignals(True)
            curr = self.party_combo.currentText()
            self.party_combo.clear()
            self.party_combo.addItems(self.db.get_unique_parties())
            if curr:
                idx = self.party_combo.findText(curr)
                if idx >= 0:
                    self.party_combo.setCurrentIndex(idx)
            self.party_combo.blockSignals(False)
            
        self.populate_ledger()

    def populate_ledger(self):
        party = self.party_combo.currentText() if self.role == "Admin" else self.username
        
        self.table.setRowCount(0)
        if not party:
            self.debit_lbl.setText("Total Debits: $0.00")
            self.credit_lbl.setText("Total Credits: $0.00")
            self.balance_lbl.setText("Net Balance: $0.00")
            return
            
        records = self.db.get_ledgers(party)
        self.table.setRowCount(len(records))
        
        total_debit = 0.0
        total_credit = 0.0
        running_bal = 0.0
        
        for row, rec in enumerate(records):
            self.table.setItem(row, 0, QTableWidgetItem(str(rec['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(rec['date']))
            self.table.setItem(row, 2, QTableWidgetItem(rec['description']))
            
            deb = rec['debit']
            cred = rec['credit']
            
            total_debit += deb
            total_credit += cred
            running_bal += (deb - cred)
            
            self.table.setItem(row, 3, QTableWidgetItem(f"${deb:,.2f}" if deb > 0 else ""))
            self.table.setItem(row, 4, QTableWidgetItem(f"${cred:,.2f}" if cred > 0 else ""))
            
            bal_str = f"${running_bal:,.2f}" if running_bal >= 0 else f"-${abs(running_bal):,.2f}"
            self.table.setItem(row, 5, QTableWidgetItem(bal_str))
            
        # Update summary labels
        self.debit_lbl.setText(f"Total Debits: ${total_debit:,.2f}")
        self.credit_lbl.setText(f"Total Credits: ${total_credit:,.2f}")
        
        bal_str = f"${running_bal:,.2f}" if running_bal >= 0 else f"-${abs(running_bal):,.2f}"
        self.balance_lbl.setText(f"Net Outstanding Balance: {bal_str}")
        
        # Color Net Balance
        if running_bal > 0:
            self.balance_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;") # Debit outstanding
        else:
            self.balance_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #22c55e;") # Paid off/Prepaid

# ==============================================================================
# MANUAL COLLECTIONS TAB (ADMIN ONLY)
# ==============================================================================

class CollectionsTab(QWidget):
    """Allows Admin to post manual cash credits to customer outstanding balances."""
    
    def __init__(self, db_manager, on_change_callback):
        super().__init__()
        self.db = db_manager
        self.on_change = on_change_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Card form centered
        form_frame = QFrame()
        form_frame.setObjectName("card")
        form_frame.setMaximumWidth(500)
        
        form_layout = QFormLayout()
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(16)
        
        title = QLabel("Manual Cash Collections")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4f46e5;")
        form_layout.addRow(title)
        
        subtitle = QLabel("Record cash collections and apply credits to decrease receivables.")
        subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        form_layout.addRow(subtitle)
        
        # Fields
        self.party_combo = QComboBox()
        self.party_combo.currentIndexChanged.connect(self.update_balance_info)
        form_layout.addRow("Select Party Profile:", self.party_combo)
        
        self.bal_info = QLabel("Net Outstanding: N/A")
        self.bal_info.setStyleSheet("font-weight: bold; font-size: 13px;")
        form_layout.addRow("", self.bal_info)
        
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 1000000.0)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$")
        form_layout.addRow("Cash Receipt Amount:", self.amount_spin)
        
        self.notes_input = QLineEdit()
        self.notes_input.setText("Cash Collection Payment - Thank you")
        form_layout.addRow("Receipt Memo Details:", self.notes_input)
        
        self.apply_btn = QPushButton("Post Credit Collection")
        self.apply_btn.clicked.connect(self.submit_payment)
        form_layout.addRow(self.apply_btn)
        
        form_frame.setLayout(form_layout)
        
        # Center alignment
        cent_lay = QHBoxLayout()
        cent_lay.addStretch()
        cent_lay.addWidget(form_frame)
        cent_lay.addStretch()
        layout.addLayout(cent_lay)
        
        self.setLayout(layout)
        self.sync_parties()

    def sync_parties(self):
        self.party_combo.blockSignals(True)
        curr = self.party_combo.currentText()
        self.party_combo.clear()
        self.party_combo.addItems(self.db.get_unique_parties())
        if curr:
            idx = self.party_combo.findText(curr)
            if idx >= 0:
                self.party_combo.setCurrentIndex(idx)
        self.party_combo.blockSignals(False)
        self.update_balance_info()

    def update_balance_info(self):
        party = self.party_combo.currentText()
        if not party:
            self.bal_info.setText("Net Outstanding: N/A")
            return
            
        summary = self.db.get_ledger_summary(party)
        bal = summary['balance']
        bal_str = f"${bal:,.2f}" if bal >= 0 else f"-${abs(bal):,.2f}"
        self.bal_info.setText(f"Outstanding Receivable: {bal_str}")
        
        # Highlight green if clear, red if they owe
        if bal > 0:
            self.bal_info.setStyleSheet("font-weight: bold; color: #ef4444;")
        else:
            self.bal_info.setStyleSheet("font-weight: bold; color: #22c55e;")

    def submit_payment(self):
        party = self.party_combo.currentText().strip()
        amount = self.amount_spin.value()
        desc = self.notes_input.text().strip()
        
        if not party:
            QMessageBox.warning(self, "Required Input", "Please select a customer profile.")
            return
            
        if amount <= 0:
            QMessageBox.warning(self, "Required Input", "Collection amount must be positive.")
            return
            
        success, error_msg = self.db.create_collection_transaction(party, amount, desc)
        
        if success:
            QMessageBox.information(
                self, 
                "Transaction Posted", 
                f"Successfully credited ${amount:,.2f} against customer balance '{party}'."
            )
            self.amount_spin.setValue(0.0)
            self.notes_input.setText("Cash Collection Payment - Thank you")
            self.on_change()  # Sync other tabs
        else:
            QMessageBox.critical(
                self, 
                "Failed", 
                f"Failed to post manual cash payment:\n{error_msg}"
            )

# ==============================================================================
# SUPPLIERS MASTER TAB (ADMIN ONLY)
# ==============================================================================

class SuppliersTab(QWidget):
    """Supplier management panel for Admin to view and edit supplier profiles."""
    
    def __init__(self, db_manager, on_change_callback):
        super().__init__()
        self.db = db_manager
        self.on_change = on_change_callback
        self.selected_supplier_id = None
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Left Panel - Supplier Table
        table_container = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(10)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search suppliers:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by Company Name...")
        self.search_input.textChanged.connect(self.populate_table)
        search_layout.addWidget(self.search_input)
        table_layout.addLayout(search_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Company Name", "Contact Person", "Phone", "Email"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.clicked.connect(self.on_row_selected)
        table_layout.addWidget(self.table)
        
        table_container.setLayout(table_layout)
        layout.addWidget(table_container, stretch=3)
        
        # Right Panel - Form Editor
        form_group = QGroupBox("Supplier Profile Form")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        self.company_input = QLineEdit()
        self.contact_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.address_input = QLineEdit()
        
        form_layout.addRow("Company Name:", self.company_input)
        form_layout.addRow("Contact Name:", self.contact_input)
        form_layout.addRow("Phone Number:", self.phone_input)
        form_layout.addRow("Email Address:", self.email_input)
        form_layout.addRow("Business Address:", self.address_input)
        
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        
        self.save_btn = QPushButton("Save Supplier")
        self.save_btn.clicked.connect(self.save_supplier)
        btn_layout.addWidget(self.save_btn)
        
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(self.clear_btn)
        
        self.delete_btn = QPushButton("Delete Supplier")
        self.delete_btn.setObjectName("dangerButton")
        self.delete_btn.clicked.connect(self.delete_supplier)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        form_layout.addRow(btn_layout)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group, stretch=1)
        
        self.setLayout(layout)
        self.populate_table()
        
    def populate_table(self):
        self.table.setRowCount(0)
        suppliers = self.db.get_suppliers()
        query = self.search_input.text().strip().lower()
        
        filtered = []
        for s in suppliers:
            if not query or query in s['company_name'].lower():
                filtered.append(s)
                
        self.table.setRowCount(len(filtered))
        for row, s in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(str(s['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(s['company_name']))
            self.table.setItem(row, 2, QTableWidgetItem(s['contact_name'] or ""))
            self.table.setItem(row, 3, QTableWidgetItem(s['phone'] or ""))
            self.table.setItem(row, 4, QTableWidgetItem(s['email'] or ""))
            
    def on_row_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self.selected_supplier_id = int(self.table.item(row, 0).text())
        
        suppliers = self.db.get_suppliers()
        target = next((s for s in suppliers if s['id'] == self.selected_supplier_id), None)
        
        if target:
            self.company_input.setText(target['company_name'])
            self.contact_input.setText(target['contact_name'] or "")
            self.phone_input.setText(target['phone'] or "")
            self.email_input.setText(target['email'] or "")
            self.address_input.setText(target['address'] or "")
            
            self.delete_btn.setEnabled(True)
            self.save_btn.setText("Update Supplier")
            
    def clear_form(self):
        self.selected_supplier_id = None
        self.company_input.clear()
        self.contact_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.address_input.clear()
        
        self.delete_btn.setEnabled(False)
        self.save_btn.setText("Save Supplier")
        self.table.clearSelection()
        
    def save_supplier(self):
        company = self.company_input.text().strip()
        contact = self.contact_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        
        if not company:
            QMessageBox.warning(self, "Validation Error", "Company Name is a required field.")
            return
            
        try:
            if self.selected_supplier_id:
                self.db.update_supplier(self.selected_supplier_id, company, contact, phone, email, address)
                QMessageBox.information(self, "Success", "Supplier profile updated.")
            else:
                self.db.add_supplier(company, contact, phone, email, address)
                QMessageBox.information(self, "Success", "Supplier profile created.")
                
            self.clear_form()
            self.populate_table()
            self.on_change()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"A supplier with name '{company}' already exists.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def delete_supplier(self):
        if not self.selected_supplier_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this supplier profile? Existing inventory links will be unassigned.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_supplier(self.selected_supplier_id)
                QMessageBox.information(self, "Deleted", "Supplier deleted.")
                self.clear_form()
                self.populate_table()
                self.on_change()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

# ==============================================================================
# ANALYTICS & REPORTS TAB (ADMIN ONLY)
# ==============================================================================

class ReportsTab(QWidget):
    """Analytics & Reports tab displaying business metrics and tables."""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Summary Header layout
        self.summary_layout = QHBoxLayout()
        self.summary_layout.setSpacing(16)
        layout.addLayout(self.summary_layout)
        
        # Tab widget for different reports
        self.report_tabs = QTabWidget()
        
        # Report 1: Sales & Margin
        self.margin_table = QTableWidget()
        self.margin_table.setColumnCount(5)
        self.margin_table.setHorizontalHeaderLabels(["Product SKU", "Product Name", "Sales Count", "Gross Sales", "Est. Gross Profit"])
        self.margin_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.margin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_tabs.addTab(self.margin_table, "📈 Sales & Profitability")
        
        # Report 2: Category distribution
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(4)
        self.category_table.setHorizontalHeaderLabels(["Category", "Distinct Products", "Total Stock Units", "Total Asset Value (Cost)"])
        self.category_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_tabs.addTab(self.category_table, "📦 Category Distribution")
        
        # Report 3: Supplier distribution
        self.supplier_table = QTableWidget()
        self.supplier_table.setColumnCount(4)
        self.supplier_table.setHorizontalHeaderLabels(["Supplier Name", "Distinct Products", "Total Stock Units", "Total Asset Value (Cost)"])
        self.supplier_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.supplier_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_tabs.addTab(self.supplier_table, "🚚 Supplier Analysis")
        
        # Report 4: Receivables Aging
        self.aging_table = QTableWidget()
        self.aging_table.setColumnCount(4)
        self.aging_table.setHorizontalHeaderLabels(["Customer Profile", "Total Debits", "Total Payments", "Outstanding Balance"])
        self.aging_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.aging_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_tabs.addTab(self.aging_table, "⏳ Receivables Aging")
        
        layout.addWidget(self.report_tabs)
        self.setLayout(layout)
        self.refresh()
        
    def create_stat_card(self, title, value, color_style=None):
        frame = QFrame()
        frame.setObjectName("card")
        
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)
        
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        card_layout.addWidget(title_label)
        
        val_label = QLabel(value)
        val_label.setObjectName("cardValue")
        if color_style:
            val_label.setStyleSheet(color_style)
        card_layout.addWidget(val_label)
        
        frame.setLayout(card_layout)
        return frame
        
    def refresh(self):
        # Clear summary stats
        for i in reversed(range(self.summary_layout.count())):
            self.summary_layout.itemAt(i).widget().setParent(None)
            
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            # --- CALCULATE GENERAL METRICS ---
            # 1. Total sales revenue
            cursor.execute("SELECT SUM(total_amount) FROM invoices")
            revenue_res = cursor.fetchone()[0]
            revenue = revenue_res if revenue_res else 0.0
            
            # 2. Total cost of goods sold (COGS)
            cursor.execute("""
                SELECT SUM(invoices.quantity * inventory.purchase_price) 
                FROM invoices 
                LEFT JOIN inventory ON invoices.product_sku = inventory.sku
            """)
            cogs_res = cursor.fetchone()[0]
            cogs = cogs_res if cogs_res else 0.0
            
            # 3. Profit & Margin
            profit = revenue - cogs
            margin_pct = (profit / revenue * 100) if revenue > 0 else 0.0
            
            # Add Stat Cards
            self.summary_layout.addWidget(self.create_stat_card("Total Sales Revenue", f"${revenue:,.2f}"))
            self.summary_layout.addWidget(self.create_stat_card("Cost of Goods Sold (COGS)", f"${cogs:,.2f}"))
            
            profit_color = "font-size: 22px; font-weight: bold; color: #22c55e;" if profit >= 0 else "font-size: 22px; font-weight: bold; color: #ef4444;"
            self.summary_layout.addWidget(self.create_stat_card("Est. Gross Profit", f"${profit:,.2f}", profit_color))
            self.summary_layout.addWidget(self.create_stat_card("Gross Profit Margin", f"{margin_pct:.1f}%"))
            
            # --- POPULATE TABLE 1: Sales & Margin ---
            cursor.execute("""
                SELECT invoices.product_sku, inventory.product_name, SUM(invoices.quantity) as sales_qty, 
                       SUM(invoices.total_amount) as gross_sales,
                       SUM(invoices.total_amount - invoices.quantity * inventory.purchase_price) as gross_profit
                FROM invoices
                LEFT JOIN inventory ON invoices.product_sku = inventory.sku
                GROUP BY invoices.product_sku
                ORDER BY gross_sales DESC
            """)
            margin_rows = cursor.fetchall()
            self.margin_table.setRowCount(len(margin_rows))
            for row, r in enumerate(margin_rows):
                self.margin_table.setItem(row, 0, QTableWidgetItem(r['product_sku']))
                self.margin_table.setItem(row, 1, QTableWidgetItem(r['product_name'] or "Unknown product"))
                self.margin_table.setItem(row, 2, QTableWidgetItem(str(r['sales_qty'])))
                self.margin_table.setItem(row, 3, QTableWidgetItem(f"${r['gross_sales']:,.2f}"))
                gross_profit = r['gross_profit'] if r['gross_profit'] is not None else 0.0
                self.margin_table.setItem(row, 4, QTableWidgetItem(f"${gross_profit:,.2f}"))
                
            # --- POPULATE TABLE 2: Category Analytics ---
            cursor.execute("""
                SELECT category, COUNT(*) as product_count, SUM(quantity) as stock_units,
                       SUM(quantity * purchase_price) as asset_value
                FROM inventory
                GROUP BY category
                ORDER BY asset_value DESC
            """)
            cat_rows = cursor.fetchall()
            self.category_table.setRowCount(len(cat_rows))
            for row, r in enumerate(cat_rows):
                self.category_table.setItem(row, 0, QTableWidgetItem(r['category']))
                self.category_table.setItem(row, 1, QTableWidgetItem(str(r['product_count'])))
                self.category_table.setItem(row, 2, QTableWidgetItem(str(r['stock_units'] or 0)))
                self.category_table.setItem(row, 3, QTableWidgetItem(f"${r['asset_value'] or 0:,.2f}"))
                
            # --- POPULATE TABLE 3: Supplier Analysis ---
            cursor.execute("""
                SELECT suppliers.company_name, COUNT(inventory.id) as product_count, SUM(inventory.quantity) as stock_units,
                       SUM(inventory.quantity * inventory.purchase_price) as asset_value
                FROM suppliers
                LEFT JOIN inventory ON suppliers.id = inventory.supplier_id
                GROUP BY suppliers.id
                ORDER BY asset_value DESC
            """)
            sup_rows = cursor.fetchall()
            self.supplier_table.setRowCount(len(sup_rows))
            for row, r in enumerate(sup_rows):
                self.supplier_table.setItem(row, 0, QTableWidgetItem(r['company_name']))
                self.supplier_table.setItem(row, 1, QTableWidgetItem(str(r['product_count'])))
                self.supplier_table.setItem(row, 2, QTableWidgetItem(str(r['stock_units'] or 0)))
                self.supplier_table.setItem(row, 3, QTableWidgetItem(f"${r['asset_value'] or 0:,.2f}"))
                
            # --- POPULATE TABLE 4: Receivables Aging ---
            parties = self.db.get_unique_parties()
            self.aging_table.setRowCount(len(parties))
            for row, party in enumerate(parties):
                summary = self.db.get_ledger_summary(party)
                self.aging_table.setItem(row, 0, QTableWidgetItem(party))
                self.aging_table.setItem(row, 1, QTableWidgetItem(f"${summary['total_debit']:,.2f}"))
                self.aging_table.setItem(row, 2, QTableWidgetItem(f"${summary['total_credit']:,.2f}"))
                bal_item = QTableWidgetItem(f"${summary['balance']:,.2f}")
                if summary['balance'] > 0:
                    bal_item.setForeground(QBrush(QColor(239, 68, 68)))
                elif summary['balance'] < 0:
                    bal_item.setForeground(QBrush(QColor(34, 197, 94)))
                self.aging_table.setItem(row, 3, bal_item)
                
        except Exception as e:
            print(f"Reports refresh error: {e}")
        finally:
            conn.close()

# ==============================================================================
# INVOICE REGISTRY TAB (ADMIN ONLY)
# ==============================================================================

class InvoicesTab(QWidget):
    """Admin invoice records tab with search and printing options."""
    
    def __init__(self, db_manager, is_dark_mode_fn):
        super().__init__()
        self.db = db_manager
        self.is_dark_mode = is_dark_mode_fn
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Search controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter invoices:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by Customer Name...")
        self.search_input.textChanged.connect(self.populate_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Invoice ID", "Date", "Customer Name", "Total Items", "Grand Total"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.print_btn = QPushButton("🖨️ View & Print Selected Invoice")
        self.print_btn.clicked.connect(self.print_selected_invoice)
        btn_layout.addWidget(self.print_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.populate_table()
        
    def populate_table(self):
        self.table.setRowCount(0)
        invoices = self.db.get_grouped_invoices()
        query = self.search_input.text().strip().lower()
        
        filtered = []
        for inv in invoices:
            if not query or query in inv['party_name'].lower():
                filtered.append(inv)
                
        self.table.setRowCount(len(filtered))
        for row, inv in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(f"INV#{inv['invoice_id']}"))
            self.table.setItem(row, 1, QTableWidgetItem(inv['date']))
            self.table.setItem(row, 2, QTableWidgetItem(inv['party_name']))
            self.table.setItem(row, 3, QTableWidgetItem(str(inv['total_items'])))
            self.table.setItem(row, 4, QTableWidgetItem(f"${inv['grand_total']:,.2f}"))
            
    def print_selected_invoice(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an invoice from the table first.")
            return
            
        row = selected[0].row()
        inv_id_str = self.table.item(row, 0).text()
        try:
            inv_id = int(inv_id_str.replace("INV#", ""))
            items = self.db.get_invoice_by_item_id(inv_id)
            if not items:
                QMessageBox.warning(self, "Not Found", "Invoice details could not be found.")
                return
                
            party_name = items[0]['party_name']
            date = items[0]['date']
            
            html = generate_invoice_html(party_name, date, items)
            dialog = InvoicePrintDialog(html, f"invoice_{inv_id}.pdf", self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not print invoice: {str(e)}")

# ==============================================================================
# MAIN APPLICATION WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    """The central shell integrating tabs and managing theme toggles."""
    
    def __init__(self, db_manager, username, role):
        super().__init__()
        self.db = db_manager
        self.username = username
        self.role = role
        
        # State
        self.current_theme = "Dark" # Starts dark as default premium style
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Enterprise Ledger & Inventory Suite")
        self.setMinimumSize(1024, 768)
        
        # Central Widget & Root Layout
        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        
        # Top Header Bar
        header_frame = QFrame()
        header_frame.setObjectName("card")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 12, 16, 12)
        
        # Title branding
        brand = QLabel("👔 Enterprise Operations Ledger")
        brand.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(brand)
        
        header_layout.addStretch()
        
        # User details badge
        user_badge = QLabel(f"Connected: <b>{self.username}</b> ({self.role})")
        user_badge.setStyleSheet("margin-right: 16px;")
        header_layout.addWidget(user_badge)
        
        # Theme toggle button
        self.theme_btn = QPushButton("☀️ Light Mode")
        self.theme_btn.setObjectName("secondaryButton")
        self.theme_btn.setFixedWidth(120)
        self.theme_btn.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_btn)
        
        header_frame.setLayout(header_layout)
        root_layout.addWidget(header_frame)
        
        # Tabs system (RBAC gateway filtered)
        self.tabs = QTabWidget()
        
        # 1. Dashboard Tab
        self.dashboard_tab = DashboardTab(self.db, self.username, self.role, self.is_dark_mode)
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        
        if self.role == "Admin":
            # 2. Inventory Tab
            self.inventory_tab = InventoryTab(self.db, self.is_dark_mode, self.refresh_all_views)
            self.tabs.addTab(self.inventory_tab, "📦 Stock Catalog")
            
            # 3. Invoicing Tab
            self.invoicing_tab = InvoicingTab(self.db, self.is_dark_mode, self.refresh_all_views)
            self.tabs.addTab(self.invoicing_tab, "🧾 Cashier Invoicing")
            
            # 4. Invoice Registry Tab
            self.invoices_tab = InvoicesTab(self.db, self.is_dark_mode)
            self.tabs.addTab(self.invoices_tab, "📄 Invoice Registry")
            
            # 5. Suppliers Master Tab
            self.suppliers_tab = SuppliersTab(self.db, self.refresh_all_views)
            self.tabs.addTab(self.suppliers_tab, "🚚 Suppliers Master")
            
            # 6. Master Ledger Tab
            self.ledger_tab = LedgersTab(self.db, self.username, self.role)
            self.tabs.addTab(self.ledger_tab, "📖 Party Ledgers")
            
            # 7. Collections Tab
            self.collections_tab = CollectionsTab(self.db, self.refresh_all_views)
            self.tabs.addTab(self.collections_tab, "💰 Payments & Receipts")
            
            # 8. Reports & Analytics Tab
            self.reports_tab = ReportsTab(self.db)
            self.tabs.addTab(self.reports_tab, "📊 Reports & Analytics")
        else:
            # Client View Restrictions
            self.ledger_tab = LedgersTab(self.db, self.username, self.role)
            self.tabs.addTab(self.ledger_tab, "📖 Personal Balance Ledger")
            
        root_layout.addWidget(self.tabs)
        
        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)
        
        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"Session established. Welcome back, {self.username}!", 5000)
        
        # Set focus to barcode entry by default if Admin
        if self.role == "Admin":
            # Make sure scanner entry gets cursor default focus on app startup
            self.tabs.currentChanged.connect(self.on_tab_changed)
            # Start on the Invoicing tab immediately to show focus, or keep Dashboard but focus barcode once they visit.
            self.barcode_focus_timer()

    def barcode_focus_timer(self):
        # We start a small single-shot timer to let the widgets render fully before focusing
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.focus_barcode_input)

    def focus_barcode_input(self):
        if self.role == "Admin" and self.tabs.currentWidget() == self.invoicing_tab:
            self.invoicing_tab.barcode_input.setFocus()

    def on_tab_changed(self, index):
        if self.role == "Admin" and self.tabs.widget(index) == self.invoicing_tab:
            self.invoicing_tab.barcode_input.setFocus()
            
    def is_dark_mode(self):
        return self.current_theme == "Dark"

    def toggle_theme(self):
        app = QApplication.instance()
        if self.current_theme == "Dark":
            app.setStyleSheet(get_light_theme())
            self.current_theme = "Light"
            self.theme_btn.setText("🌙 Dark Mode")
        else:
            app.setStyleSheet(get_dark_theme())
            self.current_theme = "Dark"
            self.theme_btn.setText("☀️ Light Mode")
            
        # Re-render tables to apply new low stock highlight backgrounds appropriately
        self.refresh_all_views()

    def refresh_all_views(self):
        """Dispatches real-time update instructions across all modular subsystems."""
        self.dashboard_tab.refresh()
        
        if self.role == "Admin":
            self.inventory_tab.populate_views()
            self.invoicing_tab.sync_combos()
            self.invoices_tab.populate_table()
            self.suppliers_tab.populate_table()
            self.ledger_tab.sync_parties()
            self.collections_tab.sync_parties()
            self.reports_tab.refresh()
        else:
            self.ledger_tab.populate_ledger()
            
        self.status.showMessage("Real-time data synchronization complete.", 3000)

# ==============================================================================
# APPLICATION ENTRYPOINT
# ==============================================================================

def main():
    app = QApplication(sys.argv)
    
    # Establish dynamic database connection
    db = DatabaseManager()
    
    # Load premium Dark theme styling by default on launch
    app.setStyleSheet(get_dark_theme())
    
    # Launch initial Modal Login Gateway Dialog interrupting main window setup
    login = LoginDialog(db)
    if login.exec() == QDialog.DialogCode.Accepted:
        username, role = login.get_credentials()
        
        # Instantiate main window structure
        main_win = MainWindow(db, username, role)
        main_win.show()
        
        sys.exit(app.exec())
    else:
        # User canceled out or rejected gateway
        sys.exit(0)

if __name__ == "__main__":
    main()
