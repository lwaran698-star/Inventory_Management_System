import csv
import io
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# ---------------------------------------------------------------- Settings
# Deploy pannumbodhu SECRET_KEY environment variable set pannunga.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DATABASE = os.environ.get("DATABASE_PATH", "inventory.db")
LOW_STOCK_LIMIT = 5
PER_PAGE = 10
CATEGORIES = ["Electronics", "Groceries", "Clothing", "Accessories", "Other"]
SORT_COLUMNS = ["id", "name", "category", "price", "quantity"]


# ---------------------------------------------------------------- Database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_table():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,
            quantity INTEGER
        )
    """)

    # Pazhaya database-la irundha new columns add pannum (data poagaadhu)
    columns = [r["name"] for r in conn.execute("PRAGMA table_info(products)")]
    for col in ("created_at", "updated_at"):
        if col not in columns:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
        conn.execute(f"UPDATE products SET {col} = ? WHERE {col} IS NULL", (now(),))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            change INTEGER NOT NULL,
            old_qty INTEGER NOT NULL,
            new_qty INTEGER NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )

    conn.commit()
    conn.close()


def log_history(conn, product_id, name, old_qty, new_qty, reason):
    change = new_qty - old_qty
    if change == 0 and reason != "Product added":
        return
    conn.execute(
        """INSERT INTO stock_history
           (product_id, product_name, change, old_qty, new_qty, reason, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (product_id, name, change, old_qty, new_qty, reason, now()),
    )


def product_exists(conn, name, category, exclude_id=None):
    sql = "SELECT id FROM products WHERE LOWER(name) = LOWER(?) AND category = ?"
    params = [name, category]
    if exclude_id:
        sql += " AND id != ?"
        params.append(exclude_id)
    return conn.execute(sql, params).fetchone() is not None


def parse_product_form(form):
    """Returns (name, category, price, quantity, error_message)."""
    name = form.get("name", "").strip()
    category = form.get("category", "").strip()

    if not name:
        return None, None, None, None, "Product name is required."
    if category not in CATEGORIES:
        return None, None, None, None, "Please select a valid category."
    try:
        price = float(form.get("price", 0))
        quantity = int(form.get("quantity", 0))
    except ValueError:
        return None, None, None, None, "Please enter a valid price and quantity."
    if price < 0 or quantity < 0:
        return None, None, None, None, "Price and quantity cannot be negative."

    return name, category, price, quantity, None


def page_number(param="page"):
    try:
        return max(int(request.args.get(param, 1)), 1)
    except ValueError:
        return 1


def back_to(default_endpoint):
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref.split("#")[0] + "#products")
    return redirect(url_for(default_endpoint, _anchor="products"))


# ---------------------------------------------------------------- Auth
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = user["username"]
            return redirect(url_for("home"))

        flash("Wrong username or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (session["user"],)
        ).fetchone()

        error = None
        if user is None:
            error = "User not found. Please log in again."
        elif not check_password_hash(user["password_hash"], current_password):
            error = "Current password is wrong."
        elif len(new_username) < 3:
            error = "Username must be at least 3 characters."
        elif new_password and len(new_password) < 6:
            error = "New password must be at least 6 characters."
        elif new_password != confirm_password:
            error = "New password and confirm password do not match."
        elif conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (new_username, user["id"]),
        ).fetchone():
            error = "That username is already taken."

        if error:
            conn.close()
            flash(error, "error")
            return redirect(url_for("account"))

        password_hash = (generate_password_hash(new_password)
                         if new_password else user["password_hash"])
        conn.execute(
            "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
            (new_username, password_hash, user["id"]),
        )
        conn.commit()
        conn.close()

        session["user"] = new_username
        flash("Account updated successfully.", "success")
        return redirect(url_for("account"))

    return render_template("account.html")


# ---------------------------------------------------------------- Template helpers
@app.context_processor
def inject_globals():
    return {"low_limit": LOW_STOCK_LIMIT, "categories": CATEGORIES}


@app.template_global()
def page_url(param, number, anchor):
    args = request.args.to_dict()
    args[param] = number
    return url_for("home", _anchor=anchor, **args)


@app.template_global()
def sort_url(column):
    args = request.args.to_dict()
    current_sort = args.get("sort", "id")
    current_order = args.get("order", "desc")
    args["sort"] = column
    args["order"] = "desc" if (current_sort == column and current_order == "asc") else "asc"
    args.pop("page", None)
    return url_for("home", _anchor="products", **args)


@app.template_filter("inr")
def inr(value):
    return "{:,.2f}".format(value or 0)


# ---------------------------------------------------------------- Home (Dashboard + Products + History)
@app.route("/")
@login_required
def home():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "id")
    order = request.args.get("order", "desc")

    if sort not in SORT_COLUMNS:
        sort = "id"
    if order not in ("asc", "desc"):
        order = "desc"

    where, params = [], []
    if q:
        where.append("LOWER(name) LIKE ?")
        params.append(f"%{q.lower()}%")
    if category:
        where.append("category = ?")
        params.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_db_connection()

    # Dashboard cards + chart data
    stats = conn.execute(
        """SELECT COUNT(*) AS total_products,
                  COALESCE(SUM(quantity), 0) AS total_stock,
                  COALESCE(SUM(price * quantity), 0) AS total_value,
                  COALESCE(SUM(CASE WHEN quantity < ? THEN 1 ELSE 0 END), 0) AS low_stock
           FROM products""",
        (LOW_STOCK_LIMIT,),
    ).fetchone()

    category_stock = conn.execute(
        """SELECT category,
                  SUM(quantity) AS total_stock,
                  SUM(CASE WHEN quantity < ? THEN 1 ELSE 0 END) AS low_stock_products
           FROM products GROUP BY category ORDER BY category""",
        (LOW_STOCK_LIMIT,),
    ).fetchall()

    low_products = conn.execute(
        "SELECT * FROM products WHERE quantity < ? ORDER BY quantity ASC LIMIT 5",
        (LOW_STOCK_LIMIT,),
    ).fetchall()

    # Product list (search + filter + sort + pagination)
    total = conn.execute(f"SELECT COUNT(*) FROM products {where_sql}", params).fetchone()[0]
    pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    page = min(page_number("page"), pages)

    products = conn.execute(
        f"SELECT * FROM products {where_sql} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [PER_PAGE, (page - 1) * PER_PAGE],
    ).fetchall()

    # Stock history (pagination)
    h_total = conn.execute("SELECT COUNT(*) FROM stock_history").fetchone()[0]
    h_pages = max((h_total + PER_PAGE - 1) // PER_PAGE, 1)
    h_page = min(page_number("hpage"), h_pages)

    history_rows = conn.execute(
        "SELECT * FROM stock_history ORDER BY id DESC LIMIT ? OFFSET ?",
        (PER_PAGE, (h_page - 1) * PER_PAGE),
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        stats=stats,
        category_stock=[dict(r) for r in category_stock],
        low_products=low_products,
        products=products, total=total, page=page, pages=pages,
        q=q, selected_category=category, sort=sort, order=order,
        history_rows=history_rows, h_total=h_total, h_page=h_page, h_pages=h_pages,
    )


@app.route("/add", methods=["POST"])
@login_required
def add_product():
    name, category, price, quantity, error = parse_product_form(request.form)
    if error:
        flash(error, "error")
        return redirect(url_for("home", _anchor="products"))

    conn = get_db_connection()

    if product_exists(conn, name, category):
        conn.close()
        flash(f"'{name}' already exists in {category}. Edit it or use Stock In instead.", "error")
        return redirect(url_for("home", _anchor="products"))

    cur = conn.execute(
        """INSERT INTO products (name, category, price, quantity, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, category, price, quantity, now(), now()),
    )
    log_history(conn, cur.lastrowid, name, 0, quantity, "Product added")
    conn.commit()
    conn.close()

    flash(f"Product '{name}' added successfully.", "success")
    return redirect(url_for("home", _anchor="products"))


@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("home", _anchor="products"))

    if request.method == "POST":
        name, category, price, quantity, error = parse_product_form(request.form)

        if not error and product_exists(conn, name, category, exclude_id=product_id):
            error = f"Another product named '{name}' already exists in {category}."

        if error:
            conn.close()
            flash(error, "error")
            return redirect(url_for("edit_product", product_id=product_id))

        conn.execute(
            """UPDATE products
               SET name = ?, category = ?, price = ?, quantity = ?, updated_at = ?
               WHERE id = ?""",
            (name, category, price, quantity, now(), product_id),
        )
        log_history(conn, product_id, name, product["quantity"], quantity, "Manual edit")
        conn.commit()
        conn.close()

        flash(f"Product '{name}' updated successfully.", "success")
        return redirect(url_for("home", _anchor="products"))

    conn.close()
    return render_template("edit.html", product=product)


@app.route("/delete/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if product:
        log_history(conn, product_id, product["name"], product["quantity"], 0, "Product deleted")
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        flash(f"Product '{product['name']}' deleted.", "success")

    conn.close()
    return back_to("home")


@app.route("/stock/<int:product_id>", methods=["POST"])
@login_required
def adjust_stock(product_id):
    action = request.form.get("action")
    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if action not in ("in", "out") or amount <= 0:
        flash("Enter a quantity greater than 0.", "error")
        return back_to("home")

    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.", "error")
        return back_to("home")

    old_qty = product["quantity"]
    new_qty = old_qty + amount if action == "in" else old_qty - amount

    if new_qty < 0:
        conn.close()
        flash(f"Only {old_qty} units of '{product['name']}' in stock.", "error")
        return back_to("home")

    conn.execute(
        "UPDATE products SET quantity = ?, updated_at = ? WHERE id = ?",
        (new_qty, now(), product_id),
    )
    log_history(conn, product_id, product["name"], old_qty, new_qty,
                "Stock in" if action == "in" else "Stock out")
    conn.commit()
    conn.close()

    label = "added to" if action == "in" else "removed from"
    flash(f"{amount} units {label} '{product['name']}'. Now {new_qty} in stock.", "success")
    return back_to("home")


# ---------------------------------------------------------------- CSV export / import
@app.route("/export")
@login_required
def export_csv():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, name, category, price, quantity FROM products ORDER BY id"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Product Name", "Category", "Price (INR)", "Quantity", "Stock Status"])

    for p in rows:
        status = "Low Stock" if p["quantity"] < LOW_STOCK_LIMIT else "In Stock"
        writer.writerow([p["id"], p["name"], p["category"], p["price"], p["quantity"], status])

    filename = f"inventory_{datetime.now().strftime('%Y-%m-%d')}.csv"

    # utf-8-sig: Excel-la special characters correct-ah theriyum
    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/import", methods=["POST"])
@login_required
def import_csv():
    file = request.files.get("csv_file")

    if not file or not file.filename.lower().endswith(".csv"):
        flash("Please select a valid .csv file.", "error")
        return redirect(url_for("home", _anchor="products"))

    try:
        content = file.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Could not read the file. Save it as UTF-8 CSV.", "error")
        return redirect(url_for("home", _anchor="products"))

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        flash("The CSV file is empty.", "error")
        return redirect(url_for("home", _anchor="products"))

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}

    def find_column(*names):
        for n in names:
            if n in headers:
                return headers[n]
        return None

    name_col = find_column("product name", "name")
    category_col = find_column("category")
    price_col = find_column("price (inr)", "price (₹)", "price")
    quantity_col = find_column("quantity", "qty")

    if not (name_col and price_col and quantity_col):
        flash("CSV must have Product Name, Price and Quantity columns.", "error")
        return redirect(url_for("home", _anchor="products"))

    conn = get_db_connection()
    added = skipped = duplicates = 0

    for row in reader:
        name = (row.get(name_col) or "").strip()
        category = (row.get(category_col) or "").strip() if category_col else ""

        try:
            price = float(row.get(price_col) or 0)
            quantity = int(float(row.get(quantity_col) or 0))
        except ValueError:
            skipped += 1
            continue

        if not name or price < 0 or quantity < 0:
            skipped += 1
            continue

        if category not in CATEGORIES:
            category = "Other"

        if product_exists(conn, name, category):
            duplicates += 1
            continue

        cur = conn.execute(
            """INSERT INTO products (name, category, price, quantity, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, category, price, quantity, now(), now()),
        )
        log_history(conn, cur.lastrowid, name, 0, quantity, "CSV import")
        added += 1

    conn.commit()
    conn.close()

    flash(f"Import finished: {added} added, {duplicates} duplicates skipped, {skipped} invalid rows skipped.", "success")
    return redirect(url_for("home", _anchor="products"))


# ---------------------------------------------------------------- PDF report
@app.route("/report")
@login_required
def report_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                        Table, TableStyle)
    except ImportError:
        flash("PDF library missing. Run: pip install reportlab", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    conn.close()

    total_stock = sum(r["quantity"] for r in rows)
    total_value = sum(r["price"] * r["quantity"] for r in rows)
    low_count = sum(1 for r in rows if r["quantity"] < LOW_STOCK_LIMIT)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Inventory Report",
                            leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Inventory Report", styles["Title"]),
        Paragraph(f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}", styles["Normal"]),
        Spacer(1, 14),
    ]

    summary = Table(
        [["Total products", "Total stock", "Low stock", "Inventory value"],
         [str(len(rows)), str(total_stock), str(low_count), f"Rs. {total_value:,.2f}"]],
        colWidths=[130, 130, 130, 135],
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10302f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d6d0")),
    ]))
    story += [summary, Spacer(1, 18)]

    data = [["#", "Product", "Category", "Price (Rs.)", "Qty", "Status"]]
    low_rows = []
    for i, r in enumerate(rows, start=1):
        low = r["quantity"] < LOW_STOCK_LIMIT
        if low:
            low_rows.append(i)
        data.append([str(i), r["name"], r["category"], f"{r['price']:,.2f}",
                     str(r["quantity"]), "Low Stock" if low else "In Stock"])

    table = Table(data, repeatRows=1, colWidths=[28, 190, 90, 80, 45, 70])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10302f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (3, 0), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d6d0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f4")]),
    ]
    for i in low_rows:
        style += [("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#c0303b")),
                  ("FONTNAME", (5, i), (5, i), "Helvetica-Bold")]
    table.setStyle(TableStyle(style))
    story.append(table)

    doc.build(story)

    filename = f"inventory_report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# Gunicorn (deploy) and python app.py rendulayum database ready aagum
create_table()

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0")