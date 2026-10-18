from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, uuid, requests
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB = "fj.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_batch"

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS items (code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin_loc TEXT, status TEXT, time TEXT)")
    return conn

@app.get("/", response_class=HTMLResponse)
def home():
    conn = get_db()
    rows = conn.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 50").fetchall()
    conn.close()
    tr = "".join([f"<tr><td style='font-size:9px'>{r[0]}<br><img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={r[0]}'></td><td>{r[1]}<br>{r[2]}</td><td>{r[3]}</td></tr>" for r in rows])
    return f"""<html><head><meta name='viewport' content='width=device-width'><style>
    body{{font-family:sans-serif;padding:10px}}.top{{background:#0b5ed7;color:white;padding:10px}}input{{width:100%;padding:12px;margin:6px 0}}button{{width:100%;padding:14px;background:#0b5ed7;color:white;border:none}}table{{width:100%;border-collapse:collapse}}td{{border:1px solid #ccc;padding:5px;font-size:12px}}
    </style></head><body><div class='top'><h3>INTAKE - WMS Polokwane</h3></div>
    <form method='post' action='/receive'><input name='sku' placeholder='SKU' required><input name='name' placeholder='Product Name' required><input name='qty' type='number' value='1' required><input name='bin' value='PLK-A-01-01' required><button>Generate & Save</button></form>
    <table><tr><th>Code</th><th>Product</th><th>BIN</th></tr>{tr}</table></body></html>"""

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    conn = get_db()
    batch=[]
    for _ in range(qty):
        code=f"{sku}-{datetime.now().strftime('%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        conn.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)",(code,sku,name,bin,"IN_BIN",datetime.now().isoformat()))
        batch.append({"unique_code":code,"sku":sku,"name":name,"bin":bin})
    conn.commit(); conn.close()
    try: requests.post(STORAGE_URL, json=batch, timeout=10)
    except: pass
    return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:20px'><h2>Saved {qty} items</h2><a href='/'>Go Back to Intake</a></body></html>")
