from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, datetime, os
app = FastAPI(title="FJ INTAKE")
DB = "fj_erp.db"
def db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, qty INTEGER DEFAULT 0, price REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, bin TEXT, qty INTEGER, type TEXT, ref TEXT, timestamp TEXT)")
    conn.execute("INSERT OR IGNORE INTO products VALUES ('TV-55-SAMSUNG','Samsung 55 TV',10,11999)")
    conn.commit()
    return conn

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><head><meta name=viewport content="width=device-width"><style>body{font-family:Arial;padding:15px;background:#e8f5e9}.card{background:white;padding:20px;border-radius:12px}button{background:#2e7d32;color:white;padding:12px;border:none;border-radius:8px;width:100%;font-weight:bold}input{padding:10px;width:95%;margin:5px}</style></head><body>
    <h1 style="color:#2e7d32">🟢 FJ INTAKE - Gate Receiving (Veldspaat)</h1>
    <div class=card><h3>1. Receive Truck - SCAN IN</h3>
    <form action=/api/move method=post>
    <input name=sku placeholder="SKU e.g. TV-55-SAMSUNG" required>
    <input name=bin placeholder="BIN e.g. PLK-A-01-01" required>
    <input name=qty type=number value=1 required>
    <input name=ref placeholder="GRN / Delivery Note">
    <button>RECEIVE STOCK -> QUEUED_FOR_SAP</button></form>
    <p>Employee: Security / Receiving ONLY</p></div></body></html>"""

@app.post("/api/move")
def move(sku:str=Form(...), bin:str=Form(...), qty:int=Form(...), ref:str=Form("")):
    conn=db(); conn.execute("INSERT OR IGNORE INTO products(sku,name) VALUES (?,?)",(sku,sku))
    conn.execute("UPDATE products SET qty=qty+? WHERE sku=?",(qty,sku))
    conn.execute("INSERT INTO movements(sku,bin,qty,type,ref,timestamp) VALUES (?,?,?,?,?,?)",(sku,bin,qty,"IN",ref or "QUEUED_FOR_SAP",datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()
    return HTMLResponse("<script>alert('IN OK - Sent to Storage');window.location='/'</script>")
