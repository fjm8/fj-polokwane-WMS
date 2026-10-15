from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, requests, uuid
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_internal"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS inventory_items (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, status TEXT, time TEXT)")
    conn.commit()
    conn.close()
init()

def make_code(sku):
    return f"{sku}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT unique_code, sku, name, bin, status FROM inventory_items ORDER BY time DESC LIMIT 50")
    items = c.fetchall()
    conn.close()
    rows = "".join([f"<tr><td><b>{i[0]}</b><br><img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={i[0]}'></td><td>{i[1]}<br>{i[2]}</td><td>{i[3]}</td><td>{i[4]}</td></tr>" for i in items])
    return f"""
    <html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;padding:10px;font-size:13px}} table{{width:100%;border-collapse:collapse}} td{{border:1px solid #ccc;padding:6px}}.head{{background:green;color:white;padding:10px}} input{{width:100%;padding:8px;margin:4px 0}} button{{width:100%;padding:10px;background:green;color:white;border:none}}</style></head><body>
    <div class='head'><h3>INTAKE - Unique Code Generator</h3></div>
    <form method='post' action='/receive'><input name='sku' placeholder='SKU e.g. TV-55' required><input name='name' placeholder='Product Name e.g. Samsung TV' required><input name='qty' type='number' placeholder='Quantity e.g. 5' required><input name='bin' value='PLK-A-01-01' required><input name='grn' placeholder='GRN No' required><button>Generate Unique Codes</button></form>
    <h3>Generated Codes (Each Item = 1 Code)</h3><table><tr><th>Unique Code</th><th>Product</th><th>BIN</th><th>Status</th></tr>{rows}</table></body></html>"""

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...), grn: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for _ in range(qty):
        code = make_code(sku)
        c.execute("INSERT INTO inventory_items VALUES (?,?,?,?,?,?)", (code, sku, name, bin, "IN_BIN", datetime.now().isoformat()))
        try: requests.post(STORAGE_URL, json={"unique_code": code, "sku": sku, "name": name, "bin": bin}, timeout=2)
        except: pass
    conn.commit()
    conn.close()
    return HTMLResponse(f"<script>alert('Generated {qty} unique codes for {sku}'); window.location.href='/';</script>")
