from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, os
from datetime import datetime

app = FastAPI()
DB = "storage.db"

def init_storage():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bins
                 (bin_code TEXT PRIMARY KEY, zone TEXT, block TEXT, level INTEGER, pos INTEGER,
                  max_weight_kg REAL, max_height_cm REAL, current_weight_kg REAL DEFAULT 0,
                  manufacturer TEXT, is_occupied INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, client_name TEXT, manufacturer TEXT,
                  product_name TEXT, pallet_weight_kg REAL, pallet_height_cm REAL,
                  bin_location TEXT, truck_plate TEXT, received_at TIMESTAMP)''')
    
    # Create bins only if empty
    if c.execute("SELECT COUNT(*) FROM bins").fetchone()[0] == 0:
        bins = []
        # A1-A9, B1-B9: 4 High x 39 Long = 156 each
        for zone in ['A','B']:
            for b in range(1,10):
                block = f"{zone}{b}"
                for level in range(1,5):
                    for pos in range(1,40):
                        code = f"{block}-{level}-{pos}"
                        max_h = 180 # cm
                        max_w = 1200 # kg per slot
                        bins.append((code, zone, block, level, pos, max_w, max_h, 0, None, 0))
        # HVG 48
        for i in range(1,49):
            code = f"HVG-{i:02d}"
            bins.append((code, 'HVG', 'HVG', 1, i, 1200, 180, 0, None, 0))
        # M1 41, M2 27 - flat, 1 level, ground only, higher weight capacity
        for i in range(1,42):
            bins.append((f"M1-{i:02d}", 'M', 'M1', 1, i, 2000, 300, 0, None, 0))
        for i in range(1,28):
            bins.append((f"M2-{i:02d}", 'M', 'M2', 1, i, 2000, 300, 0, None, 0))
        
        c.executemany("INSERT INTO bins VALUES (?,?,?,?,?,?,?,?,?,?)", bins)
    conn.commit()
    conn.close()

init_storage()

def find_best_bin(manufacturer, weight, height):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Rule: weight >800 -> level 1 or M only, height >160 -> level 1 or M only
    if weight >= 800 or height > 160:
        level_filter = "AND level=1"
    elif weight >= 500 or height >= 120:
        level_filter = "AND level IN (1,2)"
    else:
        level_filter = "AND level IN (1,2,3,4)"

    # Prefer same manufacturer
    query = f"SELECT * FROM bins WHERE is_occupied=0 {level_filter} AND max_weight_kg >= ? AND max_height_cm >= ? ORDER BY CASE WHEN manufacturer=? THEN 0 ELSE 1 END, zone, block LIMIT 5"
    rows = c.execute(query, (weight, height, manufacturer)).fetchall()
    conn.close()
    return rows

@app.post("/api/receive-intake")
def receive_intake(code: str = Form(...), client_name: str = Form(None), manufacturer: str = Form(None),
                   product_name: str = Form(None), pallet_weight_kg: float = Form(0),
                   pallet_height_cm: float = Form(0), bin_location: str = Form(...), truck_plate: str = Form(None)):
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    bin_row = c.execute("SELECT * FROM bins WHERE bin_code=?", (bin_location,)).fetchone()
    if not bin_row:
        return {"error": f"BIN {bin_location} does not exist"}
    
    # Check weight capacity
    current_w = c.execute("SELECT current_weight_kg, max_weight_kg FROM bins WHERE bin_code=?", (bin_location,)).fetchone()
    if current_w[0] + pallet_weight_kg > current_w[1]:
        conn.close()
        # Suggest alternatives
        alts = find_best_bin(manufacturer, pallet_weight_kg, pallet_height_cm)
        return {"error": f"BIN {bin_location} overweight. Max {current_w[1]}kg, current {current_w[0]}kg + new {pallet_weight_kg}kg exceeds.", "suggested_bins": [dict(zip([d[0] for d in c.description], r)) for r in []]}

    # Save stock and update bin
    c.execute("INSERT INTO stock (code, client_name, manufacturer, product_name, pallet_weight_kg, pallet_height_cm, bin_location, truck_plate, received_at) VALUES (?,?,?,?,?,?,?, ?, ?)",
              (code, client_name, manufacturer, product_name, pallet_weight_kg, pallet_height_cm, bin_location, truck_plate, datetime.now()))
    c.execute("UPDATE bins SET current_weight_kg = current_weight_kg + ?, manufacturer=?, is_occupied=1 WHERE bin_code=?",
              (pallet_weight_kg, manufacturer, bin_location))
    conn.commit()
    conn.close()
    return {"status": "stored", "bin": bin_location}

@app.get("/api/available-bins")
def available_bins(manufacturer: str = "", weight: float = 0, height: float = 0):
    rows = find_best_bin(manufacturer, weight or 500, height or 100)
    return {"available": [dict(r) for r in rows]}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM bins").fetchone()[0]
    occupied = conn.execute("SELECT COUNT(*) FROM bins WHERE is_occupied=1").fetchone()[0]
    stocks = conn.execute("SELECT * FROM stock ORDER BY received_at DESC LIMIT 50").fetchall()
    # Weight per zone
    zone_stats = conn.execute("SELECT zone, COUNT(*) as cnt, SUM(current_weight_kg) as w FROM bins GROUP BY zone").fetchall()
    conn.close()

    html = f"""
    <html><body style="font-family:Arial; padding:20px">
    <h2>FJ Storage Dashboard - 2,924 Total Slots</h2>
    <p>Total: {total} | Occupied: {occupied} | Free: {total-occupied}</p>
    <h3>Weight per Zone</h3>
    <ul>{''.join([f"<li>{z['zone']}: {z['cnt']} bins, {z['w'] or 0} kg</li>" for z in zone_stats])}</ul>
    <h3>Recent Stock</h3>
    <table border=1 cellpadding=5><tr><th>Code</th><th>Manufacturer</th><th>Product</th><th>Weight</th><th>BIN</th><th>Truck</th></tr>
    {''.join([f"<tr><td>{s['code']}</td><td>{s['manufacturer']}</td><td>{s['product_name']}</td><td>{s['pallet_weight_kg']}kg</td><td>{s['bin_location']}</td><td>{s['truck_plate']}</td></tr>" for s in stocks])}
    </table>
    </body></html>
    """
    return HTMLResponse(html)
