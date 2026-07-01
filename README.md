# FitAura — Premium Streetwear E-Commerce Store

FitAura is a feature-rich, high-performance, warm-luxury streetwear e-commerce platform. It features a complete shopping funnel, administrative moderation dashboards, reviews, sliding side carts, dynamic PDF invoicing, and interactive filters, built using a lightweight **FastAPI** backend and an embedded **SQLite** database.

---

## Key Features

### 🛍️ Customer Experience
- **Sleek warm-luxury styling:** Built using premium typography (Playfair Display + Inter), layered soft ambient shadows, fluid bezier animations, blur backdrops, and modern hover interactions.
- **Interactive Sliding Cart Drawer:** Click the cart icon to slide open a side cart drawer panel. Modify item quantities, remove products, and view subtotal updates without leaving the catalog.
- **Advanced Shop Sidebar Filters:** Filter products dynamically by Category checkboxes, Size checkboxes, Color swatches, Stock availability (In-Stock only), and a Price range slider (₹0 – ₹5,000).
- **Product Reviews & Ratings:** Write customer comments and submit 1-5 star reviews on product detail pages. Average stars are updated in the store catalog dynamically.
- **Dynamic PDF Invoice Downloads:** Track your order status online and download a professionally compiled receipt invoice sheet in PDF format with one click.

### ⚙️ Administrative Dashboard (`/admin.html`)
- **Inventory Control:** Complete CRUD actions to create, update, or remove catalog items.
- **Product Image Uploads:** Drag-and-drop or browse local file fields inside the product creation modal to save real image paths.
- **Member Directory Control:** View user details, promote customers to administrators, or delete accounts, complete with safeguards blocking admins from self-demoting or self-deleting their own accounts.
- **Order Tracking:** Update customer order delivery states (Placed, Confirmed, Packing, Shipped, Delivered).

---

## Tech Stack
- **Backend:** Python, FastAPI, SQLite (database), ReportLab (PDF compiler), a2wsgi (WSGI adapter for hosting)
- **Frontend:** Semantic HTML5, Vanilla CSS3, Vanilla ES6 JavaScript (zero heavy frameworks, ensuring extremely fast page load times and perfect SEO speeds)

---

## Installation & Local Execution

### 1. Install Dependencies
Run this command inside your terminal to install all required python libraries:
```bash
pip install fastapi uvicorn reportlab a2wsgi
```

### 2. Run the Server
Start the local ASGI web server:
```bash
python -m uvicorn main:app --reload
```
Once started, visit the store in your browser:
👉 **Local Storefront:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Administration Portal

To log into the management console:
1. Register a new user account at the `/register.html` page.
2. Log in with the administrator credentials initialized in the database seed, or promote an existing account through direct database query.
3. Once authenticated, access the dashboard at `/admin.html`.

## Codebase Structure
- `main.py` — Core FastAPI REST endpoints, auth checks, file upload endpoints, and PDF generators.
- `database.py` — Database schema creation, seed catalog files, and table migration.
- `checklist.md` — Detailed checklist for hosting and SEO optimization.
- `static/` — Frontend layouts, animations, and JS scripts.
  - `static/uploads/` — Local directory storing product images uploaded by the admin.
  - `static/style.css` — Global stylesheets containing color tokens and layouts.
  - `static/app.js` — Client cart updates, session handlers, and dynamic drawer injection.
