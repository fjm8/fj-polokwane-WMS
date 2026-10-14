from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, datetime, requests
from pydantic import BaseModel

app = FastAPI(title="FJ POS")
DB = "fj_erp.db"
STORAGE_URL = "https://fj-polokwane-storage.onrender.com/api/move_internal"

class SaleData(BaseModel):
    sku: str
    qty: int

def db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, qty INTEGER DEFAULT 0, price REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, bin TEXT, qty INTEGER, type TEXT, ref TEXT, timestamp TEXT)")
    conn.execute("INSERT OR IGNORE INTO products VALUES ('TV-55-SAMSUNG','Samsung 55 TV',10,11999)")
    conn.commit()
    return conn

@app.get("/", response_class=HTMLResponse)
def home():
    conn=db()
    prods = conn.execute("SELECT sku,name,qty,price FROM products").fetchall()
    conn.close()
    p_html = "".join([f"<tr><td>{p[0]}</td><td>{p[2]}</td><td>R{p[3]}</td><td><form action=/sell method=post style=display:inline><input type=hidden name=sku value='{p[0]}'><input name=qty type=number value=1 style=width:50px><button>SELL</button></form></td></tr>" for p in prods])
    return f"""<html><head><meta name=viewport content="width=device-width"><style>body{{font-family:Arial;padding:15px;background:#fce4ec}}.card{{background:white;padding:15px;border-radius:10px}}table{{width:100%}}td{{border:1px solid #ddd;padding:6px}}button{{background:#c62828;color:white;padding:6px;border:none;border-radius:4px}}</style></head><body>
    <h1 style="color:#c62828">🔴 FJ POS - Shop Front (Veldspaat)</h1>
    <div class=card><h3>Sell - Deducts from Storage</h3><table><tr><th>SKU</th><th>Qty</th><th>Price</th><th>Action</th></tr>{p_html}</table></div>
    <p>Employee: Cashier ONLY</p></body></html>"""

@app.post("/sell")
def sell(sku:str=Form(...), qty:int=Form(...)):
    conn=db()
    conn.execute("UPDATE products SET qty=qty-? WHERE sku=?",(qty,sku))
    conn.execute("INSERT INTO movements(sku,bin,qty,type,ref,timestamp) VALUES (?,?,?,?,?,?)",(sku,"POS",qty,"OUT","SALE",datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()
    # Tell storage to deduct too
    try:
        requests.post(STORAGE_URL, json={"sku":sku,"bin":"POS-SALE","qty":-qty,"ref":"SALE"}, timeout=5)
    except:
        pass
    return HTMLResponse("<script>alert('SOLD!');window.location='/'</script>")

@app.post("/api/move_internal")
def move_internal(data: dict):
    conn=db()
    conn.execute("INSERT OR IGNORE INTO products(sku,name) VALUES (?,?)",(data['sku'],data['sku']))
    conn.execute("UPDATE products SET qty=qty+? WHERE sku=?",(data.get('qty',0),data['sku']))
    conn.commit(); conn.close()
    return {"ok":True}
