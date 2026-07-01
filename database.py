import sqlite3
import os
import json

DB_FILE = os.path.join(os.path.dirname(__file__), "database.db")
JSON_FILE = os.path.join(os.path.dirname(__file__), "data.json")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Only run migration if the database tables do not exist
    conn = get_db()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password_hash TEXT,
        salt TEXT,
        hashing_method TEXT,
        token TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        slug TEXT UNIQUE,
        price REAL,
        original_price REAL,
        category TEXT,
        badge TEXT,
        rating REAL,
        stock INTEGER,
        sizes TEXT,
        colors TEXT,
        image_url TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS carts (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        product_id INTEGER,
        quantity INTEGER,
        size TEXT,
        color TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wishlists (
        user_id TEXT,
        product_id INTEGER,
        PRIMARY KEY (user_id, product_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        order_number TEXT UNIQUE,
        user_id TEXT,
        user_name TEXT,
        user_email TEXT,
        items TEXT,
        address TEXT,
        payment_method TEXT,
        coupon TEXT,
        subtotal REAL,
        discount REAL,
        delivery REAL,
        tax REAL,
        total REAL,
        status TEXT,
        placed_at TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        type TEXT,
        value REAL,
        min_order REAL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        user_id TEXT,
        user_name TEXT,
        rating INTEGER,
        comment TEXT,
        created_at TEXT
    )
    """)
    
    conn.commit()
    
    # Safely alter table to add image_url to products table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    
    # Check if we need to migrate data
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0 and os.path.exists(JSON_FILE):
        print("Migrating data from data.json to SQLite database...")
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Users
            for u in data.get("users", []):
                # Map old format
                is_admin = 1 if u.get("is_admin") else 0
                # Old passwords were SHA-256 (64 characters long)
                # Keep hashing_method as 'sha256' for imported legacy accounts
                cursor.execute("""
                INSERT OR IGNORE INTO users 
                (id, first_name, last_name, email, phone, password_hash, salt, hashing_method, token, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (u["id"], u.get("first_name", ""), u.get("last_name", ""), u["email"], u.get("phone", ""), 
                      u["password"], None, "sha256", u.get("token"), is_admin, u.get("created_at", "")))
            
            # Products
            for p in data.get("products", []):
                sizes = json.dumps(p.get("sizes", []))
                colors = json.dumps(p.get("colors", []))
                cursor.execute("""
                INSERT OR IGNORE INTO products 
                (id, name, slug, price, original_price, category, badge, rating, stock, sizes, colors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p["id"], p["name"], p["slug"], p["price"], p.get("original_price"), p["category"], 
                      p.get("badge"), p.get("rating", 5.0), p.get("stock", 0), sizes, colors))
            
            # Carts
            for user_id, cart_items in data.get("carts", {}).items():
                for item in cart_items:
                    cursor.execute("""
                    INSERT OR IGNORE INTO carts (id, user_id, product_id, quantity, size, color)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (item.get("id"), user_id, item["product_id"], item.get("quantity", 1), 
                          item.get("size", ""), item.get("color", "")))
            
            # Wishlists
            for user_id, product_ids in data.get("wishlists", {}).items():
                for pid in product_ids:
                    cursor.execute("""
                    INSERT OR IGNORE INTO wishlists (user_id, product_id)
                    VALUES (?, ?)
                    """, (user_id, pid))
            
            # Orders
            for o in data.get("orders", []):
                items = json.dumps(o.get("items", []))
                address = json.dumps(o.get("address", {}))
                cursor.execute("""
                INSERT OR IGNORE INTO orders 
                (id, order_number, user_id, user_name, user_email, items, address, payment_method, coupon, subtotal, discount, delivery, tax, total, status, placed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (o["id"], o["order_number"], o["user_id"], o.get("user_name", ""), o.get("user_email", ""), 
                      items, address, o.get("payment_method", "cod"), o.get("coupon", ""), o["subtotal"], o.get("discount", 0.0), 
                      o.get("delivery", 0.0), o.get("tax", 0.0), o["total"], o.get("status", "Confirmed"), o.get("placed_at", "")))
            
            # Coupons
            for c in data.get("coupons", []):
                cursor.execute("""
                INSERT OR IGNORE INTO coupons (code, type, value, min_order)
                VALUES (?, ?, ?, ?)
                """, (c["code"], c["type"], c["value"], c["min_order"]))
            
            conn.commit()
            print("Migration completed successfully!")
        except Exception as e:
            conn.rollback()
            print(f"Error during migration: {e}")
            raise e
    
    conn.close()

# Run initialization immediately when imported
init_db()
