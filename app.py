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
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count == 0:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     ('admin', generate_password_hash('change-me'), 'admin'))
    conn.commit()
    conn.close()


# Auto-create users table on startup
with app.app_context():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_users_table()


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
    if request.path.startswith('/static/'):
        return None
    forwarded_for = (request.headers.get('X-Forwarded-For') or '').strip()
    if request.remote_addr in ('127.0.0.1', '::1') and not forwarded_for:
        return None
    if not has_valid_basic_auth():
        return Response('Authentication required', 401,
                        {'WWW-Authenticate': 'Basic realm="Toolroom Kiosk"'})
    return None


@app.route('/')
def index():
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
    data = query_db("SELECT * FROM logs")
    def generate():
        yield 'ID,Timestamp,Badge_ID,Item_ID,Qty,Is_Edited,Original_Qty\n'
        for row in data:
            yield ','.join(map(str, tuple(row))) + '\n'
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-disposition": "attachment; filename=toolroom_export.csv"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
