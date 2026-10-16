from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uuid
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj.db"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS items (code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin_loc TEXT, status TEXT, time TEXT)")
    conn.commit()
    conn.close()
init()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    html_rows = ""
    for code, sku, name, bin_loc in rows:
        html_rows += f"<tr><td><b>{code}</b><br><img src='https://api.qrserver.com/v1/create-qr-code/?size=80x80&data={code}'></td><td>{sku}<br>{name}</td><td>{bin_loc}</td></tr>"
    return f"""
    <html><head><meta name='viewport' content='width=device-width'><style>body{{font-family:sans-serif;padding:12px}} .top{{background:green;color:white;padding:12px}} input{{width:100%;padding:10px;margin:5px 0}} button{{width:100%;padding:12px;background:green;color:white;border:none;font-size:16px}} td{{border:1px solid #ccc;padding:6px;font-size:12px}}</style></head><body>
    <div class='top'><h2>INTAKE - WMS 2</h2><p>Generates Unique QR per item</p></div>
    <form method='post' action='/receive'>
    <input name='sku' placeholder='SKU' required>
    <input name='name' placeholder='Product Name' required>
    <input name='qty' type='number' placeholder='Qty' required>
    <input name='bin' placeholder='BIN' value='PLK-A-01-01' required>
    <button type='submit'>Generate</button>
    </form>
    <h3>Last Items</h3><table style='width:100%;border-collapse:collapse'><tr><th>Unique Code</th><th>Product</th><th>BIN</th></tr>{html_rows}</table>
    </body></html>
    """

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for i in range(qty):
        code = f"{sku}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        c.execute("INSERT INTO items VALUES (?,?,?,?,?,?)", (code, sku, name, bin, "IN_BIN", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return HTMLResponse(f"<script>alert('Created {qty} unique QR codes for {sku}'); window.location.href='/';</script>")
