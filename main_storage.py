@app.post("/api/receive-intake")
def receive_intake(data: dict):
    # Accept both old and new format
    code = data.get("code","")
    client_name = data.get("client_name","")
    product_name = data.get("product_name", data.get("items","").split("|")[0] if data.get("items") else "")
    product_type = data.get("product_type", "")
    quantity = data.get("quantity", "")
    bin_location = data.get("bin_location","")
    truck_plate = data.get("truck_plate","")

    con = sqlite3.connect(DB)
    # Make sure table has new columns
    try:
        con.execute("ALTER TABLE stock ADD COLUMN product_name TEXT")
        con.execute("ALTER TABLE stock ADD COLUMN product_type TEXT")
        con.execute("ALTER TABLE stock ADD COLUMN quantity TEXT")
    except: pass
    
    con.execute("INSERT OR REPLACE INTO stock (code, client_name, product_name, product_type, quantity, bin_location, truck_plate, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (code, client_name, product_name, product_type, quantity, bin_location, truck_plate, datetime.now().isoformat()))
    con.commit(); con.close()
    return {"status": "stored"}
