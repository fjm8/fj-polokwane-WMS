from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime

app = FastAPI()
DB = "storage.db"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        client_name TEXT,
        product_name TEXT,
        product_type TEXT,
        quantity TEXT,
        bin_location TEXT,
        truck_plate TEXT,
        created_at TEXT
    )
    """)
    con.close()
init_db()

@app.get("/")
def home():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT code, client_name, product_name, product_type, quantity, bin_location, truck_plate FROM stock ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()
    rows_html = "".join([f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td></tr>" for r in rows])
    return HTMLResponse(f"""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{{font-family:sans-serif;background:#eef2f7;padding:20px}} .card{{background:white;padding:20px;border-radius:12px;max-width:900px;margin:auto}}
    table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border:1px solid #ccc;padding:6px}} th{{background:#1a3c6e;color:white}}</style>
    </head><body><div class="card"><h2>FJ Storage - Stock</h2>
    <table><tr><th>CODE</th><th>Client</th><th>Name</th><th>Type</th><th>Qty</th><th>BIN</th><th>Truck</th></tr>{rows_html}</table>
    </div></body></html>
    """)

@app.post("/api/receive-intake")
def receive_intake(data: dict):
    code = data.get("code","")
    client_name = data.get("client_name","")
    product_name = data.get("product_name","")
    if not product_name and data.get("items"):
        product_name = data.get("items").split("|")[0]
    product_type = data.get("product_type","")
    quantity = data.get("quantity","")
    bin_location = data.get("bin_location","")
    truck_plate = data.get("truck_plate","")
    
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO stock (code, client_name, product_name, product_type, quantity, bin_location, truck_plate, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (code, client_name, product_name, product_type, quantity, bin_location, truck_plate, datetime.now().isoformat()))
    con.commit()
    con.close()
    return {"status": "stored", "code": code}
