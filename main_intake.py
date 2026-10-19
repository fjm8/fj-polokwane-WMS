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
    return conn

def send_to_storage(batch):
    # 1. Wake storage first (free tier sleeps)
    try:
        requests.get(STORAGE_WAKE_URL, timeout=15)
    except:
        pass
    # 2. Try send 3 times
    for attempt in range(3):
        try:
            r = requests.post(STORAGE_URL, json=batch, timeout=20)
            if r.status_code == 200:
                return True
        except:
            time.sleep(2)
    return False

def retry_pending_loop():
    while True:
        try:
            time.sleep(60)  # retry every 60 sec
            conn = get_db()
            rows = conn.execute("SELECT code, sku, name, bin_loc FROM pending LIMIT 20").fetchall()
            if not rows:
                conn.close()
                continue
            batch = [{"unique_code": r[0], "sku": r[1], "name": r[2], "bin": r[3]} for r in rows]
            if send_to_storage(batch):
                # success - clear pending
                for r in rows:
                    conn.execute("DELETE FROM pending WHERE code=?", (r[0],))
                conn.commit()
            else:
                # update tries
                for r in rows:
                    conn.execute("UPDATE pending SET tries=tries+1, last_try=? WHERE code=?", (datetime.now().isoformat(), r[0]))
                conn.commit()
            conn.close()
        except:
            pass

# Start background retry thread once
threading.Thread(target=retry_pending_loop, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = get_db()
    rows = conn.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 50").fetchall()
    pending_count = conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    conn.close()
    tr = "".join([f"<tr><td style='font-size:9px'>{r[0]}<br><img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={r[0]}'></td><td>{r[1]}<br>{r[2]}</td><td>{r[3]}</td></tr>" for r in rows])
    return f"""<html><head><meta name='viewport' content='width=device-width'><style>
    body{{font-family:sans-serif;padding:10px}}.top{{background:#0b5ed7;color:white;padding:10px}}input{{width:100%;padding:12px;margin:6px 0}}button{{width:100%;padding:14px;background:#0b5ed7;color:white;border:none}}table{{width:100%;border-collapse:collapse}}td{{border:1px solid #ccc;padding:5px;font-size:12px}}.warn{{background:#fff3cd;padding:8px;margin:8px 0}}
    </style></head><body><div class='top'><h3>INTAKE - WMS Polokwane</h3><small>Pending to Storage: {pending_count} | Auto-retry ON</small></div>
    <form method='post' action='/receive'><input name='sku' placeholder='SKU' required><input name='name' placeholder='Product Name' required><input name='qty' type='number' value='1' required><input name='bin' value='PLK-A-01-01' required><button>Generate & Save</button></form>
    <div class='warn'>If Storage is sleeping, item will be queued and sent automatically within 60 sec. Check <a href='/status'>/status</a></div>
    <table><tr><th>Code</th><th>Product</th><th>BIN</th></tr>{tr}</table></body></html>"""

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    conn = get_db()
    batch=[]
    for _ in range(qty):
        code=f"{sku}-{datetime.now().strftime('%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        conn.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)",(code,sku,name,bin,"IN_BIN",datetime.now().isoformat()))
        conn.execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?,?,?)",(code,sku,name,bin,0,datetime.now().isoformat()))
        batch.append({"unique_code":code,"sku":sku,"name":name,"bin":bin})
    conn.commit(); conn.close()

    # try immediately in background
    def try_send():
        if send_to_storage(batch):
            c = get_db()
            for b in batch:
                c.execute("DELETE FROM pending WHERE code=?",(b["unique_code"],))
            c.commit(); c.close()
    threading.Thread(target=try_send, daemon=True).start()

    return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:20px'><h2>Saved {qty} items - queued to Storage</h2><p>Even if Storage is sleeping, it will auto-send in 60 sec.</p><a href='/'>Go Back to Intake</a><br><br><a href='/status'>Check Status</a></body></html>")

@app.get("/status")
def status():
    conn = get_db()
    pending = conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    conn.close()
    try:
        r = requests.get(STORAGE_WAKE_URL, timeout=15)
        storage_ok = f"OK - {r.status_code}"
    except Exception as e:
        storage_ok = f"DOWN / Sleeping - {e}"
    return {"intake": "running", "pending_queue": pending, "storage_url": STORAGE_URL, "storage_status": storage_ok, "auto_retry": "every 60 sec ON"}

@app.get("/retry_now")
def retry_now():
    conn = get_db()
    rows = conn.execute("SELECT code, sku, name, bin_loc FROM pending LIMIT 50").fetchall()
    conn.close()
    if not rows:
        return {"msg": "No pending"}
    batch = [{"unique_code": r[0], "sku": r[1], "name": r[2], "bin": r[3]} for r in rows]
    ok = send_to_storage(batch)
    if ok:
        c = get_db()
        for r in rows:
            c.execute("DELETE FROM pending WHERE code=?",(r[0],))
        c.commit(); c.close()
    return {"sent": len(rows), "success": ok}
