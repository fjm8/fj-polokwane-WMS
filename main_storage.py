from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
app = FastAPI(title="FJ STORAGE")
DB = "fj_erp.db"
def db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, qty INTEGER DEFAULT 0, price REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, bin TEXT, qty INTEGER, type TEXT, ref TEXT, timestamp TEXT)")
    conn.commit()
    return conn
@app.get("/", response_class=HTMLResponse)
def home():
    conn=db()
    prods = conn.execute("SELECT sku,name,qty FROM products").fetchall()
    moves = conn.execute("SELECT sku,bin,qty,type,ref,timestamp FROM movements ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    p_html = "".join([f"<tr><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td></tr>" for p in prods])
    m_html = "".join([f"<tr><td>{m[0]}</td><td>{m[1]}</td><td>{m[2]}</td><td>{m[3]}</td><td>{m[4]}</td></tr>" for m in moves])
    return f"""<html><head><meta name=viewport content="width=device-width"><style>body{{font-family:Arial;padding:15px;background:#e3f2fd}}.card{{background:white;padding:15px;border-radius:10px;margin-bottom:10px}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:6px;font-size:12px}}</style></head><body>
    <h1 style="color:#1565c0">🔵 FJ STORAGE - Warehouse (Veldspaat)</h1>
    <div class=card><h3>Live Stock by BIN</h3><table><tr><th>SKU</th><th>Name</th><th>Qty</th></tr>{p_html}</table></div>
    <div class=card><h3>Last 20 Movements</h3><table><tr><th>SKU</th><th>BIN</th><th>Qty</th><th>Type</th><th>Ref</th></tr>{m_html}</table></div>
    <p>Employee: Forklift / Warehouse ONLY - No selling</p></body></html>"""
