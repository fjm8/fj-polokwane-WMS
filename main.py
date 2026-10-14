from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, datetime, os

app = FastAPI(title="FJ-ERP SA v1 - Polokwane")

DB = "fj_erp.db"

def db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT, cost REAL DEFAULT 0, price REAL DEFAULT 0, qty INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS locations (bin TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, bin TEXT, qty INTEGER, type TEXT, ref TEXT, timestamp TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, balance REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, total REAL, vat REAL, grand_total REAL, status TEXT, timestamp TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS invoice_items (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER, sku TEXT, qty INTEGER, price REAL)")
    # seed
    if conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]==0:
        for b in ["PLK-A-01-01","PLK-A-01-02","PLK-B-02-01","RECEIVING","DISPATCH"]:
            conn.execute("INSERT INTO locations VALUES (?)",(b,))
        conn.execute("INSERT OR IGNORE INTO products VALUES ('TV-55-SAMSUNG','Samsung 55 TV',8000,11999,10)")
        conn.execute("INSERT OR IGNORE INTO customers VALUES (1,'Cash Sale Polokwane','015 000 0000',0)")
        conn.commit()
    return conn

HTML = """
<html><head><meta name=viewport content="width=device-width,initial-scale=1"><title>FJ-ERP SA</title>
<style>body{font-family:Arial;padding:15px;background:#f5f5f5}.card{background:white;padding:15px;border-radius:10px;margin-bottom:15px;box-shadow:0 2px 5px #0001}
h1{color:#d00} input,select,button{padding:10px;margin:5px;width:95%} button{background:#d00;color:white;border:none;border-radius:5px;font-weight:bold}
.tab{padding:10px;background:#222;color:white;display:inline-block;border-radius:5px;margin-right:5px;cursor:pointer}.active{background:#d00}
table{width:100%;border-collapse:collapse} td,th{border:1px solid #ddd;padding:8px;font-size:13px}</style>
<script>
function show(t){document.querySelectorAll('.sec').forEach(s=>s.style.display='none');document.getElementById(t).style.display='block'}
</script></head><body>
<h1>FJ-ERP SA v1 - Veldspaat DC</h1>
<div><span class=tab onclick="show('wms')">WMS Scan</span><span class=tab onclick="show('pos')">POS / Invoice</span><span class=tab onclick="show('stock')">Stock</span></div>

<div id=wms class="sec card">
<h3>1. Scan Stock Movement (Your old WMS)</h3>
<form action=/api/move method=post>
<select name=type><option>IN</option><option>OUT</option></select>
<input name=sku placeholder="SKU e.g. TV-55-SAMSUNG" required>
<input name=bin placeholder="BIN e.g. PLK-A-01-01" required>
<input name=qty type=number value=1 required>
<input name=ref placeholder="Ref / GRN / SAP Doc">
<button>POST MOVEMENT -> QUEUED_FOR_SAP</button>
</form>
</div>

<div id=pos class="sec card" style="display:none">
<h3>2. New Sale - Invoice (SA VAT 15%)</h3>
<form action=/api/invoice method=post>
<input name=customer_phone placeholder="Customer Phone - e.g. 082..." required>
<input name=sku placeholder="SKU" required>
<input name=qty type=number value=1 required>
<button>CREATE INVOICE + AUTO STOCK OUT</button>
</form>
<p>Flow: Invoice created -> Stock reduced -> VAT 15% calculated -> Ready for Yoco/Pay</p>
</div>

<div id=stock class="sec card" style="display:none">
<h3>3. Live Stock & Invoices</h3>
{stock_table}
<hr>
{invoice_table}
</div>

</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    conn=db()
    stock = conn.execute("SELECT sku,name,qty,price FROM products").fetchall()
    inv = conn.execute("SELECT id,total,vat,grand_total,status,timestamp FROM invoices ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    stock_html = "<table><tr><th>SKU</th><th>Name</th><th>Qty</th><th>Price</th></tr>" + "".join([f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td><td>R{s[3]}</td></tr>" for s in stock]) + "</table>"
    inv_html = "<table><tr><th>Inv#</th><th>Total</th><th>VAT</th><th>Grand</th><th>Status</th></tr>" + "".join([f"<tr><td>{i[0]}</td><td>R{i[1]}</td><td>R{i[2]}</td><td>R{i[3]}</td><td>{i[4]}</td></tr>" for i in inv]) + "</table>"
    return HTML.replace("{stock_table}",stock_html).replace("{invoice_table}",inv_html)

@app.post("/api/move")
def move(sku:str=Form(...), bin:str=Form(...), qty:int=Form(...), type:str=Form(...), ref:str=Form("")):
    conn=db()
    conn.execute("INSERT OR IGNORE INTO products(sku,name) VALUES (?,?)",(sku,sku))
    if type=="IN":
        conn.execute("UPDATE products SET qty=qty+? WHERE sku=?",(qty,sku))
    else:
        conn.execute("UPDATE products SET qty=qty-? WHERE sku=?",(qty,sku))
    conn.execute("INSERT INTO movements(sku,bin,qty,type,ref,timestamp) VALUES (?,?,?,?,?,?)",(sku,bin,qty,type,ref or "QUEUED_FOR_SAP",datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()
    return HTMLResponse("<script>alert('Movement OK - QUEUED_FOR_SAP');window.location='/'</script>")

@app.post("/api/invoice")
def invoice(customer_phone:str=Form(...), sku:str=Form(...), qty:int=Form(...)):
    conn=db()
    prod = conn.execute("SELECT price FROM products WHERE sku=?",(sku,)).fetchone()
    price = prod[0] if prod else 11999
    total = price*qty
    vat = round(total*0.15,2)
    grand = total+vat
    # customer
    cust = conn.execute("SELECT id FROM customers WHERE phone=?",(customer_phone,)).fetchone()
    if not cust:
        conn.execute("INSERT INTO customers(name,phone) VALUES (?,?)",(customer_phone,customer_phone))
        cust_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else: cust_id=cust[0]
    conn.execute("INSERT INTO invoices(customer_id,total,vat,grand_total,status,timestamp) VALUES (?,?,?,?,?,?)",(cust_id,total,vat,grand,"PAID",datetime.datetime.now().isoformat()))
    inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO invoice_items(invoice_id,sku,qty,price) VALUES (?,?,?,?)",(inv_id,sku,qty,price))
    conn.execute("UPDATE products SET qty=qty-? WHERE sku=?",(qty,sku))
    conn.execute("INSERT INTO movements(sku,bin,qty,type,ref,timestamp) VALUES (?,?,?,?,?,?)",(sku,"DISPATCH",qty,"OUT",f"INV-{inv_id}",datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()
    return HTMLResponse(f"<script>alert('Invoice INV-{inv_id} Created: R{grand} incl VAT');window.location='/'</script>")

@app.get("/health")
def health(): return {"status":"FJ-ERP SA Live","modules":["WMS","POS","VAT","SAP-Queue"]}
