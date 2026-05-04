from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, hashlib
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'dongil-secret-key-2025'
DB_PATH = os.path.join(os.path.dirname(__file__), 'dongil.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, name TEXT NOT NULL, role TEXT DEFAULT 'user', active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now','localtime')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS doc_numbers (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_no TEXT UNIQUE NOT NULL, description TEXT, created_by INTEGER, created_at TEXT DEFAULT (datetime('now','localtime')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT UNIQUE NOT NULL, doc_no_id INTEGER, title TEXT, writer TEXT, write_date TEXT, approver1 TEXT, approver2 TEXT, approver3 TEXT, status TEXT DEFAULT 'writing', created_by INTEGER, created_at TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY (doc_no_id) REFERENCES doc_numbers(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, seq INTEGER DEFAULT 1, customer TEXT, product_name TEXT, quantity REAL, unit TEXT, material_spec TEXT, delivery_date TEXT, note TEXT, FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE)""")
    conn.commit()
    existing = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        pw = hashlib.sha256('admin1234'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, name, role) VALUES (?,?,?,?)", ('admin', pw, '관리자', 'admin'))
        conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND active=1", (username, pw_hash)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('index'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = get_db()
    orders = conn.execute('SELECT o.*, d.doc_no FROM orders o LEFT JOIN doc_numbers d ON o.doc_no_id = d.id ORDER BY o.created_at DESC').fetchall()
    conn.close()
    return render_template('index.html', orders=orders)

@app.route('/users')
@admin_required
def users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    conn = get_db()
    cnt = conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
    if cnt >= 10:
        flash('사용자는 최대 10명까지 등록 가능합니다.', 'error')
        conn.close()
        return redirect(url_for('users'))
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    name = request.form.get('name','').strip()
    role = request.form.get('role','user')
    if not username or not password or not name:
        flash('모든 필드를 입력하세요.', 'error')
        conn.close()
        return redirect(url_for('users'))
    if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        flash('이미 존재하는 아이디입니다.', 'error')
        conn.close()
        return redirect(url_for('users'))
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn.execute("INSERT INTO users (username, password, name, role) VALUES (?,?,?,?)", (username, pw_hash, name, role))
    conn.commit()
    conn.close()
    flash(f'사용자 [{name}]이 등록되었습니다.', 'success')
    return redirect(url_for('users'))

@app.route('/users/edit/<int:uid>', methods=['POST'])
@admin_required
def edit_user(uid):
    conn = get_db()
    name = request.form.get('name','').strip()
    role = request.form.get('role','user')
    active = 1 if request.form.get('active') else 0
    password = request.form.get('password','').strip()
    if password:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("UPDATE users SET name=?, role=?, active=?, password=? WHERE id=?", (name, role, active, pw_hash, uid))
    else:
        conn.execute("UPDATE users SET name=?, role=?, active=? WHERE id=?", (name, role, active, uid))
    conn.commit()
    conn.close()
    flash('사용자 정보가 수정되었습니다.', 'success')
    return redirect(url_for('users'))

@app.route('/users/delete/<int:uid>', methods=['POST'])
@admin_required
def delete_user(uid):
    if uid == session.get('user_id'):
        flash('본인 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('users'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('users'))

@app.route('/doc_numbers')
@login_required
def doc_numbers():
    conn = get_db()
    docs = conn.execute('SELECT d.*, u.name as creator_name, COUNT(o.id) as order_count FROM doc_numbers d LEFT JOIN users u ON d.created_by = u.id LEFT JOIN orders o ON o.doc_no_id = d.id GROUP BY d.id ORDER BY d.created_at DESC').fetchall()
    conn.close()
    return render_template('doc_numbers.html', docs=docs)

@app.route('/doc_numbers/add', methods=['POST'])
@login_required
def add_doc_number():
    doc_no = request.form.get('doc_no','').strip()
    description = request.form.get('description','').strip()
    if not doc_no:
        flash('문서번호를 입력하세요.', 'error')
        return redirect(url_for('doc_numbers'))
    conn = get_db()
    if conn.execute("SELECT id FROM doc_numbers WHERE doc_no=?", (doc_no,)).fetchone():
        flash('이미 존재하는 문서번호입니다.', 'error')
        conn.close()
        return redirect(url_for('doc_numbers'))
    conn.execute("INSERT INTO doc_numbers (doc_no, description, created_by) VALUES (?,?,?)", (doc_no, description, session['user_id']))
    conn.commit()
    conn.close()
    flash(f'문서번호 [{doc_no}]가 등록되었습니다.', 'success')
    return redirect(url_for('doc_numbers'))

@app.route('/doc_numbers/delete/<int:did>', methods=['POST'])
@admin_required
def delete_doc_number(did):
    conn = get_db()
    conn.execute("DELETE FROM doc_numbers WHERE id=?", (did,))
    conn.commit()
    conn.close()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('doc_numbers'))

@app.route('/orders/new')
@login_required
def new_order():
    conn = get_db()
    doc_numbers = conn.execute("SELECT * FROM doc_numbers ORDER BY doc_no").fetchall()
    conn.close()
    return render_template('order_form.html', order=None, items=[], doc_numbers=doc_numbers, today=date.today().strftime('%Y-%m-%d'), mode='new')

@app.route('/orders/save', methods=['POST'])
@login_required
def save_order():
    order_id = request.form.get('order_id')
    doc_no_id = request.form.get('doc_no_id') or None
    order_no = request.form.get('order_no','').strip()
    title = request.form.get('title','').strip()
    writer = request.form.get('writer', session['name']).strip()
    write_date = request.form.get('write_date','').strip()
    approver1 = request.form.get('approver1','').strip()
    approver2 = request.form.get('approver2','').strip()
    approver3 = request.form.get('approver3','').strip()
    customers = request.form.getlist('customer[]')
    product_names = request.form.getlist('product_name[]')
    quantities = request.form.getlist('quantity[]')
    units = request.form.getlist('unit[]')
    material_specs = request.form.getlist('material_spec[]')
    delivery_dates = request.form.getlist('delivery_date[]')
    notes = request.form.getlist('note[]')
    conn = get_db()
    if order_id:
        conn.execute('UPDATE orders SET doc_no_id=?,order_no=?,title=?,writer=?,write_date=?,approver1=?,approver2=?,approver3=? WHERE id=?', (doc_no_id, order_no, title, writer, write_date, approver1, approver2, approver3, order_id))
        conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
    else:
        cur = conn.execute('INSERT INTO orders (doc_no_id,order_no,title,writer,write_date,approver1,approver2,approver3,created_by) VALUES (?,?,?,?,?,?,?,?,?)', (doc_no_id, order_no, title, writer, write_date, approver1, approver2, approver3, session['user_id']))
        order_id = cur.lastrowid
    for i, pname in enumerate(product_names):
        if pname.strip():
            conn.execute('INSERT INTO order_items (order_id,seq,customer,product_name,quantity,unit,material_spec,delivery_date,note) VALUES (?,?,?,?,?,?,?,?,?)', (order_id, i+1, customers[i] if i<len(customers) else '', pname.strip(), quantities[i] if i<len(quantities) else '', units[i] if i<len(units) else '', material_specs[i] if i<len(material_specs) else '', delivery_dates[i] if i<len(delivery_dates) else '', notes[i] if i<len(notes) else ''))
    conn.commit()
    conn.close()
    flash('저장되었습니다.', 'success')
    return redirect(url_for('view_order', oid=order_id))

@app.route('/orders/<int:oid>')
@login_required
def view_order(oid):
    conn = get_db()
    order = conn.execute('SELECT o.*, d.doc_no FROM orders o LEFT JOIN doc_numbers d ON o.doc_no_id = d.id WHERE o.id=?', (oid,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY seq", (oid,)).fetchall()
    conn.close()
    if not order:
        flash('없는 의뢰서입니다.', 'error')
        return redirect(url_for('index'))
    return render_template('order_view.html', order=order, items=items)

@app.route('/orders/<int:oid>/edit')
@login_required
def edit_order(oid):
    conn = get_db()
    order = conn.execute('SELECT o.*, d.doc_no FROM orders o LEFT JOIN doc_numbers d ON o.doc_no_id = d.id WHERE o.id=?', (oid,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY seq", (oid,)).fetchall()
    doc_numbers = conn.execute("SELECT * FROM doc_numbers ORDER BY doc_no").fetchall()
    conn.close()
    if not order:
        return redirect(url_for('index'))
    return render_template('order_form.html', order=order, items=items, doc_numbers=doc_numbers, today=date.today().strftime('%Y-%m-%d'), mode='edit')

@app.route('/orders/<int:oid>/delete', methods=['POST'])
@login_required
def delete_order(oid):
    conn = get_db()
    conn.execute("DELETE FROM orders WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/orders/<int:oid>/print')
@login_required
def print_order(oid):
    conn = get_db()
    order = conn.execute('SELECT o.*, d.doc_no FROM orders o LEFT JOIN doc_numbers d ON o.doc_no_id = d.id WHERE o.id=?', (oid,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY seq", (oid,)).fetchall()
    conn.close()
    if not order:
        return redirect(url_for('index'))
    return render_template('order_print.html', order=order, items=items)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

with app.app_context():
    init_db()
