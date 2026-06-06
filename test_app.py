#!/usr/bin/env python3
"""
Unit/Integration Tests for Inventory, Billing, and Double-entry Ledger Management System.
Verifies DB schemas, business logic transactions, constraints, and double-entry ledger calculations.
"""

import os
import unittest
import sqlite3
from main import DatabaseManager

class TestBusinessLogic(unittest.TestCase):
    
    _counter = 0

    def setUp(self):
        TestBusinessLogic._counter += 1
        self.test_db_path = f"test_business_{TestBusinessLogic._counter}.db"
        try:
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception:
            pass
        self.db = DatabaseManager(self.test_db_path)

    def tearDown(self):
        # Clean up files silently; ignore locking errors since Windows delays release
        try:
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception:
            pass

    def test_database_initialization(self):
        """Test that database tables exist and default seed data is present."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check users
            cursor.execute("SELECT COUNT(*) FROM users")
            self.assertEqual(cursor.fetchone()[0], 2)
            
            # Check inventory items seeded
            cursor.execute("SELECT COUNT(*) FROM inventory")
            self.assertEqual(cursor.fetchone()[0], 5)
            
            # Check ledgers seeded (Opening balance for client)
            cursor.execute("SELECT COUNT(*) FROM ledgers")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_authentication(self):
        """Test role-based authentication credentials lookup."""
        self.assertEqual(self.db.authenticate("admin", "admin123"), "Admin")
        self.assertEqual(self.db.authenticate("client", "client123"), "Client")
        self.assertIsNone(self.db.authenticate("admin", "wrongpassword"))
        self.assertIsNone(self.db.authenticate("nonexistent", "client123"))

    def test_inventory_crud(self):
        """Test adding, updating, and deleting items in the inventory table."""
        # Add new item
        self.db.add_inventory_item("Test Keyboard", "KEY-123", 10, 25.0, 45.0)
        item = self.db.get_inventory_item("KEY-123")
        self.assertIsNotNone(item)
        self.assertEqual(item['product_name'], "Test Keyboard")
        self.assertEqual(item['quantity'], 10)
        
        # Update item
        self.db.update_inventory_item(item['id'], "Updated Keyboard", "KEY-123", 8, 26.0, 48.0)
        updated_item = self.db.get_inventory_item("KEY-123")
        self.assertEqual(updated_item['product_name'], "Updated Keyboard")
        self.assertEqual(updated_item['quantity'], 8)
        self.assertEqual(updated_item['selling_price'], 48.0)
        
        # Delete item
        self.db.delete_inventory_item(item['id'])
        deleted_item = self.db.get_inventory_item("KEY-123")
        self.assertIsNone(deleted_item)

    def test_atomic_invoice_checkout_transaction(self):
        """Test invoice checkout reduces inventory stock and adds ledger debit entries."""
        # Item: NVIDIA RTX 4070 Ti GPU, SKU: 471120, Qty: 3, Selling Price: 799.99
        sku = "471120"
        party = "client"
        
        # 1. Test checkout exceeding inventory levels must fail
        cart_items_exceed = [(sku, 5, "1 Year Warranty")] # Only 3 available
        success, error = self.db.create_invoice_cart_transaction(party, cart_items_exceed)
        self.assertFalse(success)
        self.assertIn("Insufficient stock", error)
        
        # Stock should remain unchanged (3)
        item = self.db.get_inventory_item(sku)
        self.assertEqual(item['quantity'], 3)
        
        # 2. Test successful checkout (Qty: 2)
        cart_items_ok = [(sku, 2, "1 Year Warranty")]
        success, error = self.db.create_invoice_cart_transaction(party, cart_items_ok)
        self.assertTrue(success)
        self.assertIsNone(error)
        
        # Verify stock decremented (3 - 2 = 1)
        item = self.db.get_inventory_item(sku)
        self.assertEqual(item['quantity'], 1)
        
        # Verify invoice is inserted
        invoices = self.db.get_invoices(party)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0]['product_sku'], sku)
        self.assertEqual(invoices[0]['quantity'], 2)
        self.assertEqual(invoices[0]['total_amount'], 2 * 799.99)
        
        # Verify ledger debit entry (+ outstanding receivable)
        ledgers = self.db.get_ledgers(party)
        # We had 1 seed entry (Opening Balance Deposit: credit = 500)
        # Now we should have 2 entries (debit = 1599.98)
        self.assertEqual(len(ledgers), 2)
        self.assertEqual(ledgers[1]['debit'], 1599.98)
        self.assertEqual(ledgers[1]['credit'], 0.0)
        
        # Calculate balance: Debit (1599.98) - Credit (500) = 1099.98
        summary = self.db.get_ledger_summary(party)
        self.assertAlmostEqual(summary['balance'], 1099.98, places=2)

    def test_manual_collection_transaction(self):
        """Test posting cash collections adds ledger credit and decreases outstanding balance."""
        party = "client"
        
        # Starting: 500.0 credit seeded
        summary_start = self.db.get_ledger_summary(party)
        self.assertEqual(summary_start['balance'], -500.0) # Client has a credit balance (we owe them)
        
        # Post credit collection (client pays us cash / reduces outstanding receivables)
        success, error = self.db.create_collection_transaction(party, 200.0, "Manual Cash Receipt")
        self.assertTrue(success)
        
        # Total Credits: 500 + 200 = 700.0. Balance: 0 - 700 = -700.0
        summary_end = self.db.get_ledger_summary(party)
        self.assertEqual(summary_end['total_credit'], 700.0)
        self.assertEqual(summary_end['balance'], -700.0)

if __name__ == "__main__":
    unittest.main()
