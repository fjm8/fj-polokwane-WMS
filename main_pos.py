from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, datetime
app = FastAPI(title="FJ POS")
DB = "fj_erp.db"
def db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, qty INTEGER DEFAULT 0, price REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, bin TEXT, qty INTEGER, type TEXT, ref TEXT, timestamp TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_phone TEXT, total REAL, vat REAL, grand_total REAL, timestamp TEXT)")
    conn.commit()
    return conn
@app.get("/", response_class=HTMLResponse)
def home():
    return """<html><head><meta name=viewport content="width=device-width"><style>body{font-family:Arial;padding:15px;background:#ffebee}.card{background:white;padding:20px;border-radius:12px}button{background:#c62828;color:white;padding:12px;border:none;border-radius:8px;width:100%;font-weight:bold}input{padding:10px;width:95%;margin:5px}</style></head><body>
    <h1 style="color:#c62828">🔴 FJ POS - Shop / Outbound (Veldspaat)</h1>
    <div class=card><h3>2. Sell - Invoice + Auto OUT</h3>
    <form action=/api/sell method=post>
    <input name=customer_phone placeholder="Customer Phone 082..." required>
    <input name=sku placeholder="SKU TV-55-SAMSUNG" required>
    <input name=qty type=number value=1 required>
    <button>CREATE INVOICE + STOCK OUT (15% VAT)</button></form></div></body></html>"""
@app.post("/api/sell")
def sell(customer_phone:str=Form(...), sku:str=Form(...), qty:int=Form(...)):
    conn=db()
    prod = conn.execute("SELECT price FROM products WHERE sku=?",(sku,)).fetchone()
    price = prod[0] if prod else 11999
    total = price*qty; vat=round(total*0.15,2); grand=total+vat
    conn.execute("INSERT INTO invoices(customer_phone,total,vat,grand_total,timestamp) VALUES (?,?,?,?,?)",(customer_phone,total,vat,grand,datetime.datetime.now().isoformat()))
    conn.execute("UPDATE products SET qty=qty-? WHERE sku=?",(qty,sku))
    conn.execute("INSERT INTO movements(sku,bin,qty,type,ref,timestamp) VALUES (?,?,?,?,?,?)",(sku,"DISPATCH",qty,"OUT",f"POS-{customer_phone}",datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()
    return HTMLResponse(f"<script>alert('SOLD R{grand} incl VAT');window.location='/'</script>")
