from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, requests
from datetime import datetime

app = FastAPI()
DB = "intake.db"
CLIENT_URL = "https://fj-polokwane-client.onrender.com"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS intakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, client_name TEXT, address TEXT,
        product_name TEXT, product_type TEXT, quantity TEXT,
        bin_location TEXT, truck_plate TEXT, created_at TEXT)""")
    con.close()
init_db()

@app.get("/verify-client")
def verify_client_proxy(code: str):
    try:
        r = requests.get(f"{CLIENT_URL}/api/verify/{code}", timeout=10)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/", response_class=HTMLResponse)
def home():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT code, client_name, product_name, product_type, quantity, bin_location, truck_plate FROM intakes ORDER BY id DESC LIMIT 25")
    rows = cur.fetchall(); con.close()
    rows_html = "".join([f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]} | {r[3]} | {r[4]}</td><td>{r[5]}</td><td>{r[6]}</td></tr>" for r in rows])
    return f"""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:Segoe UI,sans-serif;background:#f5f7fb;padding:15px}} .card{{max-width:600px;margin:auto;background:white;padding:20px;border-radius:16px;box-shadow:0 4px 15px rgba(0,0,0,0.07);margin-bottom:20px}}
input{{width:100%;padding:11px;margin:6px 0;border:1px solid #d1d5db;border-radius:10px;box-sizing:border-box}} button{{padding:11px 15px;border:none;border-radius:10px;font-weight:bold}}
.label{{font-size:13px;font-weight:600;color:#374151;margin-top:8px;display:block}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border:1px solid #ddd;padding:6px}} th{{background:#1a3c6e;color:white}}</style>
</head><body>
<div class="card" style="border:2px dashed #1a3c6e;background:#f0f8ff"><h3>Step 1: Verify CODE</h3>
<div style="display:flex;gap:8px"><input id="verify_code" placeholder="FJ-123456"><button onclick="verifyCode()" style="background:#1a3c6e;color:white">Verify</button></div><p id="verify_status" style="font-weight:bold"></p></div>
<div class="card"><h2 style="color:#1a3c6e">FJ Intake</h2>
<form action="/intake" method="post">
<span class="label">Client CODE</span><input name="code" id="code" placeholder="FJ-123456">
<span class="label">Client Name</span><input name="client_name" id="client_name" required>
<span class="label">Address</span><input name="address" id="address" required>
<hr><b>📦 3 Separate Product Bars (Editable)</b>
<span class="label">1. Product Name</span><input name="product_name" id="product_name" required>
<span class="label">2. What is the product?</span><input name="product_type" id="product_type" required>
<span class="label">3. Quantity</span><input name="quantity" id="quantity" required>
<hr>
<span class="label">BIN Location</span><input name="bin_location" required placeholder="A1-R2-B3">
<span class="label">Truck Plate</span><input name="truck_plate" required placeholder="AB 12 CD GP">
<button type="submit" style="width:100%;margin-top:15px;background:#0f9d58;color:white;font-size:16px">SAVE INTAKE</button>
</form></div>
<div class="card"><h3>Recent</h3><table><tr><th>CODE</th><th>Client</th><th>Product (Name|Type|Qty)</th><th>BIN</th><th>Truck</th></tr>{rows_html}</table></div>
<script>
async function verifyCode(){{
  let code=document.getElementById('verify_code').value.trim();
  if(!code) return alert('Enter code');
  document.getElementById('verify_status').innerText='Checking...';
  let res=await fetch('/verify-client?code='+code); let data=await res.json();
  if(data.status=='valid'){{
    document.getElementById('verify_status').innerText='✓ Valid - You can EDIT';
    document.getElementById('code').value=data.code;
    document.getElementById('client_name').value=data.client_name||'';
    document.getElementById('address').value=data.address||'';
    document.getElementById('product_name').value=data.product_name||'';
    document.getElementById('product_type').value=data.product_type||'';
    document.getElementById('quantity').value=data.quantity||'';
  }} else {{ document.getElementById('verify_status').innerText='✗ Invalid CODE'; }}
}}
</script></body></html>
"""

@app.post("/intake", response_class=HTMLResponse)
def do_intake(code: str = Form(""), client_name: str = Form(...), address: str = Form(...), product_name: str = Form(...), product_type: str = Form(...), quantity: str = Form(...), bin_location: str = Form(...), truck_plate: str = Form(...)):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO intakes (code, client_name, address, product_name, product_type, quantity, bin_location, truck_plate, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (code, client_name, address, product_name, product_type, quantity, bin_location, truck_plate, datetime.now().isoformat()))
    con.commit(); con.close()
    return HTMLResponse(f"<div style='font-family:sans-serif;padding:20px;text-align:center'><h2>✓ Saved!</h2><p>{product_name} | {product_type} | {quantity}</p><a href='/'>Back</a></div>")
