from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS shelves (shelf_id TEXT PRIMARY KEY, zone TEXT, note TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, qty INTEGER, bin TEXT, shelf TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, qty INTEGER, from_bin TEXT, to_shelf TEXT, employee TEXT, status TEXT, time TEXT)")
    # Pre-create shelves
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('A1','Electronics','High-Value')")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('A2','Electronics','Heavy')")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('B1','Groceries','Heavy')")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('B2','Fragile Zone','Fragile Only')")
    c.execute("INSERT OR IGNORE INTO shelves VALUES ('C1','General','')")
    conn.commit()
    conn.close()
init()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT shelf_id, zone FROM shelves")
    shelves = c.fetchall()
    c.execute("SELECT sku, qty, bin, shelf, status FROM products")
    products = c.fetchall()
    c.execute("SELECT sku, qty, from_bin, to_shelf, employee, status FROM tasks ORDER BY id DESC LIMIT 20")
    tasks = c.fetchall()
    conn.close()

    shelf_opts = "".join([f"<option value='{s[0]}'>{s[0]} - {s[1]}</option>" for s in shelves])

    prod_rows = ""
    for sku, qty, bin_loc, shelf, status in products:
        if status == "IN_BIN":
            prod_rows += f"<tr><td>{sku}</td><td>{qty}</td><td>{bin_loc}</td><td>{status}</td><td><form method='post' action='/assign'><input type='hidden' name='sku' value='{sku}'><select name='shelf_id' required>{shelf_opts}</select><input name='employee' placeholder='Employee name' required><button>Assign & Create Task</button></form></td></tr>"
        else:
            prod_rows += f"<tr style='background:#e8f5e9'><td>{sku}</td><td>{qty}</td><td>{bin_loc}</td><td>{shelf} ({status})</td><td>✅ Shelved</td></tr>"

    shelf_rows = ""
    for s in shelves:
        conn2 = sqlite3.connect(DB)
        c2 = conn2.cursor()
        c2.execute("SELECT sku, qty FROM products WHERE shelf=?", (s[0],))
        items = c2.fetchall()
        conn2.close()
        items_str = ", ".join([f"{i[0]} x{i[1]}" for i in items]) or "Empty"
        shelf_rows += f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{items_str}</td></tr>"

    task_rows = "".join([f"<tr><td>{t[0]} x{t[1]}</td><td>{t[2]} -> {t[3]}</td><td>{t[4]}</td><td>{t[5]}</td></tr>" for t in tasks])

    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{{font-family:sans-serif;padding:12px;font-size:13px}} table{{width:100%;border-collapse:collapse;margin:10px 0}} td,th{{border:1px solid #ccc;padding:6px}}.head{{background:#0d47a1;color:white;padding:12px}} button{{background:#1565c0;color:white;border:none;padding:6px 10px;border-radius:4px}}</style></head><body>
    <div class='head'><h2>STORAGE - Warehouse</h2><p>BIN -> Assign to Shelf -> Generate Task for Employee</p></div>
    <button onclick="location.reload()">REFRESH</button>

    <h3>Products from INTAKE (In BIN)</h3>
    <table><tr><th>SKU</th><th>Qty</th><th>BIN</th><th>Status / Shelf</th><th>Action</th></tr>{prod_rows}</table>

    <h3>Shelf Master - What's Where</h3>
    <table><tr><th>Shelf ID</th><th>Zone</th><th>What's in shelf</th></tr>{shelf_rows}</table>

    <h3>Put-Away Tasks (For Employees)</h3>
    <table><tr><th>Product</th><th>From -> To</th><th>Employee</th><th>Status</th></tr>{task_rows}</table>
    </body></html>
    """

@app.post("/assign")
def assign(sku: str = Form(...), shelf_id: str = Form(...), employee: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT qty, bin FROM products WHERE sku=?", (sku,))
    qty, bin_loc = c.fetchone()
    c.execute("UPDATE products SET shelf=?, status='SHELVED' WHERE sku=?", (shelf_id, sku))
    c.execute("INSERT INTO tasks (sku, qty, from_bin, to_shelf, employee, status, time) VALUES (?,?,?,?,?,?,?)",
              (sku, qty, bin_loc, shelf_id, employee, "PENDING - Go collect from BIN to shelf", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return HTMLResponse("<script>alert('Task created! Employee must move from BIN to shelf.'); window.location.href='/';</script>")

@app.post("/api/move_internal")
async def move_internal(request: Request):
    data = await request.json()
    sku = data.get("sku"); qty = int(data.get("qty",0)); bin_loc = data.get("bin","PLK-A-01-01")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT qty FROM products WHERE sku=?", (sku,))
    ex = c.fetchone()
    if ex:
        c.execute("UPDATE products SET qty=? WHERE sku=?", (ex[0]+qty, sku))
    else:
        c.execute("INSERT INTO products (sku, qty, bin, shelf, status) VALUES (?,?,?,?,?)", (sku, qty, bin_loc, None, "IN_BIN"))
    conn.commit()
    conn.close()
    return {"ok": True}
