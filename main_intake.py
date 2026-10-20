from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, uuid, requests, threading, time
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB = "fj.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_batch"
STORAGE_WAKE_URL = "https://fj-polokwane-storage.onrender.com/"

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS items (code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin_loc TEXT, qty INTEGER, truck_plate TEXT, status TEXT, time TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS pending (code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin_loc TEXT, tries INTEGER, last_try TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS trucks (id TEXT PRIMARY KEY, plate TEXT, brand TEXT, driver TEXT, exp_date TEXT, exp_time TEXT, status TEXT, created TEXT)")
    return conn

def send_to_storage(batch):
    try: requests.get(STORAGE_WAKE_URL, timeout=15)
    except: pass
    for _ in range(3):
        try:
            r = requests.post(STORAGE_URL, json=batch, timeout=20)
            if r.status_code == 200: return True
        except: time.sleep(2)
    return False

def retry_loop():
    while True:
        time.sleep(60)
        try:
            conn=get_db()
            rows=conn.execute("SELECT code, sku, name, bin_loc FROM pending LIMIT 20").fetchall()
            if rows:
                batch=[{"unique_code":r[0],"sku":r[1],"name":r[2],"bin":r[3]} for r in rows]
                if send_to_storage(batch):
                    for r in rows: conn.execute("DELETE FROM pending WHERE code=?",(r[0],))
                    conn.commit()
            conn.close()
        except: pass
threading.Thread(target=retry_loop, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def home():
    conn=get_db()
    trucks=conn.execute("SELECT id, plate, brand, driver, exp_date, exp_time, status FROM trucks ORDER BY exp_date ASC, exp_time ASC").fetchall()
    items=conn.execute("SELECT code, sku, name, bin_loc, truck_plate, time FROM items ORDER BY time DESC LIMIT 50").fetchall()
    pending=conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    truck_options = "".join([f"<option value='{t[1]}'>{t[1]} - {t[2]} ({t[5]})</option>" for t in trucks if t[5]!='DELIVERED'])
    if not truck_options:
        truck_options = "<option value=''>No trucks enlisted - add truck first</option>"

    truck_rows=""
    for t in trucks:
        if t[5]=='DELIVERED': color="#d1e7dd"
        elif t[3] < today_str and t[5]!='DELIVERED': color="#f8d7da"
        elif t[3]==today_str: color="#fff3cd"
        else: color="#e7f3ff"
        truck_rows+=f"<tr style='background:{color}'><td><b>{t[1]}</b><br><small>{t[2]}</small></td><td>{t[3]} {t[4]}<br><small>{t[3]}</small></td><td><b>{t[5]}</b></td><td><form method='post' action='/truck/status'><input type='hidden' name='id' value='{t[0]}'><select name='status'><option>EXPECTED</option><option>ARRIVED</option><option>OFFLOADING</option><option>DELIVERED</option></select><button style='padding:5px'>Update</button></form></td></tr>"

    item_rows=""
    for r in items:
        item_rows+=f"<tr><td style='font-size:9px'>{r[0]}<br><img src='https://api.qrserver.com/v1/create-qr-code/?size=70x70&data={r[0]}'><br>{r[4]}</td><td>{r[1]}<br>{r[2]}</td><td>{r[3]}<br><small>{r[5][:16]}</small></td></tr>"

    conn.close()
    return f"""<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>
    body{{font-family:sans-serif;padding:8px;margin:0}} .top{{background:#0b5ed7;color:white;padding:12px;position:sticky;top:0}} input,select{{width:100%;padding:11px;margin:4px 0;box-sizing:border-box;border:1px solid #ccc;border-radius:4px}} button{{width:100%;padding:13px;background:#0b5ed7;color:white;border:none;border-radius:6px;font-weight:bold}} table{{width:100%;border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px;font-size:12px;text-align:left}} .card{{border:1px solid #ddd;padding:10px;margin:10px 0;border-radius:8px;background:white}} .kpi{{display:flex;gap:6px}} .kpi div{{flex:1;background:#f1f1f1;padding:8px;text-align:center;border-radius:6px}} h4{{margin:8px 0}}
    </style></head><body>
    <div class='top'><h3 style='margin:0'>INTAKE - WMS Polokwane [FULL]</h3><small>Pending to Storage: {pending} | Auto-retry ON</small></div>

    <div class='card'><h4>🚚 1. Enlist Truck (Plate + Expected Date/Time)</h4>
    <form method='post' action='/truck/add'>
    <input name='plate' placeholder='Plate e.g. FT 45 XY GP' required>
    <input name='brand' placeholder='Brand e.g. Scania' required>
    <input name='driver' placeholder='Driver / Phone'>
    <label>Date:</label><input name='exp_date' type='date' required>
    <label>Time:</label><input name='exp_time' type='time' required>
    <button style='background:#198754'>+ Enlist Truck</button></form>
    <table><tr><th>Plate/Brand</th><th>Expected</th><th>Status</th><th>Action</th></tr>{truck_rows if truck_rows else "<tr><td colspan=4>No trucks</td></tr>"}</table></div>

    <div class='card' style='border:2px solid #0b5ed7'><h4>📦 2. Enter Stock That Was Delivered (Barcode + Bin)</h4>
    <p><small>Select which truck delivered, then enter product. It will generate barcode, save to bin, and auto-send to Storage.</small></p>
    <form method='post' action='/receive'>
    <label>Truck that delivered (important):</label><select name='truck_plate' required>{truck_options}</select>
    <input name='sku' placeholder='SKU e.g. MAIZE-25KG' required>
    <input name='name' placeholder='Product Name e.g. Maize Meal 25kg' required>
    <input name='qty' type='number' min='1' value='1' required placeholder='Quantity'>
    <input name='bin' value='PLK-A-01-01' required placeholder='BIN Location'>
    <button>Generate Barcode & Save Stock</button></form>
    <p><small>It will: 1) Generate unique code + QR 2) Save in INTAKE 3) Send to Storage bin automatically</small></p></div>

    <div class='card'><h4>📋 What is in BIN / What was Delivered (Last 50)</h4>
    <table><tr><th>Barcode / Truck</th><th>Product</th><th>BIN / Time</th></tr>{item_rows if item_rows else "<tr><td colspan=3>No stock yet</td></tr>"}</table></div>
    <p><a href='/status'>System Status</a> | <a href='/retry_now'>Force Send Pending to Storage Now</a></p>
    </body></html>"""

@app.post("/truck/add")
def truck_add(plate: str = Form(...), brand: str = Form(...), driver: str = Form(""), exp_date: str = Form(...), exp_time: str = Form(...)):
    conn=get_db()
    tid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO trucks VALUES (?,?,?,?,?,?,?,?)",(tid, plate.upper().strip(), brand, driver, exp_date, exp_time, "EXPECTED", datetime.now().isoformat()))
    conn.commit(); conn.close()
    return HTMLResponse("<script>window.location.href='/'</script>")

@app.post("/truck/status")
def truck_status(id: str = Form(...), status: str = Form(...)):
    conn=get_db(); conn.execute("UPDATE trucks SET status=? WHERE id=?",(status,id)); conn.commit(); conn.close()
    return HTMLResponse("<script>window.location.href='/'</script>")

@app.post("/receive")
def receive(truck_plate: str = Form(...), sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    conn=get_db(); batch=[]
    for _ in range(qty):
        code=f"{sku}-{datetime.now().strftime('%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        conn.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?)",(code,sku,name,bin,qty,truck_plate,"IN_BIN",datetime.now().isoformat()))
        conn.execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?,?,?)",(code,sku,name,bin,0,datetime.now().isoformat()))
        batch.append({"unique_code":code,"sku":sku,"name":name,"bin":bin})
    conn.commit(); conn.close()
    def try_send():
        if send_to_storage(batch):
            c=get_db()
            for b in batch: c.execute("DELETE FROM pending WHERE code=?",(b["unique_code"],))
            c.commit(); c.close()
    threading.Thread(target=try_send, daemon=True).start()
    return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:20px'><h2>✅ {qty} x {name} saved!</h2><p>Truck: {truck_plate}<br>BIN: {bin}<br>Barcodes generated + queued to Storage.</p><a href='/'>Go Back</a></body></html>")

@app.get("/status")
def status():
    conn=get_db(); pending=conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]; conn.close()
    return {"pending_to_storage": pending, "storage_url": STORAGE_URL}

@app.get("/retry_now")
def retry_now():
    conn=get_db(); rows=conn.execute("SELECT code, sku, name, bin_loc FROM pending LIMIT 50").fetchall(); conn.close()
    if not rows: return {"msg":"No pending"}
    batch=[{"unique_code":r[0],"sku":r[1],"name":r[2],"bin":r[3]} for r in rows]
    ok=send_to_storage(batch)
    if ok:
        c=get_db()
        for r in rows: c.execute("DELETE FROM pending WHERE code=?",(r[0],))
        c.commit(); c.close()
    return {"tried": len(rows), "success": ok}
