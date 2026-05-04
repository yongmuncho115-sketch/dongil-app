from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, os, hashlib, json
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'dongil-secret-key-2025-change-this'

DB_PATH = 'data/dongil.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def init_db():
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        role TEXT DEFAULT 'user'
    );
    CREATE TABLE IF NOT EXISTS 거래처리스트 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        거래처명 TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS 영업담당목록 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        영업담당 TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS 상품목록 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        상품등록번호 TEXT,
        상품명 TEXT NOT NULL,
        거래처 TEXT,
        재질1 TEXT, 비중 REAL, 두께1 REAL, 폭1 REAL,
        재질2 TEXT, 두께2 REAL, 폭2 REAL,
        상품폭 REAL, 길이 REAL, 피치 REAL,
        Cut수 REAL, 방향 TEXT, 인쇄도수 REAL,
        PE투입 TEXT, 동판둘레 INTEGER, 동판폭 INTEGER,
        포장방법 TEXT, 폼텍갯수 INTEGER, 영업담당 TEXT,
        일매 TEXT, 적요 TEXT, 후도 TEXT, 캡 TEXT, 밑지 TEXT,
        이차여부 TEXT, 이차가공 TEXT, 실링 TEXT, 개구부 TEXT,
        방향2 TEXT, 동판위치 TEXT
    );
    CREATE TABLE IF NOT EXISTS 제조의뢰서 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        문서번호 TEXT,
        거래처 TEXT, 상품명 TEXT,
        수량 REAL, 단위 TEXT, 납기 TEXT, 비고 TEXT,
        재질1 TEXT, 두께1 REAL, 폭1 REAL,
        재질2 TEXT, 두께2 REAL, 폭2 REAL,
        상품폭 REAL, 비중 REAL, 길이 REAL, 피치 REAL,
        Cut수 REAL, 방향 TEXT, 인쇄도수 REAL,
        PE투입 TEXT, 동판둘레 INTEGER, 동판폭 INTEGER,
        포장방법 TEXT, 폼텍갯수 INTEGER, 영업담당 TEXT,
        출고일 TEXT, 출고여부 INTEGER DEFAULT 0,
        일매 TEXT, 적요 TEXT, 후도 TEXT, 캡 TEXT, 밑지 TEXT,
        이차여부 TEXT, 이차가공 TEXT, 실링 TEXT, 개구부 TEXT,
        방향2 TEXT, 상품등록번호 TEXT,
        작성일 TEXT DEFAULT (date('now')),
        작성자 TEXT
    );
    ''')
    try:
        c.execute("INSERT INTO users (username, password, name, role) VALUES (?,?,?,?)",
                  ('admin', hash_pw('admin1234'), '관리자', 'admin'))
    except:
        pass
    conn.commit()
    conn.close()

def gen_doc_no():
    today = datetime.now().strftime('%Y%m%d')
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM 제조의뢰서 WHERE 문서번호 LIKE ?",
        (f'DI-{today}-%',)
    ).fetchone()
    conn.close()
    seq = str(row['cnt'] + 1).zfill(3)
    return f'DI-{today}-{seq}'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_pw(password))
        ).fetchone()
        conn.close()
        if user:
            session['user'] = dict(user)
            return redirect(url_for('index'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM 제조의뢰서").fetchone()['c']
    pending = conn.execute("SELECT COUNT(*) as c FROM 제조의뢰서 WHERE 출고여부=0").fetchone()['c']
    done = conn.execute("SELECT COUNT(*) as c FROM 제조의뢰서 WHERE 출고여부=1").fetchone()['c']
    today_str = date.today().isoformat()
    urgent = conn.execute(
        "SELECT COUNT(*) as c FROM 제조의뢰서 WHERE 출고여부=0 AND 납기<=?", (today_str,)
    ).fetchone()['c']
    recent = conn.execute("SELECT * FROM 제조의뢰서 ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    return render_template('index.html', total=total, pending=pending,
                           done=done, urgent=urgent, recent=recent)

@app.route('/orders')
@login_required
def orders():
    q = request.args.get('q', '')
    status = request.args.get('status', '')
    conn = get_db()
    sql = "SELECT * FROM 제조의뢰서 WHERE 1=1"
    params = []
    if q:
        sql += " AND (거래처 LIKE ? OR 상품명 LIKE ? OR 문서번호 LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if status == 'pending':
        sql += " AND 출고여부=0"
    elif status == 'done':
        sql += " AND 출고여부=1"
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('orders.html', rows=rows, q=q, status=status)

@app.route('/orders/new', methods=['GET', 'POST'])
@login_required
def order_new():
    conn = get_db()
    거래처목록 = [r['거래처명'] for r in conn.execute("SELECT 거래처명 FROM 거래처리스트 ORDER BY 거래처명").fetchall()]
    영업담당목록 = [r['영업담당'] for r in conn.execute("SELECT 영업담당 FROM 영업담당목록 ORDER BY 영업담당").fetchall()]

    if request.method == 'POST':
        data = request.form
        doc_no = data.get('문서번호','').strip() or gen_doc_no()
        공통 = {
            '거래처': data.get('거래처','') or None,
            '납기': data.get('납기','') or None,
            '영업담당': data.get('영업담당','') or None,
            '비고': data.get('비고','') or None,
            '출고일': data.get('출고일','') or None,
            '출고여부': 1 if data.get('출고여부') else 0,
        }
        행필드 = ['상품명','수량','단위','재질1','두께1','폭1','재질2','두께2','폭2',
                  '상품폭','비중','길이','피치','Cut수','방향','인쇄도수',
                  'PE투입','동판둘레','동판폭','포장방법','폼텍갯수',
                  '일매','적요','후도','캡','밑지','이차여부','이차가공',
                  '실링','개구부','방향2','상품등록번호']
        상품명들 = data.getlist('상품명[]')
        count = 0
        for i in range(len(상품명들)):
            if not 상품명들[i].strip():
                continue
            row = {f: (data.getlist(f+'[]')[i] if i < len(data.getlist(f+'[]')) else '') for f in 행필드}
            all_fields = ['문서번호','거래처','납기','영업담당','비고','출고일','출고여부','작성자'] + 행필드
            vals = [doc_no, 공통['거래처'], 공통['납기'], 공통['영업담당'], 공통['비고'],
                    공통['출고일'], 공통['출고여부'], session['user']['name']]
            vals += [row[f] or None for f in 행필드]
            ph = ','.join(['?']*len(all_fields))
            conn.execute(f"INSERT INTO 제조의뢰서 ({','.join(all_fields)}) VALUES ({ph})", vals)
            count += 1
        conn.commit()
        conn.close()
        flash(f'제조의뢰서 {doc_no} — {count}건 등록 완료!')
        return redirect(url_for('orders'))

    conn.close()
    return render_template('order_form_multi.html', doc_no=gen_doc_no(),
                           거래처목록=거래처목록, 영업담당목록=영업담당목록)

@app.route('/orders/<int:oid>/edit', methods=['GET', 'POST'])
@login_required
def order_edit(oid):
    conn = get_db()
    order = conn.execute("SELECT * FROM 제조의뢰서 WHERE id=?", (oid,)).fetchone()
    거래처목록 = [r['거래처명'] for r in conn.execute("SELECT 거래처명 FROM 거래처리스트 ORDER BY 거래처명").fetchall()]
    영업담당목록 = [r['영업담당'] for r in conn.execute("SELECT 영업담당 FROM 영업담당목록 ORDER BY 영업담당").fetchall()]
    상품목록 = conn.execute("SELECT * FROM 상품목록 ORDER BY 상품명").fetchall()

    if request.method == 'POST':
        data = request.form
        fields = ['거래처','상품명','수량','단위','납기','비고',
                  '재질1','두께1','폭1','재질2','두께2','폭2',
                  '상품폭','비중','길이','피치','Cut수','방향','인쇄도수',
                  'PE투입','동판둘레','동판폭','포장방법','폼텍갯수','영업담당',
                  '출고일','일매','적요','후도','캡','밑지',
                  '이차여부','이차가공','실링','개구부','방향2','상품등록번호']
        set_str = ','.join([f'{f}=?' for f in fields])
        출고여부 = 1 if data.get('출고여부') else 0
        vals = [data.get(f,'') or None for f in fields]
        conn.execute(
            f"UPDATE 제조의뢰서 SET {set_str}, 출고여부=? WHERE id=?",
            vals + [출고여부, oid]
        )
        conn.commit()
        conn.close()
        flash('수정 완료!')
        return redirect(url_for('orders'))

    conn.close()
    return render_template('order_form.html', order=order, doc_no=order['문서번호'],
                           거래처목록=거래처목록, 영업담당목록=영업담당목록, 상품목록=상품목록)

@app.route('/orders/<int:oid>/delete', methods=['POST'])
@login_required
def order_delete(oid):
    conn = get_db()
    conn.execute("DELETE FROM 제조의뢰서 WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    flash('삭제 완료')
    return redirect(url_for('orders'))

@app.route('/api/product')
@login_required
def api_product():
    name = request.args.get('name', '')
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM 상품목록 WHERE 상품명 LIKE ? LIMIT 10", (f'%{name}%',)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/master/clients', methods=['GET','POST'])
@login_required
def master_clients():
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if name:
            try:
                conn.execute("INSERT INTO 거래처리스트 (거래처명) VALUES (?)", (name,))
                conn.commit()
            except: pass
    rows = conn.execute("SELECT * FROM 거래처리스트 ORDER BY 거래처명").fetchall()
    conn.close()
    return render_template('master.html', title='거래처 관리', rows=rows,
                           col='거래처명', endpoint='master_clients')

@app.route('/master/clients/<int:rid>/delete', methods=['POST'])
@login_required
def delete_client(rid):
    conn = get_db()
    conn.execute("DELETE FROM 거래처리스트 WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return redirect(url_for('master_clients'))

@app.route('/master/staff', methods=['GET','POST'])
@login_required
def master_staff():
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if name:
            conn.execute("INSERT INTO 영업담당목록 (영업담당) VALUES (?)", (name,))
            conn.commit()
    rows = conn.execute("SELECT * FROM 영업담당목록 ORDER BY 영업담당").fetchall()
    conn.close()
    return render_template('master.html', title='영업담당 관리', rows=rows,
                           col='영업담당', endpoint='master_staff')

@app.route('/master/staff/<int:rid>/delete', methods=['POST'])
@login_required
def delete_staff(rid):
    conn = get_db()
    conn.execute("DELETE FROM 영업담당목록 WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return redirect(url_for('master_staff'))

@app.route('/users', methods=['GET','POST'])
@login_required
def manage_users():
    if session['user']['role'] != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    if request.method == 'POST':
        uname = request.form.get('username','').strip()
        pw = request.form.get('password','')
        name = request.form.get('name','').strip()
        role = request.form.get('role','user')
        try:
            conn.execute("INSERT INTO users (username,password,name,role) VALUES (?,?,?,?)",
                         (uname, hash_pw(pw), name, role))
            conn.commit()
            flash(f'사용자 {uname} 추가 완료')
        except:
            flash('이미 존재하는 아이디입니다.')
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
def delete_user(uid):
    if session['user']['role'] != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()
    flash('삭제 완료')
    return redirect(url_for('manage_users'))

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
