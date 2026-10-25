from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime

app = FastAPI()
DB = "storage.db"

def init_storage():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bins (bin_code TEXT PRIMARY KEY, zone TEXT, block TEXT, level INTEGER, pos INTEGER, max_weight_kg REAL, max_height_cm REAL, current_weight_kg REAL DEFAULT 0, manufacturer TEXT, is_occupied INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, client_name TEXT, manufacturer TEXT, product_name TEXT, pallet_weight_kg REAL, pallet_height_cm REAL, bin_location TEXT, truck_plate TEXT, received_at TIMESTAMP)''')
    if c.execute("SELECT COUNT(*) FROM bins").fetchone()[0] == 0:
        bins = []
        for zone in ['A','B']:
            for b in range(1,10):
                block = f"{zone}{b}"
                for level in range(1,5):
                    for pos in range(1,40):
                        bins.append((f"{block}-{level}-{pos}", zone, block, level, pos, 1200, 180, 0, None, 0))
        for i in range(1,49): bins.append((f"HVG-{i:02d}", 'HVG', 'HVG', 1, i, 1200, 180, 0, None, 0))
        for i in range(1,42): bins.append((f"M1-{i:02d}", 'M', 'M1', 1, i, 2000, 300, 0, None, 0))
        for i in range(1,28): bins.append((f"M2-{i:02d}", 'M', 'M2', 1, i, 2000, 300, 0, None, 0))
        c.executemany("INSERT INTO bins VALUES (?,?,?,?,?,?,?,?,?,?)", bins)
    conn.commit()
    conn.close()
init_storage()

@app.post("/api/receive-intake")
def receive_intake(code: str = Form(...), client_name: str = Form(None), manufacturer: str = Form(None), product_name: str = Form(None), pallet_weight_kg: float = Form(0), pallet_height_cm: float = Form(0), bin_location: str = Form(...), truck_plate: str = Form(None)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    bin_row = c.execute("SELECT * FROM bins WHERE bin_code=?", (bin_location,)).fetchone()
    if not bin_row: return {"error": f"BIN {bin_location} does not exist. Total 2924 bins: A1-A9, B1-B9 (1-4-39), HVG-01-48, M1-01-41, M2-01-27"}
    cur_w, max_w = c.execute("SELECT current_weight_kg, max_weight_kg FROM bins WHERE bin_code=?", (bin_location,)).fetchone()
    if cur_w + pallet_weight_kg > max_w: return {"error": f"Overweight. BIN max {max_w}kg, current {cur_w}kg + new {pallet_weight_kg}kg"}
    c.execute("INSERT INTO stock VALUES (NULL,?,?,?,?,?,?,?,?)", (code, client_name, manufacturer, product_name, pallet_weight_kg, pallet_height_cm, bin_location, truck_plate, datetime.now()))
    c.execute("UPDATE bins SET current_weight_kg=current_weight_kg+?, manufacturer=?, is_occupied=1 WHERE bin_code=?", (pallet_weight_kg, manufacturer, bin_location))
    conn.commit()
    conn.close()
    return {"status": "stored", "bin": bin_location}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM bins").fetchone()[0]
    occ = conn.execute("SELECT COUNT(*) FROM bins WHERE is_occupied=1").fetchone()[0]
    stocks = conn.execute("SELECT * FROM stock ORDER BY received_at DESC LIMIT 100").fetchall()
    conn.close()
    rows = "".join([f"<tr><td>{s['code']}</td><td>{s['manufacturer']}</td><td>{s['product_name']}</td><td>{s['pallet_weight_kg']}kg</td><td>{s['bin_location']}</td></tr>" for s in stocks])
    return HTMLResponse(f"<html><body style='padding:20px'><h2>Storage 2924 Slots | {occ}/{total} Occupied</h2><table border=1 cellpadding=5><tr><th>Code</th><th>MFG</th><th>Product</th><th>Weight</th><th>BIN</th></tr>{rows}</table></body></html>")
