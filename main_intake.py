from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uuid
from datetime import datetime
import requests

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
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 50")
        rows = c.fetchall()
        conn.close()
    except:
        rows = []
    
    html_rows = ""
    for code, sku, name, bin_loc in rows:
        html_rows += f"<tr><td style='font-size:10px'>{code}<br><img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={code}'></td><td>{sku}<br>{name}</td><td>{bin_loc}</td></tr>"

    return f"""
    <html><head><meta name='viewport' content='width=device-width'><style>
    body{{font-family:sans-serif;padding:10px}} .top{{background:#0b5ed7;color:white;padding:10px}} input{{width:100%;padding:12px;margin:6px 0;box-sizing:border-box}} button{{width:100%;padding:14px;background:#0b5ed7;color:white;border:none;font-size:16px}}
    table{{width:100%;border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:5px;font-size:12px}}
    </style></head><body>
    <div class='top'><h3>INTAKE - WMS Polokwane</h3><small>Invoice PAUSED</small></div>
    <form method='post' action='/receive'>
    <input name='sku' placeholder='SKU (e.g. B123)' required>
    <input name='name' placeholder='Product Name' required>
    <input name='qty' type='number' value='1' min='1' required>
    <input name='bin' placeholder='BIN' value='PLK-A-01-01' required>
    <button type='submit'>Generate & Save</button>
    </form>
    <h4>Last Items ({len(rows)})</h4>
    <table><tr><th>Code / QR</th><th>Product</th><th>BIN</th></tr>{html_rows}</table>
    </body></html>
    """

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...)):
    try:
        conn = get_db()
        c = conn.cursor()
        batch = []
        for i in range(qty):
            code = f"{sku}-{datetime.now().strftime('%m%d')}-{str(uuid.uuid4())[:4].upper()}"
            c.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)", (code, sku, name, bin, "IN_BIN", datetime.now().isoformat()))
            batch.append({"unique_code": code, "sku": sku, "name": name, "bin": bin})
        conn.commit()
        conn.close()

        # Try to push to storage - if it fails, still ok, intake saved
        try:
            requests.post(STORAGE_URL, json=batch, timeout=8)
        except:
            pass

        return HTMLResponse(f"<html><body><h3>Created {qty} items OK</h3><p>SKU: {sku}</p><a href='/'>Back to Intake</a><br><br><a href='https://fj-polokwane-storage.onrender.com' target='_blank'>Go to Storage</a></body></html>")
    except Exception as e:
        return HTMLResponse(f"<html><body><h3>Error: {str(e)}</h3><a href='/'>Back</a></body></html>", status_code=500)
