# Inventory, Billing, and Double-Entry Ledger Management System

A production-ready desktop application built with Python 3, PyQt6, and SQLite, featuring role-based access control, barcode scanner integration, and real-time inventory and financial ledger tracking.

## Features

- **Role-Based Access Control (RBAC):** Secure login gateway with distinct Admin and Client roles.
- **Inventory Management:** Track stock levels, categories, subcategories, and suppliers.
- **Real-Time Alerts:** Status banners and visual highlights for low-stock items.
- **Barcode Scanner Integration:** Automatic focus and transactional lookup.
- **Double-Entry Ledger:** Atomic financial transactions for billing, invoices, and cash collections.
- **Theme Support:** Premium light and dark mode stylesheets.
- **Printing:** Integrated invoice printing and preview capabilities.

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sas4211/inventorydesk.git
   cd inventorydesk
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate the Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   * **Windows (CMD):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   * **macOS/Linux:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install Dependencies:**
   ```bash
   pip install PyQt6
   ```

## Running the Application

To start the application, run:
```bash
python main.py
```

### Default Credentials
On initial startup, the database is auto-initialized and seeded with default accounts:
- **Admin Account:**
  - Username: `admin`
  - Password: `admin123`
- **Client Account:**
  - Username: `client`
  - Password: `client123`
