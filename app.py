from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "jewel_vogue_secret_2026"

DB_NAME = "jewel_vogue.db"


# =========================
# DATABASE
# =========================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    admin = cur.execute("SELECT * FROM admin LIMIT 1").fetchone()

    if not admin:
        cur.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    product_count = cur.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if product_count == 0:
        products = [
            ("Classic Black T-Shirt", 1499, "Premium cotton black T-shirt"),
            ("White Premium T-Shirt", 1599, "Comfortable premium white T-shirt"),
            ("Oversized Streetwear", 1999, "Modern oversized streetwear T-shirt"),
            ("Graphic Printed T-Shirt", 1799, "Stylish graphic printed T-shirt"),
            ("Classic Navy T-Shirt", 1499, "Simple and comfortable navy T-shirt"),
            ("Premium Polo Shirt", 2299, "Elegant premium polo shirt")
        ]

        cur.executemany(
            "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
            products
        )

    conn.commit()
    conn.close()


# =========================
# ADMIN LOGIN
# =========================

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin"))
        return func(*args, **kwargs)

    return wrapper


# =========================
# CSS
# =========================

CSS = """
<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f7f7f7;
    color: #222;
}

nav {
    background: #111;
    padding: 18px 7%;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logo {
    color: white;
    font-size: 25px;
    font-weight: bold;
    letter-spacing: 2px;
}

nav a {
    color: white;
    text-decoration: none;
    margin-left: 22px;
    font-size: 15px;
}

nav a:hover {
    color: #d4af37;
}

.container {
    width: 86%;
    max-width: 1200px;
    margin: 40px auto;
}

.hero {
    background: #111;
    color: white;
    padding: 80px 30px;
    text-align: center;
}

.hero h1 {
    font-size: 52px;
    margin: 0 0 15px;
    letter-spacing: 4px;
}

.hero p {
    font-size: 19px;
    color: #ddd;
}

.btn {
    display: inline-block;
    padding: 11px 18px;
    background: #111;
    color: white;
    border: none;
    border-radius: 5px;
    text-decoration: none;
    cursor: pointer;
    margin: 4px;
}

.btn:hover {
    background: #333;
}

.gold {
    background: #b08d22;
}

.gold:hover {
    background: #8f731c;
}

.danger {
    background: #c0392b;
}

.success {
    background: #218838;
}

.products {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 22px;
}

.card {
    background: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.08);
}

.card h3 {
    margin-top: 0;
}

.price {
    font-size: 21px;
    font-weight: bold;
    margin: 12px 0;
}

input, textarea, select {
    width: 100%;
    padding: 12px;
    margin: 7px 0 15px;
    border: 1px solid #ccc;
    border-radius: 5px;
    font-size: 15px;
}

label {
    font-weight: bold;
}

table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}

th, td {
    padding: 13px;
    border-bottom: 1px solid #ddd;
    text-align: left;
}

th {
    background: #111;
    color: white;
}

.message {
    background: #e8f5e9;
    padding: 15px;
    border-radius: 6px;
    margin-bottom: 20px;
}

.error {
    background: #ffebee;
    padding: 15px;
    border-radius: 6px;
    margin-bottom: 20px;
}

footer {
    background: #111;
    color: white;
    text-align: center;
    padding: 25px;
    margin-top: 50px;
}

@media(max-width: 700px) {
    nav {
        flex-direction: column;
        gap: 15px;
    }

    nav a {
        margin: 5px;
    }

    .hero h1 {
        font-size: 35px;
    }

    table {
        font-size: 13px;
    }
}

</style>
"""


# =========================
# NAVBAR
# =========================

NAV = """
<nav>
    <div class="logo">JEWEL VOGUE</div>

    <div>
        <a href="/">Home</a>
        <a href="/products">Shop</a>
        <a href="/cart">Cart 🛒</a>
        <a href="/admin">Admin</a>
    </div>
</nav>
"""


# =========================
# HOME
# =========================

@app.route("/")
def home():

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <section class="hero">

        <h1>JEWEL VOGUE</h1>

        <p>
            Fashion that speaks for you.
        </p>

        <a class="btn gold" href="/products">
            Shop Now
        </a>

    </section>

    <div class="container">

        <h2>Welcome to JEWEL VOGUE</h2>

        <p>
            Discover stylish and comfortable fashion made for everyday life.
        </p>

    </div>

    <footer>
        © 2026 JEWEL VOGUE
    </footer>

    </body>
    </html>
    """, css=CSS, nav=NAV)


# =========================
# PRODUCTS
# =========================

@app.route("/products")
def products():

    conn = get_db()
    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shop - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <h1>Our Collection</h1>

        <div class="products">

        {% for product in products %}

            <div class="card">

                <h3>{{ product["name"] }}</h3>

                <p>{{ product["description"] }}</p>

                <div class="price">
                    Rs. {{ "%.2f"|format(product["price"]) }}
                </div>

                <a class="btn gold"
                   href="/add_to_cart/{{ product['id'] }}">
                   Add to Cart
                </a>

            </div>

        {% endfor %}

        </div>

    </div>

    <footer>
        © 2026 JEWEL VOGUE
    </footer>

    </body>
    </html>
    """, css=CSS, nav=NAV, products=products)


# =========================
# ADD TO CART
# =========================

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id=?",
        (product_id,)
    ).fetchone()

    conn.close()

    if not product:
        return redirect(url_for("products"))

    cart = session.get("cart", {})

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] += 1
    else:
        cart[product_id] = 1

    session["cart"] = cart

    return redirect(url_for("cart"))


# =========================
# CART
# =========================

@app.route("/cart")
def cart():

    cart = session.get("cart", {})

    items = []
    total = 0

    conn = get_db()

    for product_id, quantity in cart.items():

        product = conn.execute(
            "SELECT * FROM products WHERE id=?",
            (product_id,)
        ).fetchone()

        if product:

            subtotal = product["price"] * quantity

            items.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

            total += subtotal

    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cart - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <h1>Your Cart</h1>

        {% if items %}

        <table>

            <tr>
                <th>Product</th>
                <th>Price</th>
                <th>Quantity</th>
                <th>Subtotal</th>
                <th>Action</th>
            </tr>

            {% for item in items %}

            <tr>

                <td>{{ item.name }}</td>

                <td>Rs. {{ "%.2f"|format(item.price) }}</td>

                <td>
                    <a class="btn" href="/decrease/{{ item.id }}">−</a>
                    {{ item.quantity }}
                    <a class="btn" href="/increase/{{ item.id }}">+</a>
                </td>

                <td>
                    Rs. {{ "%.2f"|format(item.subtotal) }}
                </td>

                <td>
                    <a class="btn danger"
                       href="/remove/{{ item.id }}">
                       Remove
                    </a>
                </td>

            </tr>

            {% endfor %}

        </table>

        <h2>
            Total: Rs. {{ "%.2f"|format(total) }}
        </h2>

        <a class="btn gold" href="/checkout">
            Proceed to Checkout
        </a>

        {% else %}

        <p>Your cart is empty.</p>

        <a class="btn gold" href="/products">
            Continue Shopping
        </a>

        {% endif %}

    </div>

    <footer>
        © 2026 JEWEL VOGUE
    </footer>

    </body>
    </html>
    """, css=CSS, nav=NAV, items=items, total=total)


# =========================
# INCREASE
# =========================

@app.route("/increase/<int:product_id>")
def increase(product_id):

    cart = session.get("cart", {})

    key = str(product_id)

    if key in cart:
        cart[key] += 1

    session["cart"] = cart

    return redirect(url_for("cart"))


# =========================
# DECREASE
# =========================

@app.route("/decrease/<int:product_id>")
def decrease(product_id):

    cart = session.get("cart", {})

    key = str(product_id)

    if key in cart:

        cart[key] -= 1

        if cart[key] <= 0:
            del cart[key]

    session["cart"] = cart

    return redirect(url_for("cart"))


# =========================
# REMOVE
# =========================

@app.route("/remove/<int:product_id>")
def remove(product_id):

    cart = session.get("cart", {})

    key = str(product_id)

    if key in cart:
        del cart[key]

    session["cart"] = cart

    return redirect(url_for("cart"))


# =========================
# CHECKOUT
# =========================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("products"))

    conn = get_db()

    items = []
    total = 0

    for product_id, quantity in cart.items():

        product = conn.execute(
            "SELECT * FROM products WHERE id=?",
            (product_id,)
        ).fetchone()

        if product:

            subtotal = product["price"] * quantity

            items.append({
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

            total += subtotal

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        payment = request.form["payment"]

        if not name or not email or not phone or not address:
            conn.close()

            return render_template_string("""
            {{ css|safe }}
            {{ nav|safe }}

            <div class="container">

                <div class="error">
                    Please fill all required fields.
                </div>

                <a href="/checkout" class="btn">
                    Go Back
                </a>

            </div>
            """, css=CSS, nav=NAV)

        cur = conn.cursor()

        cur.execute("""
            INSERT INTO orders
            (customer_name, email, phone, address,
             payment_method, total, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            phone,
            address,
            payment,
            total,
            "Pending"
        ))

        order_id = cur.lastrowid

        for item in items:

            cur.execute("""
                INSERT INTO order_items
                (order_id, product_name, price, quantity)
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                item["name"],
                item["price"],
                item["quantity"]
            ))

        conn.commit()
        conn.close()

        session["cart"] = {}

        return render_template_string("""
        <!DOCTYPE html>
        <html>

        <head>
            <title>Order Confirmed - JEWEL VOGUE</title>
            {{ css|safe }}
        </head>

        <body>

        {{ nav|safe }}

        <div class="container">

            <div class="message">

                <h1>Order Confirmed!</h1>

                <p>
                    Thank you for shopping with JEWEL VOGUE.
                </p>

                <p>
                    Your Order ID is:
                    <strong>#{{ order_id }}</strong>
                </p>

            </div>

            <a class="btn gold" href="/products">
                Continue Shopping
            </a>

        </div>

        <footer>
            © 2026 JEWEL VOGUE
        </footer>

        </body>
        </html>
        """, css=CSS, nav=NAV, order_id=order_id)

    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>

    <head>
        <title>Checkout - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <h1>Checkout</h1>

        <h2>
            Total: Rs. {{ "%.2f"|format(total) }}
        </h2>

        <form method="POST">

            <label>Full Name</label>
            <input type="text" name="name" required>

            <label>Email Address</label>
            <input type="email" name="email" required>

            <label>Phone Number</label>
            <input type="text" name="phone" required>

            <label>Delivery Address</label>
            <textarea name="address" rows="4" required></textarea>

            <label>Payment Method</label>

            <select name="payment" required>

                <option value="Cash on Delivery">
                    Cash on Delivery
                </option>

                <option value="Bank Transfer">
                    Bank Transfer
                </option>

                <option value="Easypaisa">
                    Easypaisa
                </option>

                <option value="JazzCash">
                    JazzCash
                </option>

            </select>

            <button class="btn gold" type="submit">
                Place Order
            </button>

        </form>

    </div>

    <footer>
        © 2026 JEWEL VOGUE
    </footer>

    </body>
    </html>
    """, css=CSS, nav=NAV, items=items, total=total)


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin", methods=["GET", "POST"])
def admin():

    error = ""

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        admin_user = conn.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

        conn.close()

        if admin_user:

            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(url_for("admin_dashboard"))

        error = "Invalid username or password."

    return render_template_string("""
    <!DOCTYPE html>
    <html>

    <head>
        <title>Admin Login - JEWEL VOGUE</title>
        {{ css|safe }}

        <script>
        function showPassword() {

            var password =
                document.getElementById("password");

            if (password.type === "password") {
                password.type = "text";
            } else {
                password.type = "password";
            }
        }
        </script>

    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <div class="card">

            <h1>Admin Login</h1>

            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}

            <form method="POST">

                <label>Username</label>

                <input
                    type="text"
                    name="username"
                    required
                >

                <label>Password</label>

                <input
                    id="password"
                    type="password"
                    name="password"
                    required
                >

                <label>
                    <input
                        type="checkbox"
                        onclick="showPassword()"
                        style="width:auto;"
                    >
                    Show Password
                </label>

                <br><br>

                <button class="btn gold" type="submit">
                    Login
                </button>

            </form>

        </div>

    </div>

    </body>
    </html>
    """, css=CSS, nav=NAV, error=error)


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = get_db()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    orders = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>

    <head>
        <title>Admin Dashboard - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <h1>Admin Dashboard</h1>

        <p>
            Welcome,
            <strong>{{ username }}</strong>
        </p>

        <a class="btn gold"
           href="/admin/add_product">
           Add Product
        </a>

        <a class="btn"
           href="/admin/change-password">
           Change Password
        </a>

        <a class="btn danger"
           href="/admin/logout">
           Logout
        </a>

        <h2>Products</h2>

        <table>

            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Price</th>
                <th>Action</th>
            </tr>

            {% for product in products %}

            <tr>

                <td>{{ product.id }}</td>

                <td>{{ product.name }}</td>

                <td>
                    Rs. {{ "%.2f"|format(product.price) }}
                </td>

                <td>

                    <a
                        class="btn danger"
                        href="/admin/delete_product/{{ product.id }}"
                        onclick="return confirm('Delete this product?')"
                    >
                        Delete
                    </a>

                </td>

            </tr>

            {% endfor %}

        </table>


        <h2>Orders</h2>

        <table>

            <tr>
                <th>ID</th>
                <th>Customer</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Payment</th>
                <th>Total</th>
                <th>Status</th>
            </tr>

            {% for order in orders %}

            <tr>

                <td>#{{ order.id }}</td>

                <td>{{ order.customer_name }}</td>

                <td>{{ order.email }}</td>

                <td>{{ order.phone }}</td>

                <td>{{ order.payment_method }}</td>

                <td>
                    Rs. {{ "%.2f"|format(order.total) }}
                </td>

                <td>

                    <form
                        method="POST"
                        action="/admin/update_status/{{ order.id }}"
                    >

                        <select name="status">

                            <option
                                value="Pending"
                                {% if order.status == "Pending" %}
                                selected
                                {% endif %}
                            >
                                Pending
                            </option>

                            <option
                                value="Processing"
                                {% if order.status == "Processing" %}
                                selected
                                {% endif %}
                            >
                                Processing
                            </option>

                            <option
                                value="Shipped"
                                {% if order.status == "Shipped" %}
                                selected
                                {% endif %}
                            >
                                Shipped
                            </option>

                            <option
                                value="Delivered"
                                {% if order.status == "Delivered" %}
                                selected
                                {% endif %}
                            >
                                Delivered
                            </option>

                            <option
                                value="Cancelled"
                                {% if order.status == "Cancelled" %}
                                selected
                                {% endif %}
                            >
                                Cancelled
                            </option>

                        </select>

                        <button class="btn" type="submit">
                            Update
                        </button>

                    </form>

                </td>

            </tr>

            {% endfor %}

        </table>

    </div>

    <footer>
        © 2026 JEWEL VOGUE
    </footer>

    </body>
    </html>
    """,
    css=CSS,
    nav=NAV,
    products=products,
    orders=orders,
    username=session.get("admin_username")
    )


# =========================
# ADD PRODUCT
# =========================

@app.route("/admin/add_product", methods=["GET", "POST"])
@admin_required
def add_product():

    if request.method == "POST":

        name = request.form["name"]
        price = float(request.form["price"])
        description = request.form["description"]

        conn = get_db()

        conn.execute("""
            INSERT INTO products
            (name, price, description)
            VALUES (?, ?, ?)
        """, (name, price, description))

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    return render_template_string("""
    <!DOCTYPE html>
    <html>

    <head>
        <title>Add Product - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <div class="card">

            <h1>Add Product</h1>

            <form method="POST">

                <label>Product Name</label>
                <input type="text" name="name" required>

                <label>Price</label>
                <input
                    type="number"
                    name="price"
                    step="0.01"
                    required
                >

                <label>Description</label>

                <textarea
                    name="description"
                    rows="5"
                ></textarea>

                <button class="btn gold" type="submit">
                    Add Product
                </button>

            </form>

        </div>

    </div>

    </body>
    </html>
    """, css=CSS, nav=NAV)


# =========================
# DELETE PRODUCT
# =========================

@app.route("/admin/delete_product/<int:product_id>")
@admin_required
def delete_product(product_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM products WHERE id=?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# =========================
# UPDATE ORDER STATUS
# =========================

@app.route("/admin/update_status/<int:order_id>", methods=["POST"])
@admin_required
def update_status(order_id):

    status = request.form["status"]

    conn = get_db()

    conn.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (status, order_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# =========================
# CHANGE ADMIN PASSWORD
# =========================

@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def change_password():

    message = ""
    error = ""

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        conn = get_db()

        admin_user = conn.execute(
            "SELECT * FROM admin WHERE username=?",
            (session.get("admin_username"),)
        ).fetchone()

        if not admin_user:
            conn.close()
            error = "Admin account not found."

        elif admin_user["password"] != current_password:
            conn.close()
            error = "Current password is incorrect."

        elif len(new_password) < 6:
            conn.close()
            error = "New password must be at least 6 characters."

        elif new_password != confirm_password:
            conn.close()
            error = "New passwords do not match."

        elif new_password == current_password:
            conn.close()
            error = "New password must be different."

        else:

            conn.execute(
                "UPDATE admin SET password=? WHERE username=?",
                (new_password, session.get("admin_username"))
            )

            conn.commit()
            conn.close()

            message = "Password changed successfully."

    return render_template_string("""
    <!DOCTYPE html>
    <html>

    <head>
        <title>Change Password - JEWEL VOGUE</title>
        {{ css|safe }}
    </head>

    <body>

    {{ nav|safe }}

    <div class="container">

        <div class="card">

            <h1>Change Password</h1>

            {% if message %}
                <div class="message">
                    {{ message }}
                </div>
            {% endif %}

            {% if error %}
                <div class="error">
                    {{ error }}
                </div>
            {% endif %}

            <form method="POST">

                <label>Current Password</label>

                <input
                    type="password"
                    name="current_password"
                    required
                >

                <label>New Password</label>

                <input
                    type="password"
                    name="new_password"
                    required
                >

                <label>Confirm New Password</label>

                <input
                    type="password"
                    name="confirm_password"
                    required
                >

                <button class="btn gold" type="submit">
                    Change Password
                </button>

            </form>

        </div>

    </div>

    </body>
    </html>
    """,
    css=CSS,
    nav=NAV,
    message=message,
    error=error
    )


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)

    return redirect(url_for("home"))


# =========================
# START APP
# =========================

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
