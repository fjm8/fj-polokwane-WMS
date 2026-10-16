from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime
from typing import List

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = "fj_storage.db"

def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS products (unique_code TEXT PRIMARY KEY, sku TEXT, name TEXT, bin TEXT, shelf TEXT, status TEXT, time TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS shelves (shelf_id TEXT PRIMARY KEY)")
    for s in ['A1','B1','B2','C1','D1']: c.execute("INSERT OR IGNORE INTO shelves VALUES (?)", (s,))
    conn.commit()
    conn.close()
init()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT unique_code, sku, name, bin FROM products WHERE status='IN_BIN' ORDER BY time DESC")
    in_bin = c.fetchall()
    c.execute("SELECT unique_code, sku, shelf FROM products WHERE status='SHELVED'")
    shelved = c.fetchall()
    conn.close()
    in_bin_rows = "".join([f"<tr><td><b>{u}</b><br>{s}<br><img src='https://api.qrserver.com/v1/create-qr-code/?size=50x50&data={u}'></td><td>{n}</td><td>{b}</td></tr>" for u,s,n,b in [(r[0],r[1],r[2],r[3]) for r in in_bin]])
    return f"<html><body style='font-family:sans-serif;padding:10px'><div style='background:#0d47a1;color:white;padding:10px'><h3>STORAGE - Items from INTAKE BIN</h3><p>Total IN BIN: {len(in_bin)} | SHELVED: {len(shelved)}</p></div><h3>IN BIN - Ready to Shelve (with QR)</h3><table border=1 style='width:100%;border-collapse:collapse'><tr><th>Unique Code / QR</th><th>Name</th><th>From BIN</th></tr>{in_bin_rows or '<tr><td colspan=3>No items yet - Check Intake</td></tr>'}</table></body></html>"

@app.post("/api/move_internal")
async def move_internal(request: Request):
    d = await request.json()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?,?,?)", (d.get("unique_code"), d.get("sku"), d.get("name"), d.get("bin"), None, "IN_BIN", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"ok": True, "code": d.get("unique_code")}

@app.post("/api/move_batch")
async def move_batch(request: Request):
    items = await request.json()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for d in items:
        c.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?,?,?)", (d.get("unique_code"), d.get("sku"), d.get("name"), d.get("bin"), None, "IN_BIN", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(items)}
