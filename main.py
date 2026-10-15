from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
import uuid
from datetime import datetime
import random

app = FastAPI(title="FJ INTAKE - Unique Code Generator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_erp.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_internal"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # New table: Every single item has unique code
    c.execute("""CREATE TABLE IF NOT EXISTS inventory_items 
                 (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, status TEXT, time TEXT, durability TEXT, weight INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS grn_log (grn TEXT PRIMARY KEY, time TEXT)""")
    conn.commit()
    conn.close()
init()

def make_unique_code(sku):
    # Format: SKU-DATE-4RANDOM e.g. TV-55-20251015-A7K9
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
        # QR Code API for scanning
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=80x80&data={code}"
        rows += f"<tr><td><b>{code}</b><br><img src='{qr_url}'><br><small>{sku}</small></td><td>{name}</td><td>{bin_loc}</td><td>{status}</td><td><a href='/scan/{code}' target='_blank'>View/Scan</a></td></tr>"

    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
    <script src='https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js'></script>
    <style>body{{font-family:sans-serif;padding:12px;font-size:12px}} table{{width:100%;border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px}} .head{{background:#2e7d32;color:white;padding:12px}} input,select{{padding:8px;width:100%;margin:4px 0}} button{{background:#2e7d32;color:white;border:none;padding:10px;border-radius:5px;width:100%}} .scan-box{{background:#fff3e0;padding:10px;border:2px dashed #ff9800;margin:10px 0}}</style></head><body>
    <div class='head'><h2>🟢 INTAKE - Unique Scannable Codes</h2><p>Every single product gets its own unique code for scanning</p></div>

    <div class='scan-box'>
    <h3>SCAN PRODUCT HERE</h3>
    <input id='scanInput' placeholder='Scan barcode / QR here (unique code)' onkeypress="if(event.key==='Enter'){{window.location.href='/scan/'+this.value}}">
    <button onclick="window.location.href='/scan/'+document.getElementById('scanInput').value">Identify Product</button>
    </div>

    <h3>Receive New Stock (Gate)</h3>
    <form method='post' action='/receive'>
        <input name='sku' placeholder='SKU e.g. TV-55-SAMSUNG' required>
        <input name='name' placeholder='Product Name e.g. Samsung 55 inch TV' required>
        <input name='qty' type='number' placeholder='Qty e.g. 5' required>
        <input name='bin' placeholder='BIN e.g. PLK-A-01-01' value='PLK-A-01-01' required>
        <select name='durability'><option value='Durable'>Durable</option><option value='Fragile'>Fragile</option></select>
        <input name='weight' type='number' placeholder='Weight per item kg' value='10'>
        <input name='grn' placeholder='GRN Number' required>
        <button type='submit'>Generate { '{' } qty { '}' } Unique Scannable Codes</button>
    </form>

    <h3>Last 100 Items Generated - Each has UNIQUE code (Print labels from here)</h3>
    <table><tr><th>Unique Code / QR + Barcode</th><th>Name</th><th>BIN</th><th>Status</th><th>Action</th></tr>{rows}</table>

    <script>JsBarcode('.barcode').init();</script>
    </body></html>
    """

@app.post("/receive")
def receive(sku: str = Form(...), name: str = Form(...), qty: int = Form(...), bin: str = Form(...), grn: str = Form(...), durability: str = Form(...), weight: int = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO grn_log VALUES (?,?)", (grn, datetime.now().isoformat()))
    
    generated = []
    for _ in range(qty):
        unique_code = make_unique_code(sku)
        # Ensure unique
        while True:
            c.execute("SELECT unique_code FROM inventory_items WHERE unique_code=?", (unique_code,))
            if not c.fetchone():
                break
            unique_code = make_unique_code(sku)
        
        c.execute("INSERT INTO inventory_items (unique_code, sku, name, bin, status, time, durability, weight) VALUES (?,?,?,?,?,?,?,?)",
                  (unique_code, sku, name, bin, "IN_BIN", datetime.now().isoformat(), durability, weight))
        generated.append(unique_code)

        # Forward to STORAGE as individual item
        try:
            requests.post(STORAGE_URL, json={"unique_code": unique_code, "sku": sku, "name": name, "qty": 1, "bin": bin, "weight": weight, "durability": durability}, timeout=2)
        except:
            pass

    conn.commit()
    conn.close()
    
    codes_html = "<br>".join([f"{code} <img src='https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={code}'>" for code in generated])
    return HTMLResponse(f"<html><body><h2>Generated {qty} Unique Codes for {sku}</h2><p>{codes_html}</p><br><a href='/'>Back to INTAKE</a><script>setTimeout(()=>window.location.href='/', 5000)</script></body></html>")

@app.get("/scan/{unique_code}", response_class=HTMLResponse)
def scan(unique_code: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT unique_code, sku, name, bin, status, time, durability, weight FROM inventory_items WHERE unique_code=?", (unique_code,))
    item = c.fetchone()
    conn.close()
    if not item:
        return HTMLResponse(f"<h2>Code {unique_code} NOT FOUND</h2><a href='/'>Back</a>")
    
    code, sku, name, bin_loc, status, time, dur, weight = item
    qr = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={code}"
    return f"""
    <html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{font-family:sans-serif;padding:20px;text-align:center}}.card{{border:3px solid #2e7d32;padding:20px;border-radius:10px;max-width:400px;margin:auto}}</style></head><body>
    <div class='card'>
    <h2>✅ PRODUCT IDENTIFIED</h2>
    <img src='{qr}'><br><br>
    <h1 style='background:yellow;padding:10px'>{code}</h1>
    <p><b>SKU:</b> {sku}</p>
    <p><b>Name:</b> {name}</p>
    <p><b>BIN:</b> {bin_loc}</p>
    <p><b>Status:</b> {status}</p>
    <p><b>Type:</b> {dur} / {weight}kg</p>
    <p><b>Received:</b> {time}</p>
    <hr>
    <p>This unique code belongs to ONE specific item. If there are 10x {sku}, this is 1 of 10.</p>
    <p>You can now assign THIS specific item to a specific shelf.</p>
    <a href='/'>Back to INTAKE</a>
    </div></body></html>
    """

@app.get("/api/item/{{unique_code}}")
def api_item(unique_code: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory_items WHERE unique_code=?", (unique_code,))
    item = c.fetchone()
    conn.close()
    return {"item": item}
