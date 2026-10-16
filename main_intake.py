from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, requests, uuid
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"
STORAGE_URL_SINGLE = "https://fj-polokwane-storage.onrender.com/api/move_internal"
STORAGE_URL_BATCH = "https://fj-polokwane-storage.onrender.com/api/move_batch"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS inventory_items (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, status TEXT, time TEXT)")
    conn.commit()
    conn.close()
init()

def make_code(sku): return f"{sku}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT unique_code, sku, name, bin, status FROM inventory_items ORDER BY time DESC LIMIT 50")
    items = c.fetchall()
    conn.close()
    rows = "".join([f"<tr><td><b>{i[0]}</b><br><img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={i[0]}'></td><td>{i[1]}<br>{i[2]}</td><td>{i[3]}</td><td>{i[4]}</td></tr>" for i in items])
    return f"""<html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;padding:10px;font-size:13px}} td{{border:1px solid #ccc;padding:6px}}.head{{background:green;color:white;padding:10px}} input{{width:100%;padding:8px;margin:4px 0}} button{{width:100%;padding:10px;background:green;color:white;border:none}}</style></head><body><div class='head'><h3>INTAKE - Unique QR Generator</h3><p>Generates 1 QR per item, then sends to STORAGE</p></div><form method='post' action='/receive'><input name='sku' placeholder='SKU e.g. D5-FRIDGE' required><input name='name' placeholder='Name' required><input name='qty' type='number' placeholder='Qty' required><input name='bin' value='PLK-A-01-01' required><input name='grn' placeholder='GRN' required><button>Generate & Send to Storage</button></form><h3>Generated</h3><table><tr><th>Unique Code / QR</th><th>Product</th><th>BIN</th><th>Status</th></tr>{rows}</table></body></html>"""

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...), grn: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    batch = []
    for _ in range(qty):
        code = make_code(sku)
        c.execute("INSERT INTO inventory_items VALUES (?,?,?,?,?,?)", (code, sku, name, bin, "IN_BIN", datetime.now().isoformat()))
        batch.append({"unique_code": code, "sku": sku, "name": name, "bin": bin})
    conn.commit()
    conn.close()
    # SEND TO STORAGE - TRY BATCH FIRST
    try:
        requests.post(STORAGE_URL_BATCH, json=batch, timeout=10)
    except:
        # Fallback to single
        for item in batch:
            try: requests.post(STORAGE_URL_SINGLE, json=item, timeout=5)
            except: pass
    return HTMLResponse(f"<script>alert('Generated {qty} QRs and sent to STORAGE BIN {bin}'); window.location.href='/';</script>")
