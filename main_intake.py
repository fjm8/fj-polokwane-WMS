from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
import sqlite3, requests
from datetime import datetime
import os

app = FastAPI()
DB = "intake.db"
CLIENT_URL = "https://fj-polokwane-client.onrender.com"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
    CREATE TABLE IF NOT EXISTS intakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        client_name TEXT,
        address TEXT,
        items TEXT,
        bin_location TEXT,
        truck_plate TEXT,
        created_at TEXT
    )
    """)
    con.close()
init_db()

# --- PROXY TO CLIENT SYSTEM ---
@app.get("/verify-client")
def verify_client_proxy(code: str):
    try:
        r = requests.get(f"{CLIENT_URL}/api/verify/{code}", timeout=10)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- MAIN PAGE ---
@app.get("/", response_class=HTMLResponse)
def home():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM intakes ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    
    rows_html = ""
    for r in rows:
        rows_html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td></tr>"

    return f"""
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FJ Intake</title></head>
<body style="font-family:sans-serif;padding:15px;max-width:600px;margin:auto">

<h2>FJ Polokwane - Intake</h2>

<div style="border:2px dashed blue;padding:15px;margin-bottom:20px;background:#f0f8ff">
<h3>Step 1: Verify Client CODE (Optional)</h3>
<input id="verify_code" placeholder="Enter FJ-123456" style="padding:8px;width:60%">
<button onclick="verifyCode()" type="button" style="padding:8px">Verify & Auto-Fill</button>
<p id="verify_status" style="font-weight:bold"></p>
</div>

<form action="/intake" method="post" style="border:1px solid #ccc;padding:15px">
<h3>Step 2: Intake Form (You can EDIT)</h3>
Client CODE: <br><input name="code" id="code" placeholder="FJ-123456" style="width:100%;padding:8px"><br><br>
Client Name: <br><input name="client_name" id="client_name" required style="width:100%;padding:8px"><br><br>
Address: <br><input name="address" id="address" required style="width:100%;padding:8px"><br><br>
Items / Description: <br><input name="items" id="items" required style="width:100%;padding:8px"><br><br>
BIN Location: <br><input name="bin_location" id="bin_location" placeholder="e.g. A1-R2-B3" required style="width:100%;padding:8px"><br><br>
Truck Plate: <br><input name="truck_plate" id="truck_plate" placeholder="e.g. AB 12 CD GP" required style="width:100%;padding:8px"><br><br>
<button type="submit" style="width:100%;padding:12px;background:green;color:white;font-size:16px">SAVE INTAKE</button>
</form>

<h3 style="margin-top:30px">Recent Intakes</h3>
<table border="1" cellpadding="5" style="width:100%;border-collapse:collapse;font-size:12px">
<tr><th>ID</th><th>CODE</th><th>Client</th><th>Address</th><th>Items</th><th>BIN</th><th>Truck</th></tr>
{rows_html}
</table>

<script>
async function verifyCode(){{
  let code = document.getElementById('verify_code').value.trim();
  if(!code) return alert('Enter code');
  document.getElementById('verify_status').innerText = 'Checking...';
  let res = await fetch('/verify-client?code=' + code);
  let data = await res.json();
  if(data.status == 'valid'){{
    document.getElementById('verify_status').innerText = '✓ Valid - Data filled, you can still EDIT';
    document.getElementById('code').value = data.code;
    document.getElementById('client_name').value = data.client_name;
    document.getElementById('address').value = data.address;
    document.getElementById('items').value = data.items;
  }} else if(data.status == 'invalid'){{
    document.getElementById('verify_status').innerText = '✗ Invalid CODE';
  }} else {{
    document.getElementById('verify_status').innerText = 'Error: ' + data.message;
  }}
}}
</script>

</body>
</html>
"""

@app.post("/intake", response_class=HTMLResponse)
def do_intake(
    code: str = Form(""),
    client_name: str = Form(...),
    address: str = Form(...),
    items: str = Form(...),
    bin_location: str = Form(...),
    truck_plate: str = Form(...)
):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO intakes (code, client_name, address, items, bin_location, truck_plate, created_at) VALUES (?,?,?,?,?,?,?)",
                (code, client_name, address, items, bin_location, truck_plate, datetime.now().isoformat()))
    con.commit()
    con.close()
    return HTMLResponse(f"<h2>Saved!</h2><p>Client: {client_name}</p><p>BIN: {bin_location}</p><a href='/'>Back to Intake</a>")
