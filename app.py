from flask import Flask, render_template, request, redirect, url_for, Response, session
import sqlite3
import os
import hmac
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'replace-this-dev-secret')

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


def get_admin_credentials():
    # For now we use env vars. Replace with DB-backed user manager in next phase.
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    password = os.environ.get('ADMIN_PASSWORD', 'change-me')
    return username, password


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login', next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def has_valid_basic_auth():
    auth = request.authorization
    if not auth:
        return False
    valid_user, valid_pass = get_admin_credentials()
    user_ok = hmac.compare_digest(auth.username or '', valid_user)
    pass_ok = hmac.compare_digest(auth.password or '', valid_pass)
    return user_ok and pass_ok


def basic_auth_challenge():
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="Toolroom Kiosk"'}
    )


@app.before_request
def require_login_for_app():
    # Lock down port 5000 with browser-level auth challenge.
    if request.path.startswith('/static/'):
        return None
    # Allow local kiosk browser (Cog) on the Pi to load without auth prompt UI issues.
    if request.remote_addr in ('127.0.0.1', '::1'):
        return None
    if not has_valid_basic_auth():
        return basic_auth_challenge()
    return None

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


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == 'POST':
        submitted_user = request.form.get('username', '')
        submitted_pass = request.form.get('password', '')
        valid_user, valid_pass = get_admin_credentials()

        user_ok = hmac.compare_digest(submitted_user, valid_user)
        pass_ok = hmac.compare_digest(submitted_pass, valid_pass)

        if user_ok and pass_ok:
            session['is_admin'] = True
            session['admin_user'] = submitted_user
            next_path = request.args.get('next') or request.form.get('next') or url_for('admin_dashboard')
            return redirect(next_path)

        error = 'Invalid credentials'

    return render_template('admin_login.html', error=error, next_path=request.args.get('next', ''))


@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_user', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    recent_scans = query_db("SELECT * FROM logs ORDER BY id DESC LIMIT 20")
    total_logs = query_db("SELECT COUNT(*) FROM logs", one=True)[0]
    return render_template(
        'admin_dashboard.html',
        recent_scans=recent_scans,
        total_logs=total_logs,
        admin_user=session.get('admin_user', 'admin')
    )


@app.route('/admin/users')
@admin_required
def admin_users():
    # Stub page for future account manager implementation.
    return render_template('admin_users_stub.html')

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

@app.route('/export')
@admin_required
def export():
    data = query_db("SELECT * FROM logs")
    def generate():
        # Create CSV headers
        yield 'ID,Timestamp,Badge_ID,Item_ID,Qty,Is_Edited,Original_Qty\n'
        for row in data:
            yield ','.join(map(str, row)) + '\n'
    
    return Response(generate(), mimetype='text/csv', 
                    headers={"Content-disposition": "attachment; filename=toolroom_export.csv"})


if __name__ == '__main__':
    # Running on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
