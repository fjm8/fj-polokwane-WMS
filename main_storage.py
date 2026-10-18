from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
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

@app.post("/api/move_batch")
async def move_batch(request: Request):
    data = await request.json()
    if not data:
        return {"status": "empty"}
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # data can be list or single
    items = data if isinstance(data, list) else [data]
    for item in items:
        code = item.get("unique_code") or item.get("code")
        sku = item.get("sku", "")
        name = item.get("name", "")
        bin_loc = item.get("bin") or item.get("bin_loc") or "PLK-A-01-01"
        if code:
            c.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)", (code, sku, name, bin_loc, "IN_BIN", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "ok", "count": len(items)}

@app.post("/api/move_internal")
async def move_internal(request: Request):
    return await move_batch(request)

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT code, sku, name, bin_loc FROM items ORDER BY time DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    html = ""
    for code, sku, name, bin_loc in rows:
        html += f"<tr><td>{code}</td><td>{sku} {name}</td><td>{bin_loc}</td></tr>"
    return f"<html><body><h2>STORAGE - Stock</h2><table border=1 style='width:100%'><tr><th>Code</th><th>Product</th><th>BIN</th></tr>{html}</table></body></html>"
