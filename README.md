# StockPilot: Inventory Management System

A secure, responsive web application that helps small shops and warehouses track products, monitor stock levels, and generate reports. Built with Python, Flask, and SQLite.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

Small businesses often track stock in notebooks or spreadsheets, which leads to missed reorders, stock-outs, and no record of what changed. StockPilot replaces that with a single web app: owners can manage products, record every stock movement, see low-stock alerts at a glance, and export data and reports in seconds.

## Features

**Dashboard**
- Total inventory value, product count, available stock, and low-stock count
- Category-wise stock bar chart and stock health doughnut chart
- "Needs restocking" list for the lowest-stock products

**Product management**
- Add, edit, and delete products with server-side validation
- Duplicate detection (same name and category)
- Search by name, filter by category, sortable columns, and pagination

**Stock tracking**
- One-click Stock In / Stock Out, with protection against negative stock
- Complete stock history: date, product, reason, change, quantity before and after

**Data and reports**
- CSV export (Excel-friendly) and CSV import with validation and a result summary
- One-click PDF inventory report

**Security and usability**
- Login with hashed passwords and session handling
- Account page to change username and password
- Show / hide password toggle
- Responsive layout for desktop and mobile
- Toast notifications for every action

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Jinja2 |
| Database | SQLite |
| Frontend | HTML5, CSS3, JavaScript |
| Charts | Chart.js |
| PDF reports | ReportLab |
| Security | Werkzeug password hashing |
| Deployment | Gunicorn, PythonAnywhere |

## Screenshots

| Dashboard | Login |
|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Login](screenshots/login.png) |

## Getting Started

### Prerequisites
- Python 3.9 or newer
- pip

### Installation

```bash
git clone https://github.com/<your-username>/inventory-management-system.git
cd inventory-management-system
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

### Default login

| Username | Password |
|---|---|
| admin | admin123 |

Change these immediately from the **Account** page, or set the environment variables below before the first run.

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs login sessions | development key |
| `ADMIN_USERNAME` | First admin username | `admin` |
| `ADMIN_PASSWORD` | First admin password | `admin123` |
| `DATABASE_PATH` | Path of the SQLite file | `inventory.db` |

## Project Structure

```
inventory-management-system/
├── app.py              # Flask routes, database logic, PDF and CSV handling
├── requirements.txt    # Python dependencies
├── templates/
│   ├── index.html      # Dashboard, products, stock history
│   ├── edit.html       # Edit product
│   ├── account.html    # Change username / password
│   └── login.html      # Login page
└── README.md
```

## Database

| Table | Purpose |
|---|---|
| `products` | Product details, price, quantity, timestamps |
| `stock_history` | Audit log of every stock change |
| `users` | Login accounts with hashed passwords |

Tables are created automatically on first run.

## Security Notes

- Passwords are hashed, never stored in plain text
- All database queries are parameterised to prevent SQL injection
- Sort columns are checked against an allow-list
- Destructive actions use POST requests
- The database file is excluded from version control

## Deployment

The app runs on any WSGI host. For a free option, deploy to PythonAnywhere:

1. Clone the repository in a Bash console and install `requirements.txt` in a virtualenv
2. Create a manual-configuration Flask web app and point the WSGI file to `from app import app as application`
3. Set `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `DATABASE_PATH`
4. Reload the web app

## Roadmap

- Role-based access (admin, staff, viewer)
- Billing and sales module with invoice printing
- Supplier and purchase-order management
- Barcode / QR code support
- Email alerts for low stock
- REST API

## Author
[GOWTHAM M]
GitHub: [lwaran698@gmail.com](https://github.com/lwaran698)
