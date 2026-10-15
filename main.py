from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime

app = FastAPI(title="STORAGE - Item Level Tracking")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS shelves (shelf_id TEXT PRIMARY KEY, zone TEXT, note TEXT)")
    # UPDATED: Stores UNIQUE CODE per item, not just SKU qty
    c.execute("""CREATE TABLE IF NOT EXISTS products
                 (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, shelf TEXT, status TEXT, weight INTEGER, durability TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, unique_code TEXT, sku TEXT, from_bin TEXT, to_shelf TEXT, employee TEXT, status TEXT, time TEXT)""")
    for sid, zone in [('A1','Electronics'),('A2','Electronics'),('B1','Groceries Heavy'),('B2','Fragile Zone'),('C1','General'),('D1','Returns/Damaged')]:
        c.execute("INSERT OR IGNORE INTO shelves VALUES (?,?,?)", (sid, zone, ""))
    conn.commit()
    conn.close()
init()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT shelf_id, zone FROM shelves")
    shelves = c.fetchall()
    c.execute("SELECT unique_code, sku, name, bin, shelf, status FROM products ORDER BY status")
    products = c.fetchall()
    c.execute("SELECT unique_code, sku, from_bin, to_shelf, employee, status FROM tasks ORDER BY id DESC LIMIT 30")
    tasks = c.fetchall()
    conn.close()

    shelf_opts = "".join([f"<option value='{s[0]}'>{s[0]} - {s[1]}</option>" for s in shelves])

    in_bin_rows = ""
    shelved_rows = ""
    for ucode, sku, name, bin_loc, shelf, status in products:
        qr = f"https://api.qrserver.com/v1/create-qr-code/?size=50x50&data={ucode}"
        if status == "IN_BIN":
            in_bin_rows += f"<tr><td><b>{ucode}</b><br><img src='{qr}'><br>{sku}</td><td>{name}</td><td>{bin_loc}</td><td><form method='post' action='/assign'><input type='hidden' name='unique_code' value='{ucode}'><select name='shelf_id' required>{shelf_opts}</select><input name='employee' placeholder='Employee' required><button>Assign & Task</button></form></td></tr>"
        else:
            shelved_rows += f"<tr style='background:#e8f5e9'><td>{ucode}<br><img src='{qr}'></td><td>{sku}<br>{name}</td><td>{bin_loc}</td><td>{shelf} ✅</td></tr>"

    # Shelf Master
    shelf_master = ""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for s in shelves:
        c.execute("SELECT unique_code, sku FROM products WHERE shelf=?", (s[0],))
        items = c.fetchall()
        list_str = "<br>".join([f"{i[0]} ({i[1]})" for i in items]) or "Empty"
        shelf_master += f"<tr><td><b>{s[0]}</b><br>{s[1]}</td><td>{list_str}</td><td>{len(items)} items</td></tr>"
    conn.close()

    task_rows = "".join([f"<tr><td>{t[0]}<br>{t[1]}</td><td>{t[2]} -> {t[3]}</td><td>{t[4]}</td><td>{t[5]}</td></tr>" for t in tasks])

    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>body{{font-family:sans-serif;padding:10px;font-size:12px}} table{{width:100%;border-collapse:collapse;margin:8px 0}} td,th{{border:1px solid #ccc;padding:5px}}.head{{background:#0d47a1;color:white;padding:10px}} button{{background:#1565c0;color:white;border:none;padding:6px 8px;border-radius:4px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} @media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style></head><body>
    <div class='head'><h2>STORAGE - Item Level (Unique Code Tracking)</h2><p>SCAN unique code → Assign that specific item to shelf → Create task for employee</p></div>
    <div style='background:#fff3e0;padding:8px;margin:8px 0'><input id='scan' placeholder='SCAN UNIQUE CODE HERE e.g. TV-55-20251015-A7K9' style='width:70%;padding:8px'><button onclick="fetch('/api/get/'+document.getElementById('scan').value).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">Find Item</button></div>

    <h3>1. IN BIN - Needs Assignment (Scan & Assign Each Unique Item)</h3>
    <table><tr><th>Unique Code / QR</th><th>Name</th><th>BIN</th><th>Assign to Shelf</th></tr>{in_bin_rows or '<tr><td colspan=4>No items in BIN - Go to INTAKE</td></tr>'}</table>

    <h3>2. SHELVED - Already Assigned</h3>
    <table><tr><th>Unique Code</th><th>SKU</th><th>From BIN</th><th>Current Shelf</th></tr>{shelved_rows or '<tr><td colspan=4>None shelved yet</td></tr>'}</table>

    <div class='grid'>
    <div><h3>Shelf Master - What's Where (Prevents mixing)</h3><table><tr><th>Shelf</th><th>Unique Items Inside</th><th>Count</th></tr>{shelf_master}</table></div>
    <div><h3>Employee Put-Away Tasks</h3><table><tr><th>Unique Code</th><th>Move</th><th>Employee</th><th>Status</th></tr>{task_rows}</table></div>
    </div>
    </body></html>
    """

@app.post("/assign")
def assign(unique_code: str = Form(...), shelf_id: str = Form(...), employee: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT bin, sku FROM products WHERE unique_code=?", (unique_code,))
    row = c.fetchone()
    if not row:
        return HTMLResponse("Not found")
    bin_loc, sku = row
    c.execute("UPDATE products SET shelf=?, status='SHELVED' WHERE unique_code=?", (shelf_id, unique_code))
    c.execute("INSERT INTO tasks (unique_code, sku, from_bin, to_shelf, employee, status, time) VALUES (?,?,?,?,?,?,?)",
              (unique_code, sku, bin_loc, shelf_id, employee, f"PENDING: {employee} must move {unique_code} from {bin_loc} to {shelf_id}", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return HTMLResponse(f"<script>alert('Assigned {unique_code} to {shelf_id} - Task for {employee} created'); window.location.href='/';</script>")

@app.post("/api/move_internal")
async def move_internal(request: Request):
    data = await request.json()
    # Now accepts unique_code
    ucode = data.get("unique_code") or data.get("sku")+"-"+datetime.now().strftime("%H%M%S")
    sku = data.get("sku"); name = data.get("name", sku)
    bin_loc = data.get("bin","PLK-A-01-01"); weight = data.get("weight",0); dur = data.get("durability","")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO products (unique_code, sku, name, bin, shelf, status, weight, durability) VALUES (?,?,?,?,?,?,?,?)",
              (ucode, sku, name, bin_loc, None, "IN_BIN", weight, dur))
    conn.commit()
    conn.close()
    return {"ok": True, "unique_code": ucode}

@app.get("/api/get/{unique_code}")
def get_item(unique_code: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE unique_code=?", (unique_code,))
    item = c.fetchone()
    conn.close()
    return {"found": bool(item), "item": item}
