"""
DRIP STORE - Complete Backend
Run: pip install fastapi uvicorn python-multipart
Then: python -m uvicorn main:app --reload
Open: http://localhost:8000
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json, os, hashlib, uuid, time

# ─────────────────────────────────────────
#  DATABASE  (data.json in same folder)
# ─────────────────────────────────────────
DB = os.path.join(os.path.dirname(__file__), "data.json")

def load():
    with open(DB) as f:
        return json.load(f)

def save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def make_token(email):
    return hashlib.sha256(f"{email}{time.time()}drip".encode()).hexdigest()

def auth(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Please login first")
    db = load()
    user = next((u for u in db["users"] if u.get("token") == token), None)
    if not user:
        raise HTTPException(401, "Session expired. Please login again.")
    return user, db

def safe_user(u):
    return {k: v for k, v in u.items() if k not in ("password", "token")}

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
    db = load()

    fn = body.get("first_name", "").strip()
    ln = body.get("last_name", "").strip()
    email = body.get("email", "").strip().lower()
    pw = body.get("password", "")
    phone = body.get("phone", "").strip()

    if not fn or not ln or not email or not pw:
        raise HTTPException(400, "Please fill in all required fields")
    if len(pw) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if any(u["email"] == email for u in db["users"]):
        raise HTTPException(400, "This email is already registered. Please login.")

    token = make_token(email)
    user = {
        "id": str(uuid.uuid4()),
        "first_name": fn, "last_name": ln,
        "email": email, "phone": phone,
        "password": hash_pw(pw),
        "token": token,
        "created_at": time.strftime("%Y-%m-%d")
    }
    db["users"].append(user)
    save(db)
    return {"ok": True, "token": token, "user": safe_user(user)}


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    pw = body.get("password", "")

    db = load()
    user = next((u for u in db["users"] if u["email"] == email), None)
    if not user or user["password"] != hash_pw(pw):
        raise HTTPException(401, "Wrong email or password")

    token = make_token(email)
    user["token"] = token
    save(db)
    return {"ok": True, "token": token, "user": safe_user(user)}


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
    search: str = "", category: str = "",
    sort: str = "newest", page: int = 1, per_page: int = 12
):
    db = load()
    items = db["products"]

    if search:
        s = search.lower()
        items = [p for p in items if s in p["name"].lower() or s in p["category"].lower()]
    if category:
        items = [p for p in items if p["category"].lower() == category.lower()]

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
    db = load()
    p = next((p for p in db["products"] if p["slug"] == slug), None)
    if not p:
        raise HTTPException(404, "Product not found")
    return p

# ─────────────────────────────────────────
#  CART
# ─────────────────────────────────────────
def cart_data(user_id, db):
    items = db["carts"].get(user_id, [])
    result = []
    for item in items:
        prod = next((p for p in db["products"] if p["id"] == item["product_id"]), None)
        if prod:
            result.append({**item, "product": prod})
    subtotal = sum(i["product"]["price"] * i["quantity"] for i in result)
    return {"items": result, "subtotal": round(subtotal, 2),
            "item_count": sum(i["quantity"] for i in result)}


@app.get("/api/cart")
async def get_cart(request: Request):
    user, db = auth(request)
    return cart_data(user["id"], db)


@app.post("/api/cart/add")
async def add_cart(request: Request):
    body = await request.json()
    user, db = auth(request)

    pid = body.get("product_id")
    qty = max(1, int(body.get("quantity", 1)))
    size = body.get("size", "")
    color = body.get("color", "")

    prod = next((p for p in db["products"] if p["id"] == pid), None)
    if not prod:
        raise HTTPException(404, "Product not found")
    if prod["stock"] < qty:
        raise HTTPException(400, f"Only {prod['stock']} items left in stock")

    cart = db["carts"].setdefault(user["id"], [])
    existing = next(
        (i for i in cart if i["product_id"] == pid and i.get("size") == size and i.get("color") == color),
        None
    )
    if existing:
        existing["quantity"] += qty
    else:
        cart.append({"id": str(uuid.uuid4()), "product_id": pid,
                     "quantity": qty, "size": size, "color": color})
    save(db)
    return cart_data(user["id"], db)


@app.put("/api/cart/{item_id}")
async def update_cart(item_id: str, request: Request):
    body = await request.json()
    user, db = auth(request)
    cart = db["carts"].get(user["id"], [])

    for i, item in enumerate(cart):
        if item["id"] == item_id:
            if body.get("quantity", 1) <= 0:
                cart.pop(i)
            else:
                item["quantity"] = body["quantity"]
            break

    db["carts"][user["id"]] = cart
    save(db)
    return cart_data(user["id"], db)


@app.delete("/api/cart/{item_id}")
async def remove_cart(item_id: str, request: Request):
    user, db = auth(request)
    cart = db["carts"].get(user["id"], [])
    db["carts"][user["id"]] = [i for i in cart if i["id"] != item_id]
    save(db)
    return cart_data(user["id"], db)

# ─────────────────────────────────────────
#  WISHLIST
# ─────────────────────────────────────────
@app.get("/api/wishlist")
async def get_wishlist(request: Request):
    user, db = auth(request)
    ids = db["wishlists"].get(user["id"], [])
    items = []
    for pid in ids:
        prod = next((p for p in db["products"] if p["id"] == pid), None)
        if prod:
            items.append({"product_id": pid, "product": prod})
    return items


@app.post("/api/wishlist/{product_id}")
async def add_wishlist(product_id: int, request: Request):
    user, db = auth(request)
    wish = db["wishlists"].setdefault(user["id"], [])
    if product_id not in wish:
        wish.append(product_id)
        save(db)
    return {"ok": True, "message": "Added to wishlist"}


@app.delete("/api/wishlist/{product_id}")
async def remove_wishlist(product_id: int, request: Request):
    user, db = auth(request)
    wish = db["wishlists"].get(user["id"], [])
    db["wishlists"][user["id"]] = [i for i in wish if i != product_id]
    save(db)
    return {"ok": True, "message": "Removed from wishlist"}

# ─────────────────────────────────────────
#  COUPON
# ─────────────────────────────────────────
@app.post("/api/coupon")
async def check_coupon(request: Request):
    body = await request.json()
    db = load()
    code = body.get("code", "").strip().upper()
    coupon = next((c for c in db["coupons"] if c["code"] == code), None)
    if not coupon:
        raise HTTPException(404, "Invalid coupon code. Try DRIP20, FLAT200, FIRST10 or WELCOME")
    msg = f"{int(coupon['value'])}% off" if coupon["type"] == "percent" else f"₹{coupon['value']} off"
    return {**coupon, "message": f"Coupon applied! {msg} on orders above ₹{coupon['min_order']}"}

# ─────────────────────────────────────────
#  ORDERS
# ─────────────────────────────────────────
@app.post("/api/orders")
async def place_order(request: Request):
    body = await request.json()
    user, db = auth(request)

    cart = db["carts"].get(user["id"], [])
    if not cart:
        raise HTTPException(400, "Your cart is empty. Add some items first.")

    subtotal = 0
    items_out = []
    for item in cart:
        prod = next((p for p in db["products"] if p["id"] == item["product_id"]), None)
        if prod:
            line = prod["price"] * item["quantity"]
            subtotal += line
            items_out.append({
                "product_id": prod["id"], "name": prod["name"],
                "qty": item["quantity"], "size": item.get("size", ""),
                "color": item.get("color", ""), "price": prod["price"], "total": line
            })

    # coupon
    discount = 0
    code = body.get("coupon_code", "").strip().upper()
    if code:
        coupon = next((c for c in db["coupons"] if c["code"] == code), None)
        if coupon and subtotal >= coupon["min_order"]:
            discount = subtotal * coupon["value"] / 100 if coupon["type"] == "percent" else min(coupon["value"], subtotal)

    delivery = {"standard": 0, "express": 149, "same_day": 299}.get(body.get("delivery_type", "standard"), 0)
    if body.get("payment_method") == "cod":
        delivery += 49

    tax = round((subtotal - discount + delivery) * 0.18, 2)
    total = round(subtotal - discount + delivery + tax, 2)

    order = {
        "id": str(uuid.uuid4()),
        "order_number": "DS" + str(int(time.time()))[-8:],
        "user_id": user["id"],
        "user_name": user["first_name"] + " " + user["last_name"],
        "user_email": user["email"],
        "items": items_out,
        "address": body.get("address", {}),
        "payment_method": body.get("payment_method", "cod"),
        "coupon": code,
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "delivery": delivery,
        "tax": tax,
        "total": total,
        "status": "Confirmed",
        "placed_at": time.strftime("%Y-%m-%d %H:%M")
    }

    db["orders"].append(order)
    db["carts"][user["id"]] = []   # clear cart
    save(db)
    return order


@app.get("/api/orders")
async def get_orders(request: Request):
    user, db = auth(request)
    orders = [o for o in db["orders"] if o["user_id"] == user["id"]]
    return sorted(orders, key=lambda o: o["placed_at"], reverse=True)


@app.get("/api/orders/{order_number}")
async def get_order(order_number: str, request: Request):
    user, db = auth(request)
    order = next((o for o in db["orders"]
                  if o["order_number"] == order_number and o["user_id"] == user["id"]), None)
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@app.get("/api/track/{order_number}")
async def track_order_public(order_number: str):
    db = load()
    order = next((o for o in db["orders"] if o["order_number"] == order_number), None)
    if not order:
        raise HTTPException(404, "Order not found")
    return order


# ─────────────────────────────────────────
#  ADMIN (shop owner)
# ─────────────────────────────────────────
@app.get("/api/admin/orders")
async def admin_get_orders(request: Request, status: str = None):
    user, db = auth(request)
    require_admin(user)

    orders = db["orders"]
    if status:
        s = status.strip().lower()
        if s in ("pending", "to-deliver", "open"):
            # Pending = anything not delivered or cancelled
            orders = [o for o in orders if o.get("status", "").lower() not in ("delivered", "cancelled")]
        else:
            orders = [o for o in orders if o.get("status", "").lower() == s]

    return sorted(orders, key=lambda o: o["placed_at"], reverse=True)


@app.put("/api/admin/orders/{order_number}/status")
async def admin_update_order_status(order_number: str, request: Request):
    user, db = auth(request)
    require_admin(user)

    body = await request.json()
    new_status = body.get("status", "").strip()
    if not new_status:
        raise HTTPException(400, "Missing status")

    order = next((o for o in db["orders"] if o["order_number"] == order_number), None)
    if not order:
        raise HTTPException(404, "Order not found")

    order["status"] = new_status
    save(db)
    return {"ok": True, "order": order}
