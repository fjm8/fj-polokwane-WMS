from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime

app = FastAPI(title="FJ WAREHOUSE MANAGER")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Warehouse shelves assigned to store
    c.execute("""CREATE TABLE IF NOT EXISTS shelves
                 (shelf_id TEXT PRIMARY KEY, store TEXT, zone TEXT, shelf_type TEXT, max_kg INTEGER, current_kg INTEGER DEFAULT 0)""")
    # Products in warehouse
    c.execute("""CREATE TABLE IF NOT EXISTS products
                 (sku TEXT PRIMARY KEY, name TEXT, qty INTEGER, bin TEXT, shelf TEXT, store TEXT, weight INTEGER, durability TEXT, status TEXT)""")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('A1','Veldspaat Store','Electronics','High-Value/Fragile',300,0)")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('A2','Veldspaat Store','Electronics','Heavy-Duty',1000,0)")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('B1','Veldspaat Store','Groceries','Heavy',2000,0)")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('B2','Veldspaat Store','Fragile Zone','Fragile-Only',500,0)")
    conn.commit()
    conn.close()
init()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT shelf_id, store, zone, shelf_type, max_kg, current_kg FROM shelves")
    shelves = c.fetchall()
    c.execute("SELECT sku, name, qty, bin, shelf, store, weight, durability, status FROM products")
    products = c.fetchall()
    conn.close()

    shelf_options = "".join([f"<option value='{s[0]}'>{s[0]} - {s[2]} ({s[3]})</option>" for s in shelves])
    shelf_table = "".join([f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td><td>{s[3]}</td><td>{s[5]}kg / {s[4]}kg</td></tr>" for s in shelves])
    prod_table = "".join([f"<tr><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td><td>{p[3]}</td><td>{p[4] or 'IN BIN'}</td><td>{p[5]}</td><td>{p[7]}</td><td>{p[8]}</td><td><form method='post' action='/assign'><input type='hidden' name='sku' value='{p[0]}'><select name='shelf_id' required>{shelf_options}</select><button>Assign to Shelf/Store</button></form></td></tr>" for p in products])

    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{{font-family:sans-serif;padding:10px;font-size:13px}} table{{width:100%;border-collapse:collapse;margin-bottom:20px}} td,th{{border:1px solid #ccc;padding:6px}}.head{{background:#0d47a1;color:white;padding:12px}} button{{background:#1565c0;color:white;border:none;padding:6px 10px;border-radius:4px}} h3{{margin-top:30px}}</style></head><body>
    <div class='head'><h2>🔵 WAREHOUSE MANAGER - Assigned to Store</h2><p>Veldspaat Store DC | BIN -> SHELF -> STORE flow</p></div>

    <h3>1. SHELVES - Assigned to Store (Where products should go)</h3>
    <table><tr><th>Shelf ID</th><th>Store</th><th>Zone</th><th>Type</th><th>Load</th></tr>{shelf_table}</table>

    <h3>2. PRODUCTS IN WAREHOUSE - Assign to Shelves</h3>
    <button onclick="location.reload()">🔄 REFRESH</button>
    <table><tr><th>SKU</th><th>Name</th><th>Qty</th><th>BIN</th><th>Current Shelf</th><th>Store</th><th>Durability</th><th>Status</th><th>Assign</th></tr>{prod_table}</table>

    <h3>How it works:</h3>
    <p><b>INTAKE</b> -> Product arrives in BIN (IN_BIN). <b>WAREHOUSE MANAGER</b> assigns it to a SHELF that is assigned to a STORE. This prevents damage.</p>
    <p>Example: Fragile TV -> must go to A1 or B2 (Fragile), not B1 (Heavy Groceries).</p>
    </body></html>
    """

@app.post("/assign")
def assign(sku: str = Form(...), shelf_id: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Get product weight
    c.execute("SELECT weight, qty FROM products WHERE sku=?", (sku,))
    p = c.fetchone()
    weight_per = p[0] or 10
    qty = p[1] or 1
    total_w = weight_per * qty

    # Get shelf info
    c.execute("SELECT store, max_kg, current_kg, shelf_type FROM shelves WHERE shelf_id=?", (shelf_id,))
    s = c.fetchone()
    if not s:
        conn.close()
        return HTMLResponse("<script>alert('Shelf not found'); history.back();</script>")
    store, max_kg, curr_kg, shelf_type = s

    # Smart check: Fragile check
    c.execute("SELECT durability FROM products WHERE sku=?", (sku,))
    dur = c.fetchone()[0]
    if dur == "Fragile" and "Fragile" not in shelf_type and "High-Value" not in shelf_type:
        conn.close()
        return HTMLResponse(f"<script>alert('BLOCKED: Fragile product {sku} cannot go to {shelf_id} ({shelf_type}). Use Fragile shelf!'); window.location.href='/';</script>")
    if curr_kg + total_w > max_kg:
        conn.close()
        return HTMLResponse(f"<script>alert('BLOCKED: Shelf {shelf_id} overload! Current {curr_kg}kg + {total_w}kg > Max {max_kg}kg'); window.location.href='/';</script>")

    c.execute("UPDATE products SET shelf=?, store=?, status='SHELVED_IN_STORE' WHERE sku=?", (shelf_id, store, sku))
    c.execute("UPDATE shelves SET current_kg=? WHERE shelf_id=?", (curr_kg + total_w, shelf_id))
    conn.commit()
    conn.close()
    return HTMLResponse("<script>alert('Assigned to shelf & store!'); window.location.href='/';</script>")

@app.post("/api/move_internal")
async def move_internal(request: Request):
    data = await request.json()
    sku = data.get("sku")
    qty = int(data.get("qty", 0))
    bin_loc = data.get("bin", "PLK-A-01-01")
    name = data.get("name", sku)
    weight = int(data.get("weight", 10))
    durability = data.get("durability", "Durable")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT qty FROM products WHERE sku=?", (sku,))
    ex = c.fetchone()
    if ex:
        c.execute("UPDATE products SET qty=?, bin=? WHERE sku=?", (ex[0]+qty, bin_loc, sku))
    else:
        c.execute("INSERT INTO products (sku, name, qty, bin, shelf, store, weight, durability, status) VALUES (?,?,?,?,?,?,?,?,?)",
                  (sku, name, qty, bin_loc, None, "Veldspaat Store", weight, durability, "IN_BIN"))
    conn.commit()
    conn.close()
    return {"ok": True, "assigned_store": "Veldspaat Store"}
