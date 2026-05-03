from flask import Flask, render_template, request, redirect, url_for, Response, session, flash
import sqlite3
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'replace-this-dev-secret')

DB_PATH = os.path.join(os.path.dirname(__file__), 'data/inventory.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv


def init_users_table():
    """Create users table and seed default admin if needed."""
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # Seed default admin if table is empty
    count = conn.execute('SELECT COUNT(*) as cnt FROM users').fetchone()['cnt']
    if count == 0:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     ('admin', generate_password_hash('change-me'), 'admin'))
    conn.commit()
    conn.close()


def init_workers_table():
    """Create workers table for QR-code worker list on kiosk."""
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        badge_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def init_items_table():
    """Create items table for QR-code tool/consumable list on kiosk."""
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        part_number TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def next_badge_id():
    """Generate the next sequential badge ID like WKR-00001."""
    row = query_db("SELECT badge_id FROM workers WHERE badge_id LIKE 'WKR-%' "
                   "ORDER BY id DESC LIMIT 1", one=True)
    if not row:
        return 'WKR-00001'
    try:
        n = int(row['badge_id'].split('-')[1])
    except (IndexError, ValueError):
        n = 0
    return f'WKR-{n + 1:05d}'


def sort_by_last_name(rows):
    """Sort worker rows (each with a 'name' key) by last word of the name, case-insensitive.
    Falls back to the full name when there's only one word."""
    def key(r):
        name = (r['name'] or '').strip()
        parts = name.split()
        last = parts[-1] if parts else ''
        return (last.lower(), name.lower())
    return sorted(rows, key=key)


def next_item_code():
    """Generate the next sequential item code like ITM-00001."""
    row = query_db("SELECT item_code FROM items WHERE item_code LIKE 'ITM-%' "
                   "ORDER BY id DESC LIMIT 1", one=True)
    if not row:
        return 'ITM-00001'
    try:
        n = int(row['item_code'].split('-')[1])
    except (IndexError, ValueError):
        n = 0
    return f'ITM-{n + 1:05d}'


# Auto-create tables on startup
with app.app_context():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_users_table()
    init_workers_table()
    init_items_table()


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login', next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def has_valid_basic_auth():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return False
    user = query_db('SELECT * FROM users WHERE username = ? AND is_active = 1',
                    (auth.username,), one=True)
    if not user:
        return False
    return check_password_hash(user['password_hash'], auth.password)


@app.before_request
def require_login_for_app():
    if request.path.startswith('/static/') or request.path == '/splash':
        return None
    forwarded_for = (request.headers.get('X-Forwarded-For') or '').strip()
    if request.remote_addr in ('127.0.0.1', '::1') and not forwarded_for:
        return None
    if not has_valid_basic_auth():
        return Response('Authentication required', 401,
                        {'WWW-Authenticate': 'Basic realm="Toolroom Kiosk"'})
    return None


@app.route('/splash')
def splash():
    session['viewed_splash'] = True
    return render_template('splash.html')


@app.route('/')
def index():
    # Show splash screen once per session
    if not session.get('viewed_splash'):
        return redirect(url_for('splash'))

    # Kiosk log: worker name + item name only
    recent_scans = query_db("""
        SELECT l.id, l.timestamp, w.name AS worker_name, i.name AS item_name, l.qty
        FROM logs l
        LEFT JOIN workers w ON w.badge_id = l.badge_id
        LEFT JOIN items i ON i.item_code = l.item_id
        ORDER BY l.id DESC LIMIT 10
    """)
    workers_rows = sort_by_last_name(
        query_db("SELECT badge_id, name FROM workers WHERE is_active = 1"))
    # Precompute first/last initials so the template can render letter dividers
    # for either sort order without re-parsing names in Jinja.
    workers = []
    for r in workers_rows:
        name = (r['name'] or '').strip()
        parts = name.split()
        first_initial = (parts[0][0] if parts else '').upper()
        last_initial = (parts[-1][0] if parts else '').upper()
        workers.append({
            'badge_id': r['badge_id'],
            'name': r['name'],
            'first_initial': first_initial,
            'last_initial': last_initial,
        })
    recent_workers = query_db("""
        SELECT w.badge_id, w.name FROM workers w
        JOIN (SELECT badge_id, MAX(id) AS last_id FROM logs GROUP BY badge_id) l
          ON l.badge_id = w.badge_id
        WHERE w.is_active = 1
        ORDER BY l.last_id DESC
        LIMIT 8
    """)
    items = query_db("SELECT item_code, name FROM items WHERE is_active = 1 "
                     "ORDER BY name COLLATE NOCASE")
    recent_items = query_db("""
        SELECT i.item_code, i.name FROM items i
        JOIN (SELECT item_id, MAX(id) AS last_id FROM logs GROUP BY item_id) l
          ON l.item_id = i.item_code
        WHERE i.is_active = 1
        ORDER BY l.last_id DESC
        LIMIT 8
    """)
    return render_template('index.html', scans=recent_scans,
                           workers=workers, recent_workers=recent_workers,
                           items=items, recent_items=recent_items)


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
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user = query_db('SELECT * FROM users WHERE username = ? AND is_active = 1',
                        (username,), one=True)
        if user and user['role'] == 'admin' and check_password_hash(user['password_hash'], password):
            session['is_admin'] = True
            session['admin_user'] = username
            session['admin_user_id'] = user['id']
            next_path = request.args.get('next') or request.form.get('next') or url_for('admin_dashboard')
            return redirect(next_path)
        error = 'Invalid credentials'

    return render_template('admin_login.html', error=error, next_path=request.args.get('next', ''))


@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    recent_scans = query_db("""
        SELECT l.id, l.timestamp, l.badge_id, w.name AS worker_name,
               l.item_id, i.name AS item_name, i.part_number,
               l.qty, l.is_edited, l.original_qty
        FROM logs l
        LEFT JOIN workers w ON w.badge_id = l.badge_id
        LEFT JOIN items i ON i.item_code = l.item_id
        ORDER BY l.id DESC LIMIT 20
    """)
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
    users = query_db('SELECT * FROM users ORDER BY id')
    return render_template('admin_users.html', users=users,
                           current_user_id=session.get('admin_user_id'))


@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_users_add():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'admin')

    if not username or not password:
        flash('Username and password are required.', 'error')
        return redirect(url_for('admin_users'))

    if role not in ('admin', 'operator'):
        role = 'admin'

    existing = query_db('SELECT id FROM users WHERE username = ?', (username,), one=True)
    if existing:
        flash(f'Username "{username}" already exists.', 'error')
        return redirect(url_for('admin_users'))

    query_db('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
             (username, generate_password_hash(password), role))
    flash(f'User "{username}" created.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def admin_users_edit(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))

    password = request.form.get('password', '')
    role = request.form.get('role', user['role'])
    is_active = request.form.get('is_active', '1')

    if role not in ('admin', 'operator'):
        role = user['role']

    if password:
        query_db('UPDATE users SET password_hash = ?, role = ?, is_active = ? WHERE id = ?',
                 (generate_password_hash(password), role, int(is_active), user_id))
    else:
        query_db('UPDATE users SET role = ?, is_active = ? WHERE id = ?',
                 (role, int(is_active), user_id))

    flash(f'User "{user["username"]}" updated.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_users_delete(user_id):
    if user_id == session.get('admin_user_id'):
        flash("You can't delete your own account.", 'error')
        return redirect(url_for('admin_users'))

    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))

    query_db('DELETE FROM users WHERE id = ?', (user_id,))
    flash(f'User "{user["username"]}" deleted.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/workers')
@admin_required
def admin_workers():
    workers = sort_by_last_name(query_db('SELECT * FROM workers'))
    return render_template('admin_workers.html', workers=workers)


@app.route('/admin/workers/add', methods=['POST'])
@admin_required
def admin_workers_add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('admin_workers'))

    badge_id = next_badge_id()
    query_db('INSERT INTO workers (badge_id, name) VALUES (?, ?)', (badge_id, name))
    flash(f'Worker "{name}" created with badge {badge_id}.', 'success')
    return redirect(url_for('admin_workers'))


@app.route('/admin/workers/<int:worker_id>/edit', methods=['POST'])
@admin_required
def admin_workers_edit(worker_id):
    worker = query_db('SELECT * FROM workers WHERE id = ?', (worker_id,), one=True)
    if not worker:
        flash('Worker not found.', 'error')
        return redirect(url_for('admin_workers'))

    name = request.form.get('name', '').strip() or worker['name']
    is_active = request.form.get('is_active', '1')
    query_db('UPDATE workers SET name = ?, is_active = ? WHERE id = ?',
             (name, int(is_active), worker_id))
    flash(f'Worker "{name}" updated.', 'success')
    return redirect(url_for('admin_workers'))


@app.route('/admin/workers/<int:worker_id>/delete', methods=['POST'])
@admin_required
def admin_workers_delete(worker_id):
    worker = query_db('SELECT * FROM workers WHERE id = ?', (worker_id,), one=True)
    if not worker:
        flash('Worker not found.', 'error')
        return redirect(url_for('admin_workers'))

    query_db('DELETE FROM workers WHERE id = ?', (worker_id,))
    flash(f'Worker "{worker["name"]}" deleted.', 'success')
    return redirect(url_for('admin_workers'))


@app.route('/admin/items')
@admin_required
def admin_items():
    items = query_db('SELECT * FROM items ORDER BY name COLLATE NOCASE')
    return render_template('admin_items.html', items=items)


@app.route('/admin/items/add', methods=['POST'])
@admin_required
def admin_items_add():
    item_code = request.form.get('item_code', '').strip()
    name = request.form.get('name', '').strip()
    part_number = request.form.get('part_number', '').strip() or None

    if not name:
        flash('Item name is required.', 'error')
        return redirect(url_for('admin_items'))

    if not item_code:
        item_code = next_item_code()

    existing = query_db('SELECT id FROM items WHERE item_code = ?',
                        (item_code,), one=True)
    if existing:
        flash(f'Item code "{item_code}" already exists.', 'error')
        return redirect(url_for('admin_items'))

    query_db('INSERT INTO items (item_code, name, part_number) VALUES (?, ?, ?)',
             (item_code, name, part_number))
    flash(f'Item "{name}" created with code {item_code}.', 'success')
    return redirect(url_for('admin_items'))


@app.route('/admin/items/<int:item_id>/edit', methods=['POST'])
@admin_required
def admin_items_edit(item_id):
    item = query_db('SELECT * FROM items WHERE id = ?', (item_id,), one=True)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('admin_items'))

    name = request.form.get('name', '').strip() or item['name']
    part_number = request.form.get('part_number', '').strip() or None
    is_active = request.form.get('is_active', '1')

    query_db('UPDATE items SET name = ?, part_number = ?, is_active = ? WHERE id = ?',
             (name, part_number, int(is_active), item_id))
    flash(f'Item "{name}" updated.', 'success')
    return redirect(url_for('admin_items'))


@app.route('/admin/items/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_items_delete(item_id):
    item = query_db('SELECT * FROM items WHERE id = ?', (item_id,), one=True)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('admin_items'))

    query_db('DELETE FROM items WHERE id = ?', (item_id,))
    flash(f'Item "{item["name"]}" deleted.', 'success')
    return redirect(url_for('admin_items'))


@app.route('/api/lookup')
def api_lookup():
    """Resolve a scanned code to a human name for kiosk visual confirmation.

    Query params: ?badge=<code> or ?item=<code> (one at a time).
    Returns JSON: { known: bool, name: string|null, part_number?: string }
    """
    badge = request.args.get('badge', '').strip()
    item_code = request.args.get('item', '').strip()
    if badge:
        row = query_db('SELECT name FROM workers WHERE badge_id = ? AND is_active = 1',
                       (badge,), one=True)
        if row:
            return {'known': True, 'name': row['name']}
        return {'known': False, 'name': None}
    if item_code:
        row = query_db('SELECT name, part_number FROM items '
                       'WHERE item_code = ? AND is_active = 1',
                       (item_code,), one=True)
        if row:
            return {'known': True, 'name': row['name'],
                    'part_number': row['part_number'] or ''}
        return {'known': False, 'name': None}
    return {'known': False, 'name': None}


@app.route('/edit_last', methods=['POST'])
def edit_last():
    last_entry = query_db("SELECT id, qty FROM logs ORDER BY id DESC LIMIT 1", one=True)
    if last_entry:
        entry_id, old_qty = last_entry['id'], last_entry['qty']
        new_qty = request.form.get('new_qty')
        if new_qty:
            query_db("UPDATE logs SET qty = ?, original_qty = ?, is_edited = 1 WHERE id = ?",
                     (new_qty, old_qty, entry_id))
    return redirect(url_for('index'))


@app.route('/export')
@admin_required
def export():
    data = query_db("""
        SELECT l.id, l.timestamp, l.badge_id, w.name AS worker_name,
               l.item_id, i.name AS item_name, i.part_number,
               l.qty, l.is_edited, l.original_qty
        FROM logs l
        LEFT JOIN workers w ON w.badge_id = l.badge_id
        LEFT JOIN items i ON i.item_code = l.item_id
        ORDER BY l.id
    """)
    def csv_escape(v):
        s = '' if v is None else str(v)
        if any(c in s for c in ',"\n\r'):
            return '"' + s.replace('"', '""') + '"'
        return s
    def generate():
        yield 'ID,Timestamp,Badge_ID,Worker_Name,Item_Code,Item_Name,Part_Number,Qty,Is_Edited,Original_Qty\n'
        for row in data:
            yield ','.join(csv_escape(v) for v in tuple(row)) + '\n'
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-disposition": "attachment; filename=toolroom_export.csv"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
