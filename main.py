from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
import uuid
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_internal"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS inventory_items (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, status TEXT, time TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS grn_log (grn TEXT PRIMARY KEY, time TEXT)")
    conn.commit()
    conn.close()
init()

def make_unique_code(sku):
    date = datetime.now().strftime("%Y%m%d")
    rand = str(uuid.uuid4())[:4].upper()
    return f"{sku}-{date}-{rand}"

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT unique_code, sku, name, bin, status, time FROM inventory_items ORDER BY time DESC LIMIT 100")
    items = c.fetchall()
    conn.close()
    rows = ""
    for code, sku, name, bin_loc, status, time in items:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=80x80&data={code}"
        rows += f"<tr><td><b>{code}</b><br><img src='{qr_url}'><br><small>{sku}</small></td><td>{name}</td><td>{bin_loc}</td><td>{status}</td></tr>"
    return f"""
    <html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;padding:12px;font-size:12px}} table{{width:100%;border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px}} .head{{background:#2e7d32;color:white;padding:12px}} input{{padding:8px;width:100%;margin:4px 0}} button{{background:#2e7d32;color:white;border:none;padding:10px;width:100%;border-radius:5px}}</style></head><body>
    <div class='head'><h2>INTAKE - Unique Code Generator</h2></div>
    <form method='post' action='/receive'><input name='sku' placeholder='SKU e.g. TV-55' required><input name='name' placeholder='Product Name' required><input name='qty' type='number' placeholder='Qty' required><input name='bin' placeholder='BIN' value='PLK-A-01-01' required><input name='grn' placeholder='GRN' required><button>Generate Unique Codes</button></form>
    <h3>Last Items - Each has UNIQUE code</h3><table><tr><th>Unique Code / QR</th><th>Name</th><th>BIN</th><th>Status</th></tr>{rows}</table></body></html>
    """

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...), grn: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO grn_log VALUES (?,?)", (grn, datetime.now().isoformat()))
    for _ in range(qty):
        unique_code = make_unique_code(sku)
        c.execute("INSERT INTO inventory_items VALUES (?,?,?,?,?,?)", (unique_code, sku, name, bin, "IN_BIN", datetime.now().isoformat()))
        try:
            requests.post(STORAGE_URL, json={{"unique_code": unique_code, "sku": sku, "name": name, "qty": 1, "bin": bin}}, timeout=2)
        except:
            pass
    conn.commit()
    conn.close()
    return HTMLResponse(f"<script>alert('Generated {qty} unique codes'); window.location.href='/';</script>")
