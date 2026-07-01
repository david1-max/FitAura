"""
DRIP STORE - Complete Backend
Run: pip install fastapi uvicorn python-multipart
Then: python -m uvicorn main:app --reload
Open: http://localhost:8000
"""

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import json, os, hashlib, uuid, time, secrets, sqlite3
from io import BytesIO
from database import get_db

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def hash_pw(pw):
    # Legacy SHA-256 hashing
    return hashlib.sha256(pw.encode()).hexdigest()

def hash_pw_pbkdf2(pw: str, salt: str = None) -> tuple[str, str]:
    # Modern secure PBKDF2 hashing
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        pw.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(pw: str, password_hash: str, salt: str, method: str) -> tuple[bool, bool]:
    # Returns (is_correct, should_upgrade)
    if method == "pbkdf2":
        key_hex, _ = hash_pw_pbkdf2(pw, salt)
        return key_hex == password_hash, False
    elif method == "sha256" or not method:
        is_correct = hash_pw(pw) == password_hash
        return is_correct, is_correct
    return False, False

def make_token():
    return secrets.token_hex(32)

def auth(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Please login first")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(401, "Session expired. Please login again.")
    
    user = dict(row)
    user["is_admin"] = bool(user["is_admin"])
    return user, None

def safe_user(u):
    keys_to_strip = ("password", "password_hash", "salt", "hashing_method", "token")
    return {k: v for k, v in u.items() if k not in keys_to_strip}

def require_admin(user):
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")

# ─────────────────────────────────────────
#  APP
# ─────────────────────────────────────────
app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# ─────────────────────────────────────────
#  SERVE HTML PAGES
# ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))

@app.get("/{page}.html", response_class=HTMLResponse)
def page(page: str):
    path = os.path.join(STATIC, f"{page}.html")
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join(STATIC, "404.html"), status_code=404)


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def admin_page():
    return FileResponse(os.path.join(STATIC, "admin.html"))

# ─────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────
@app.post("/api/register")
async def register(request: Request):
    body = await request.json()

    fn = body.get("first_name", "").strip()
    ln = body.get("last_name", "").strip()
    email = body.get("email", "").strip().lower()
    pw = body.get("password", "")
    phone = body.get("phone", "").strip()

    if not fn or not ln or not email or not pw:
        raise HTTPException(400, "Please fill in all required fields")
    if len(pw) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(400, "This email is already registered. Please login.")

    pw_hash, salt = hash_pw_pbkdf2(pw)
    token = make_token()
    user_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO users (id, first_name, last_name, email, phone, password_hash, salt, hashing_method, token, is_admin, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (user_id, fn, ln, email, phone, pw_hash, salt, "pbkdf2", token, created_at))
    conn.commit()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(cursor.fetchone())
    conn.close()

    return {"ok": True, "token": token, "user": safe_user(user)}


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    pw = body.get("password", "")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(401, "Wrong email or password")

    user = dict(row)
    is_correct, should_upgrade = verify_password(pw, user["password_hash"], user["salt"], user["hashing_method"])
    if not is_correct:
        conn.close()
        raise HTTPException(401, "Wrong email or password")

    token = make_token()
    if should_upgrade:
        new_hash, new_salt = hash_pw_pbkdf2(pw)
        cursor.execute("""
        UPDATE users SET password_hash = ?, salt = ?, hashing_method = 'pbkdf2', token = ? WHERE id = ?
        """, (new_hash, new_salt, token, user["id"]))
    else:
        cursor.execute("UPDATE users SET token = ? WHERE id = ?", (token, user["id"]))
    
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
    updated_user = dict(cursor.fetchone())
    conn.close()

    return {"ok": True, "token": token, "user": safe_user(updated_user)}


@app.get("/api/me")
async def me(request: Request):
    user, _ = auth(request)
    return safe_user(user)

# ─────────────────────────────────────────
#  PRODUCTS
# ─────────────────────────────────────────
@app.get("/api/products")
async def products(
    request: Request,
    search: str = "", category: str = "", categories: str = "",
    sizes: str = "", colors: str = "", in_stock: int = 0,
    max_price: float = 0.0,
    sort: str = "newest", page: int = 1, per_page: int = 12
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for r in rows:
        p = dict(r)
        p["sizes"] = json.loads(p["sizes"]) if p.get("sizes") else []
        p["colors"] = json.loads(p["colors"]) if p.get("colors") else []
        items.append(p)

    if search:
        s = search.lower()
        items = [p for p in items if s in p["name"].lower() or s in p["category"].lower()]
        
    if category:
        items = [p for p in items if p["category"].lower() == category.lower()]
    elif categories:
        cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
        items = [p for p in items if p["category"].lower() in cats]
        
    if sizes:
        sz_list = [s.strip().upper() for s in sizes.split(",") if s.strip()]
        items = [p for p in items if any(size in p["sizes"] for size in sz_list)]
        
    if colors:
        cl_list = [c.strip().lower() for c in colors.split(",") if c.strip()]
        items = [p for p in items if any(color.lower() in [pc.lower() for pc in p["colors"]] for color in cl_list)]
        
    if in_stock == 1:
        items = [p for p in items if p["stock"] > 0]
        
    if max_price > 0.0:
        items = [p for p in items if p["price"] <= max_price]

    if sort == "price_asc":   items = sorted(items, key=lambda p: p["price"])
    elif sort == "price_desc": items = sorted(items, key=lambda p: p["price"], reverse=True)
    elif sort == "rating":     items = sorted(items, key=lambda p: p["rating"], reverse=True)
    elif sort == "popular":    items = sorted(items, key=lambda p: p["stock"])

    total = len(items)
    start = (page - 1) * per_page
    return {"items": items[start:start+per_page], "total": total, "page": page,
            "pages": max(1, (total + per_page - 1) // per_page)}


@app.get("/api/products/{slug}")
async def product(slug: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE slug = ?", (slug,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Product not found")
        
    p = dict(row)
    p["sizes"] = json.loads(p["sizes"]) if p.get("sizes") else []
    p["colors"] = json.loads(p["colors"]) if p.get("colors") else []
    return p


@app.get("/api/products/{product_id}/reviews")
async def get_product_reviews(product_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC", (product_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/products/{product_id}/reviews")
async def add_product_review(product_id: int, request: Request):
    user, _ = auth(request)
    body = await request.json()
    
    rating = int(body.get("rating", 5))
    comment = body.get("comment", "").strip()
    
    if rating < 1 or rating > 5:
        raise HTTPException(400, "Rating must be between 1 and 5")
        
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "Product not found")
        
    created_at = time.strftime("%Y-%m-%d %H:%M")
    user_name = f"{user['first_name']} {user['last_name']}".strip()
    
    try:
        cursor.execute("""
        INSERT INTO reviews (product_id, user_id, user_name, rating, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, user["id"], user_name, rating, comment, created_at))
        
        # Recalculate average rating
        cursor.execute("SELECT AVG(rating) FROM reviews WHERE product_id = ?", (product_id,))
        avg_val = cursor.fetchone()[0]
        avg_rating = round(float(avg_val), 1) if avg_val is not None else 5.0
        
        cursor.execute("UPDATE products SET rating = ? WHERE id = ?", (avg_rating, product_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(500, f"Database error: {e}")
        
    conn.close()
    return {"ok": True, "message": "Review submitted successfully", "avg_rating": avg_rating}

# ─────────────────────────────────────────
#  CART
# ─────────────────────────────────────────
def cart_data(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    
    result = []
    for r in rows:
        item = dict(r)
        cursor.execute("SELECT * FROM products WHERE id = ?", (item["product_id"],))
        p_row = cursor.fetchone()
        if p_row:
            prod = dict(p_row)
            prod["sizes"] = json.loads(prod["sizes"]) if prod.get("sizes") else []
            prod["colors"] = json.loads(prod["colors"]) if prod.get("colors") else []
            result.append({**item, "product": prod})
            
    conn.close()
    subtotal = sum(i["product"]["price"] * i["quantity"] for i in result)
    return {"items": result, "subtotal": round(subtotal, 2),
            "item_count": sum(i["quantity"] for i in result)}


@app.get("/api/cart")
async def get_cart(request: Request):
    user, _ = auth(request)
    return cart_data(user["id"])


@app.post("/api/cart/add")
async def add_cart(request: Request):
    body = await request.json()
    user, _ = auth(request)

    pid = body.get("product_id")
    qty = max(1, int(body.get("quantity", 1)))
    size = body.get("size", "")
    color = body.get("color", "")

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE id = ?", (pid,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(404, "Product not found")
    prod = dict(p_row)
    if prod["stock"] < qty:
        conn.close()
        raise HTTPException(400, f"Only {prod['stock']} items left in stock")

    cursor.execute("""
    SELECT * FROM carts 
    WHERE user_id = ? AND product_id = ? AND size = ? AND color = ?
    """, (user["id"], pid, size, color))
    existing = cursor.fetchone()
    
    if existing:
        new_qty = existing["quantity"] + qty
        if prod["stock"] < new_qty:
            conn.close()
            raise HTTPException(400, f"Only {prod['stock']} items left in stock")
        cursor.execute("UPDATE carts SET quantity = ? WHERE id = ?", (new_qty, existing["id"]))
    else:
        cursor.execute("""
        INSERT INTO carts (id, user_id, product_id, quantity, size, color)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user["id"], pid, qty, size, color))
        
    conn.commit()
    conn.close()
    
    return cart_data(user["id"])


@app.put("/api/cart/{item_id}")
async def update_cart(item_id: str, request: Request):
    body = await request.json()
    user, _ = auth(request)
    qty = int(body.get("quantity", 1))

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM carts WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(404, "Item not found in cart")

    if qty <= 0:
        cursor.execute("DELETE FROM carts WHERE id = ?", (item_id,))
    else:
        cursor.execute("SELECT stock FROM products WHERE id = ?", (item["product_id"],))
        p_row = cursor.fetchone()
        if p_row and p_row["stock"] < qty:
            conn.close()
            raise HTTPException(400, f"Only {p_row['stock']} items left in stock")
        cursor.execute("UPDATE carts SET quantity = ? WHERE id = ?", (qty, item_id))
        
    conn.commit()
    conn.close()
    return cart_data(user["id"])


@app.delete("/api/cart/{item_id}")
async def remove_cart(item_id: str, request: Request):
    user, _ = auth(request)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carts WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    conn.commit()
    conn.close()
    
    return cart_data(user["id"])

# ─────────────────────────────────────────
#  WISHLIST
# ─────────────────────────────────────────
@app.get("/api/wishlist")
async def get_wishlist(request: Request):
    user, _ = auth(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM wishlists WHERE user_id = ?", (user["id"],))
    rows = cursor.fetchall()
    
    items = []
    for r in rows:
        pid = r["product_id"]
        cursor.execute("SELECT * FROM products WHERE id = ?", (pid,))
        p_row = cursor.fetchone()
        if p_row:
            prod = dict(p_row)
            prod["sizes"] = json.loads(prod["sizes"]) if prod.get("sizes") else []
            prod["colors"] = json.loads(prod["colors"]) if prod.get("colors") else []
            items.append({"product_id": pid, "product": prod})
            
    conn.close()
    return items


@app.post("/api/wishlist/{product_id}")
async def add_wishlist(product_id: int, request: Request):
    user, _ = auth(request)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT OR IGNORE INTO wishlists (user_id, product_id)
        VALUES (?, ?)
        """, (user["id"], product_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "message": "Added to wishlist"}


@app.delete("/api/wishlist/{product_id}")
async def remove_wishlist(product_id: int, request: Request):
    user, _ = auth(request)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        DELETE FROM wishlists 
        WHERE user_id = ? AND product_id = ?
        """, (user["id"], product_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "message": "Removed from wishlist"}

# ─────────────────────────────────────────
#  COUPON
# ─────────────────────────────────────────
@app.post("/api/coupon")
async def check_coupon(request: Request):
    body = await request.json()
    code = body.get("code", "").strip().upper()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Invalid coupon code. Try DRIP20, FLAT200, FIRST10 or WELCOME")
        
    coupon = dict(row)
    msg = f"{int(coupon['value'])}% off" if coupon["type"] == "percent" else f"₹{coupon['value']} off"
    return {**coupon, "message": f"Coupon applied! {msg} on orders above ₹{coupon['min_order']}"}

# ─────────────────────────────────────────
#  ORDERS
# ─────────────────────────────────────────
@app.post("/api/orders")
async def place_order(request: Request):
    body = await request.json()
    user, _ = auth(request)

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM carts WHERE user_id = ?", (user["id"],))
    cart = cursor.fetchall()
    if not cart:
        conn.close()
        raise HTTPException(400, "Your cart is empty. Add some items first.")

    subtotal = 0
    items_out = []
    
    for item in cart:
        cursor.execute("SELECT * FROM products WHERE id = ?", (item["product_id"],))
        p_row = cursor.fetchone()
        if not p_row:
            conn.close()
            raise HTTPException(404, "One or more products in your cart could not be found.")
        prod = dict(p_row)
        if prod["stock"] < item["quantity"]:
            conn.close()
            raise HTTPException(400, f"Sorry, only {prod['stock']} units of '{prod['name']}' are left in stock.")

    try:
        for item in cart:
            cursor.execute("SELECT * FROM products WHERE id = ?", (item["product_id"],))
            prod = dict(cursor.fetchone())
            new_stock = prod["stock"] - item["quantity"]
            cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, prod["id"]))
            
            line = prod["price"] * item["quantity"]
            subtotal += line
            item_dict = dict(item)
            items_out.append({
                "product_id": prod["id"], "name": prod["name"],
                "qty": item_dict["quantity"], "size": item_dict.get("size", ""),
                "color": item_dict.get("color", ""), "price": prod["price"], "total": line
            })

        discount = 0
        code = body.get("coupon_code", "").strip().upper()
        if code:
            cursor.execute("SELECT * FROM coupons WHERE code = ?", (code,))
            c_row = cursor.fetchone()
            if c_row:
                coupon = dict(c_row)
                if subtotal >= coupon["min_order"]:
                    discount = subtotal * coupon["value"] / 100 if coupon["type"] == "percent" else min(coupon["value"], subtotal)

        delivery = {"standard": 0, "express": 149, "same_day": 299}.get(body.get("delivery_type", "standard"), 0)
        if body.get("payment_method") == "cod":
            delivery += 49

        tax = round((subtotal - discount + delivery) * 0.18, 2)
        total = round(subtotal - discount + delivery + tax, 2)

        order_id = str(uuid.uuid4())
        order_number = "DS" + str(int(time.time()))[-8:]
        placed_at = time.strftime("%Y-%m-%d %H:%M")
        
        cursor.execute("""
        INSERT INTO orders (id, order_number, user_id, user_name, user_email, items, address, payment_method, coupon, subtotal, discount, delivery, tax, total, status, placed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?)
        """, (order_id, order_number, user["id"], user["first_name"] + " " + user["last_name"], user["email"],
              json.dumps(items_out), json.dumps(body.get("address", {})), body.get("payment_method", "cod"),
              code, round(subtotal, 2), round(discount, 2), delivery, tax, total, placed_at))
        
        cursor.execute("DELETE FROM carts WHERE user_id = ?", (user["id"],))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(500, f"Failed to place order: {e}")

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    o_row = cursor.fetchone()
    conn.close()
    
    order = dict(o_row)
    order["items"] = json.loads(order["items"]) if order.get("items") else []
    order["address"] = json.loads(order["address"]) if order.get("address") else {}
    return order


@app.get("/api/orders")
async def get_orders(request: Request):
    user, _ = auth(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ?", (user["id"],))
    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o["items"]) if o.get("items") else []
        o["address"] = json.loads(o["address"]) if o.get("address") else {}
        orders.append(o)
        
    return sorted(orders, key=lambda o: o["placed_at"], reverse=True)


@app.get("/api/orders/{order_number}")
async def get_order(order_number: str, request: Request):
    user, _ = auth(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_number = ? AND user_id = ?", (order_number, user["id"]))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Order not found")
        
    order = dict(row)
    order["items"] = json.loads(order["items"]) if order.get("items") else []
    order["address"] = json.loads(order["address"]) if order.get("address") else {}
    return order


@app.get("/api/track/{order_number}")
async def track_order_public(order_number: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Order not found")
        
    order = dict(row)
    order["items"] = json.loads(order["items"]) if order.get("items") else []
    order["address"] = json.loads(order["address"]) if order.get("address") else {}
    return order


def generate_pdf_invoice(order):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#b8860b')
    )
    
    header_style = ParagraphStyle(
        'InvoiceHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555')
    )

    normal_style = ParagraphStyle(
        'InvoiceNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1c1a17')
    )
    
    # Title
    story.append(Paragraph("DRIP STORE INVOICE", title_style))
    story.append(Spacer(1, 10))
    
    # Store/Invoice header table
    addr = order.get("address", {})
    customer_addr = f"{addr.get('line1', '')}, {addr.get('city', '')}, {addr.get('state', '')} - {addr.get('postal_code', '')}"
    
    left_content = f"""<b>DRIP STORE</b><br/>
    Connaught Place, New Delhi<br/>
    Delhi, India - 110001<br/>
    Support: support@dripstore.com
    """
    
    right_content = f"""<b>Invoice No:</b> {order['order_number']}<br/>
    <b>Date:</b> {order['placed_at']}<br/>
    <b>Payment Method:</b> {order['payment_method'].upper()}<br/>
    <b>Status:</b> {order['status']}
    """
    
    header_data = [
        [Paragraph(left_content, header_style), Paragraph(right_content, header_style)]
    ]
    
    header_table = Table(header_data, colWidths=[260, 260])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Billing Info
    billing_content = f"""<b>BILL TO:</b><br/>
    <b>Name:</b> {order['user_name']}<br/>
    <b>Email:</b> {order['user_email']}<br/>
    <b>Delivery Address:</b> {customer_addr}
    """
    story.append(Paragraph(billing_content, normal_style))
    story.append(Spacer(1, 20))
    
    # Items Table Headers
    items_data = [
        ["Product Name", "Size", "Color", "Price", "Qty", "Total"]
    ]
    
    for item in order["items"]:
        items_data.append([
            item["name"],
            item.get("size", "-"),
            item.get("color", "-"),
            f"INR {item['price']}",
            str(item["qty"]),
            f"INR {item['total']}"
        ])
        
    items_table = Table(items_data, colWidths=[200, 50, 70, 70, 50, 80])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f2f0ea')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1c1a17')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e0d8')),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Totals Table
    discount_row = f"- INR {order['discount']}" if order['discount'] > 0 else "INR 0.0"
    totals_data = [
        ["Subtotal:", f"INR {order['subtotal']}"],
        ["Coupon Discount:", discount_row],
        ["Delivery Charge:", f"INR {order['delivery']}"],
        ["GST (18%):", f"INR {order['tax']}"],
        ["Final Total:", f"INR {order['total']}"]
    ]
    totals_table = Table(totals_data, colWidths=[400, 120])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-2,-1), 'Helvetica'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor('#b8860b')),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 40))
    
    # Footer Note
    terms_content = """<b>Thank you for shopping with DRIP STORE!</b><br/>
    This is a computer-generated invoice and does not require a physical signature.<br/>
    For return or exchange requests, please contact us at support@dripstore.com.
    """
    center_style = ParagraphStyle(
        'InvoiceCenter',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#6b6560')
    )
    story.append(Paragraph(terms_content, center_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


@app.get("/api/orders/{order_number}/invoice")
async def get_order_invoice(order_number: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Order not found")
        
    order = dict(row)
    order["items"] = json.loads(order["items"]) if order.get("items") else []
    order["address"] = json.loads(order["address"]) if order.get("address") else {}
    
    try:
        pdf_buffer = generate_pdf_invoice(order)
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f"attachment; filename=invoice_{order_number}.pdf"}
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate invoice PDF: {e}")


# ─────────────────────────────────────────
#  ADMIN (shop owner)
# ─────────────────────────────────────────
@app.get("/api/admin/orders")
async def admin_get_orders(request: Request, status: str = None):
    user, _ = auth(request)
    require_admin(user)

    conn = get_db()
    cursor = conn.cursor()
    
    if status:
        s = status.strip().lower()
        if s in ("pending", "to-deliver", "open"):
            cursor.execute("SELECT * FROM orders WHERE LOWER(status) NOT IN ('delivered', 'cancelled')")
        else:
            cursor.execute("SELECT * FROM orders WHERE LOWER(status) = ?", (s,))
    else:
        cursor.execute("SELECT * FROM orders")
        
    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o["items"]) if o.get("items") else []
        o["address"] = json.loads(o["address"]) if o.get("address") else {}
        orders.append(o)

    return sorted(orders, key=lambda o: o["placed_at"], reverse=True)


@app.put("/api/admin/orders/{order_number}/status")
async def admin_update_order_status(order_number: str, request: Request):
    user, _ = auth(request)
    require_admin(user)

    body = await request.json()
    new_status = body.get("status", "").strip()
    if not new_status:
        raise HTTPException(400, "Missing status")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Order not found")

    cursor.execute("UPDATE orders SET status = ? WHERE order_number = ?", (new_status, order_number))
    conn.commit()
    
    cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
    updated_row = cursor.fetchone()
    conn.close()
    
    order = dict(updated_row)
    order["items"] = json.loads(order["items"]) if order.get("items") else []
    order["address"] = json.loads(order["address"]) if order.get("address") else {}
    return {"ok": True, "order": order}


@app.post("/api/admin/products/upload")
async def upload_product_image(request: Request, file: UploadFile = File(...)):
    user, _ = auth(request)
    require_admin(user)
    
    uploads_dir = os.path.join(STATIC, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(uploads_dir, filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    return {"image_url": f"/static/uploads/{filename}"}


@app.post("/api/admin/products")
async def admin_create_product(request: Request):
    user, _ = auth(request)
    require_admin(user)
    
    body = await request.json()
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip().lower()
    price = float(body.get("price", 0.0))
    orig_price = body.get("original_price")
    if orig_price is not None and str(orig_price).strip() != "":
        orig_price = float(orig_price)
    else:
        orig_price = None
    category = body.get("category", "").strip()
    badge = body.get("badge", "").strip()
    stock = int(body.get("stock", 0))
    sizes = body.get("sizes", [])
    colors = body.get("colors", [])
    image_url = body.get("image_url", "").strip()
    
    if not name or not slug or price <= 0:
        raise HTTPException(400, "Name, slug, and price are required")
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO products (name, slug, price, original_price, category, badge, rating, stock, sizes, colors, image_url)
        VALUES (?, ?, ?, ?, ?, ?, 5.0, ?, ?, ?, ?)
        """, (name, slug, price, orig_price, category, badge, stock, json.dumps(sizes), json.dumps(colors), image_url))
        conn.commit()
        product_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, "A product with this slug already exists.")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(500, f"Database error: {e}")
        
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    p_row = cursor.fetchone()
    conn.close()
    
    p = dict(p_row)
    p["sizes"] = json.loads(p["sizes"]) if p.get("sizes") else []
    p["colors"] = json.loads(p["colors"]) if p.get("colors") else []
    return {"ok": True, "product": p}


@app.put("/api/admin/products/{product_id}")
async def admin_update_product(product_id: int, request: Request):
    user, _ = auth(request)
    require_admin(user)
    
    body = await request.json()
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip().lower()
    price = float(body.get("price", 0.0))
    orig_price = body.get("original_price")
    if orig_price is not None and str(orig_price).strip() != "":
        orig_price = float(orig_price)
    else:
        orig_price = None
    category = body.get("category", "").strip()
    badge = body.get("badge", "").strip()
    stock = int(body.get("stock", 0))
    sizes = body.get("sizes", [])
    colors = body.get("colors", [])
    image_url = body.get("image_url", "").strip()
    
    if not name or not slug or price <= 0:
        raise HTTPException(400, "Name, slug, and price are required")
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "Product not found")
        
    try:
        cursor.execute("""
        UPDATE products 
        SET name = ?, slug = ?, price = ?, original_price = ?, category = ?, badge = ?, stock = ?, sizes = ?, colors = ?, image_url = ?
        WHERE id = ?
        """, (name, slug, price, orig_price, category, badge, stock, json.dumps(sizes), json.dumps(colors), image_url, product_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, "A product with this slug already exists.")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(500, f"Database error: {e}")
        
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    p_row = cursor.fetchone()
    conn.close()
    
    p = dict(p_row)
    p["sizes"] = json.loads(p["sizes"]) if p.get("sizes") else []
    p["colors"] = json.loads(p["colors"]) if p.get("colors") else []
    return {"ok": True, "product": p}


@app.delete("/api/admin/products/{product_id}")
async def admin_delete_product(product_id: int, request: Request):
    user, _ = auth(request)
    require_admin(user)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "Product not found")
        
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Product deleted successfully"}


# ─────────────────────────────────────────
#  ADMIN MEMBERS MANAGEMENT
# ─────────────────────────────────────────
@app.get("/api/admin/users")
async def admin_get_users(request: Request):
    user, _ = auth(request)
    require_admin(user)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name, last_name, email, phone, is_admin, created_at FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]


@app.put("/api/admin/users/{user_id}/role")
async def admin_update_user_role(user_id: str, request: Request):
    admin_user, _ = auth(request)
    require_admin(admin_user)
    
    if admin_user["id"] == user_id:
        raise HTTPException(400, "You cannot modify your own admin role.")
        
    body = await request.json()
    is_admin = 1 if body.get("is_admin") else 0
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "User not found")
        
    cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "User role updated successfully"}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    admin_user, _ = auth(request)
    require_admin(admin_user)
    
    if admin_user["id"] == user_id:
        raise HTTPException(400, "You cannot delete your own admin account.")
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "User not found")
        
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "User account deleted successfully"}
