from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, os, requests
from datetime import datetime

app = FastAPI()
DB = "intake.db"
CLIENT_API_URL = os.getenv("CLIENT_API_URL", "https://fj-polokwane-client.onrender.com")
STORAGE_API_URL = os.getenv("STORAGE_API_URL", "https://fj-polokwane-storage.onrender.com")

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS intake (code TEXT PRIMARY KEY, client_name TEXT, manufacturer TEXT, product_name TEXT, pallet_weight_kg REAL, pallet_height_cm REAL, bin_location TEXT, truck_plate TEXT, created_at TIMESTAMP)''')
    conn.commit()
    conn.close()
init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""<html><body style="max-width:700px;margin:auto;padding:20px"><h2>WMS Intake</h2><p>Client: {CLIENT_API_URL}</p><form method="post" action="/verify"><input name="code" placeholder="FJ-CODE" required><button>Verify</button></form></body></html>"""

@app.post("/verify", response_class=HTMLResponse)
def verify_code(code: str = Form(...)):
    try:
        data = requests.get(f"{CLIENT_API_URL}/api/verify/{code.strip()}", timeout=10).json()
        if not data.get("valid"): return HTMLResponse(f"<h3>Code {code} NOT FOUND</h3><a href='/'>Back</a>", status_code=404)
        client_name = data.get("client_name","")
        manufacturer = data.get("manufacturer","UNKNOWN")
        product_name = data.get("product_name","")
        pallet_weight = data.get("pallet_weight_kg",0) or 0
        pallet_height = data.get("pallet_height_cm",0) or 0
        quantity = data.get("quantity",0)
    except Exception as e:
        return HTMLResponse(f"<h3>ERROR connecting to Client API: {e}<br>URL: {CLIENT_API_URL}/api/verify/{code}</h3><a href='/'>Back</a>", status_code=500)

    return f"""
    <html><body style="max-width:700px;margin:auto;padding:20px">
    <h2>{code} Found</h2>
    <p>Client: {client_name}<br>Manufacturer: {manufacturer}<br>Product: {product_name}<br>Weight: {pallet_weight}kg<br>Height: {pallet_height}cm</p>
    <p><b>Rule: {'HEAVY -> M1/M2 or Level1 ONLY' if float(pallet_weight or 0)>=800 else 'OK'}</b></p>
    <form method="post" action="/receive" style="display:grid;gap:12px">
        <input type="hidden" name="code" value="{code}">
        <input type="hidden" name="client_name" value="{client_name}">
        <input type="hidden" name="manufacturer" value="{manufacturer}">
        <input type="hidden" name="product_name" value="{product_name}">
        <input type="hidden" name="pallet_weight_kg" value="{pallet_weight}">
        <input type="hidden" name="pallet_height_cm" value="{pallet_height}">
        <label>BIN (A1-1-1 to B9-4-39, HVG-01-48, M1-01-41, M2-01-27): <input name="bin_location" required></label>
        <label>Truck Plate: <input name="truck_plate" required></label>
        <button>Save & Send to Storage</button>
    </form></body></html>
    """

@app.post("/receive")
def receive(code: str = Form(...), client_name: str = Form(...), manufacturer: str = Form(...), product_name: str = Form(...), pallet_weight_kg: float = Form(...), pallet_height_cm: float = Form(...), bin_location: str = Form(...), truck_plate: str = Form(...)):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO intake VALUES (?,?,?,?,?,?,?, ?, ?)", (code, client_name, manufacturer, product_name, pallet_weight_kg, pallet_height_cm, bin_location, truck_plate, datetime.now()))
    conn.commit()
    conn.close()
    try:
        r = requests.post(f"{STORAGE_API_URL}/api/receive-intake", data={"code": code, "client_name": client_name, "manufacturer": manufacturer, "product_name": product_name, "pallet_weight_kg": pallet_weight_kg, "pallet_height_cm": pallet_height_cm, "bin_location": bin_location, "truck_plate": truck_plate}, timeout=10)
        return HTMLResponse(f"<h3>Stored: {r.text}</h3><a href='/'>New</a>")
    except Exception as e:
        return HTMLResponse(f"<h3>Saved locally but Storage failed: {e}</h3>")
