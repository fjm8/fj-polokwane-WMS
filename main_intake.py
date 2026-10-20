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
    conn.execute("CREATE TABLE IF NOT EXISTS items (code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin_loc TEXT, status TEXT, time TEXT)")
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
    trucks=conn.execute("SELECT id, plate, brand, driver, exp_date, exp_time, status, created FROM trucks ORDER BY exp_date ASC, exp_time ASC").fetchall()
    items=conn.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 20").fetchall()
    pending=conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    total=len(trucks)
    today_count=len([t for t in trucks if t[4]==today_str])
    delivered=len([t for t in trucks if t[6]=='DELIVERED'])
    conn.close()

    rows_html=""
    for t in trucks:
        # t = id, plate, brand, driver, exp_date, exp_time, status, created
        if t[6]=='DELIVERED': color="#d1e7dd"; badge="DELIVERED"
        elif t[4] < today_str and t[6]!='DELIVERED': color="#f8d7da"; badge=f"LATE - was {t[4]}"
        elif t[4]==today_str: color="#fff3cd"; badge=f"TODAY {t[5]}"
        else: color="#e7f3ff"; badge=f"{t[4]} {t[5]}"
        
        rows_html+=f"<tr style='background:{color}'><td><b>{t[1]}</b><br><small>{t[2]}</small></td><td>{t[3]}<br><small>{t[4]} {t[5]}</small><br><small>{badge}</small></td><td><b>{t[6]}</b></td><td><form method='post' action='/truck/status'><input type='hidden' name='id' value='{t[0]}'><select name='status'><option>EXPECTED</option><option>ARRIVED</option><option>OFFLOADING</option><option>DELIVERED</option></select><button style='padding:6px'>Update</button></form><form method='post' action='/truck/delete' onsubmit=\"return confirm('Delete {t[1]}?')\"><input type='hidden' name='id' value='{t[0]}'><button style='background:#dc3545;padding:6px;margin-top:3px'>X</button></form></td></tr>"

    item_rows="".join([f"<tr><td style='font-size:9px'>{r[0]}</td><td>{r[1]} {r[2]}</td><td>{r[3]}</td></tr>" for r in items])

    return f"""<html><head><meta name='viewport' content='width=device-width'><style>
    body{{font-family:sans-serif;padding:10px}} .top{{background:#0b5ed7;color:white;padding:10px}} input,select{{width:100%;padding:10px;margin:4px 0;box-sizing:border-box}} button{{width:100%;padding:12px;background:#0b5ed7;color:white;border:none;border-radius:4px}} table{{width:100%;border-collapse:collapse}} td{{border:1px solid #ccc;padding:6px;font-size:12px}} .card{{border:1px solid #ddd;padding:10px;margin:10px 0;border-radius:8px}} .kpi{{display:flex;gap:6px}} .kpi div{{flex:1;background:#f1f1f1;padding:8px;text-align:center;border-radius:6px}}
    </style></head><body>
    <div class='top'><h3>INTAKE - WMS Polokwane</h3><small>Pending to Storage: {pending}</small></div>
    <div class='kpi'><div><h2>{today_count}</h2>Today</div><div><h2>{total}</h2>All Enlisted</div><div style='background:#d1e7dd'><h2>{delivered}</h2>Delivered</div></div>

    <div class='card'><h4>🚚 Enlist Truck Plate + Delivery Time</h4>
    <form method='post' action='/truck/add'>
    <input name='plate' placeholder='Plate Number e.g. FT 45 XY GP' required style='text-transform:uppercase'>
    <input name='brand' placeholder='Truck Brand e.g. Scania' required>
    <input name='driver' placeholder='Driver Name / Phone'>
    <label>Expected Delivery Date:</label><input name='exp_date' type='date' required>
    <label>Expected Delivery Time:</label><input name='exp_time' type='time' required>
    <select name='status'><option>EXPECTED</option><option>ARRIVED</option><option>OFFLOADING</option><option>DELIVERED</option></select>
    <button>Enlist Truck</button>
    </form></div>

    <div class='card'><h4>Delivery Schedule - Sorted by Date/Time (No Mix-Up)</h4>
    <table><tr><th>Plate / Brand</th><th>When Supposed To Deliver</th><th>Status</th><th>Action</th></tr>{rows_html if rows_html else "<tr><td colspan=4>No trucks enlisted</td></tr>"}</table></div>

    <div class='card'><h4>📦 Items (last 20)</h4><table><tr><th>Code</th><th>Product</th><th>BIN</th></tr>{item_rows}</table></div>
    </body></html>"""

@app.post("/truck/add")
def truck_add(plate: str = Form(...), brand: str = Form(...), driver: str = Form(""), exp_date: str = Form(...), exp_time: str = Form(...), status: str = Form("EXPECTED")):
    conn=get_db()
    # check duplicate plate same day
    dup=conn.execute("SELECT plate FROM trucks WHERE plate=? AND exp_date=? AND status!='DELIVERED'", (plate.upper().strip(), exp_date)).fetchone()
    tid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO trucks VALUES (?,?,?,?,?,?,?,?)",(tid, plate.upper().strip(), brand, driver, exp_date, exp_time, status, datetime.now().isoformat()))
    conn.commit(); conn.close()
    warn = f"<script>alert('WARNING: Plate {plate.upper()} already enlisted for {exp_date} - possible mix-up!'); window.location.href='/'</script>" if dup else "<script>window.location.href='/'</script>"
    return HTMLResponse(warn)

@app.post("/truck/status")
def truck_status(id: str = Form(...), status: str = Form(...)):
    conn=get_db(); conn.execute("UPDATE trucks SET status=? WHERE id=?",(status,id)); conn.commit(); conn.close()
    return HTMLResponse("<script>window.location.href='/'</script>")

@app.post("/truck/delete")
def truck_delete(id: str = Form(...)):
    conn=get_db(); conn.execute("DELETE FROM trucks WHERE id=?",(id,)); conn.commit(); conn.close()
    return HTMLResponse("<script>window.location.href='/'</script>")

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    conn=get_db(); batch=[]
    for _ in range(qty):
        code=f"{sku}-{datetime.now().strftime('%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        conn.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)",(code,sku,name,bin,"IN_BIN",datetime.now().isoformat()))
        conn.execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?,?,?)",(code,sku,name,bin,0,datetime.now().isoformat()))
        batch.append({"unique_code":code,"sku":sku,"name":name,"bin":bin})
    conn.commit(); conn.close()
    def try_send():
        if send_to_storage(batch):
            c=get_db()
            for b in batch: c.execute("DELETE FROM pending WHERE code=?",(b["unique_code"],))
            c.commit(); c.close()
    threading.Thread(target=try_send, daemon=True).start()
    return HTMLResponse("<script>window.location.href='/'</script>")
