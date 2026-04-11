from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
import os
import csv

app = Flask(__name__)

# PROTOTYPE PATH (Local)
DB_PATH = os.path.join(os.path.dirname(__file__), 'data/inventory.db')

# SHIPYARD PATH (Example of what you'll change later)
# DB_PATH = '/mnt/toolroom_nas/inventory.db'

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def index():
    # Fetch the 10 most recent scans to show on screen
    recent_scans = query_db("SELECT * FROM logs ORDER BY id DESC LIMIT 10")
    return render_template('index.html', scans=recent_scans)

@app.route('/scan', methods=['POST'])
def scan():
    badge = request.form.get('badge')
    item = request.form.get('item')
    qty = request.form.get('qty', 1)
    
    if badge and item:
        query_db("INSERT INTO logs (badge_id, item_id, qty) VALUES (?, ?, ?)", (badge, item, qty))
    return redirect(url_for('index'))

@app.route('/edit_last', methods=['POST'])
def edit_last():
    # Grab the very last entry to "flag" it
    last_entry = query_db("SELECT id, qty FROM logs ORDER BY id DESC LIMIT 1", one=True)
    if last_entry:
        entry_id, old_qty = last_entry
        new_qty = request.form.get('new_qty')
        if new_qty:
            query_db("UPDATE logs SET qty = ?, original_qty = ?, is_edited = 1 WHERE id = ?", (new_qty, old_qty, entry_id))
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Running on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)

@app.route('/export')
def export():
    data = query_db("SELECT * FROM logs")
    def generate():
        # Create CSV headers
        yield 'ID,Timestamp,Badge_ID,Item_ID,Qty,Is_Edited,Original_Qty\n'
        for row in data:
            yield ','.join(map(str, row)) + '\n'
    
    return Response(generate(), mimetype='text/csv', 
                    headers={"Content-disposition": "attachment; filename=toolroom_export.csv"})
