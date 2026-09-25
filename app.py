from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3, os
from functools import wraps
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jewel-vogue-secret-key-change-this')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, 'jewel_vogue.db')
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
USE_POSTGRES = DATABASE_URL.startswith(('postgres://', 'postgresql://'))
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

DEFAULT_SETTINGS = {
    'store_name':'JEWEL VOGUE','tagline':'Elegant jewelry for every occasion.','currency':'PKR','cod_enabled':'1','bank_transfer_enabled':'1',
    'easypaisa_enabled':'1','jazzcash_enabled':'1','easypaisa_name':'','easypaisa_number':'',
    'easypaisa_note':'','jazzcash_name':'','jazzcash_number':'','jazzcash_note':'',
    'shipping_fee':'200','free_shipping_min':'5000'
}

STORE_LAYOUT = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title><style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f7f5f1;color:#222}a{text-decoration:none;color:inherit}
nav{background:#111;color:#fff;padding:15px 5%;display:flex;align-items:center;gap:22px;flex-wrap:wrap}nav .brand{font-size:22px;font-weight:700;letter-spacing:2px;margin-right:auto}nav a{color:#fff}nav a:hover{color:#d6b45a}.container{width:min(1180px,92%);margin:30px auto}.hero{background:#111;color:#fff;padding:55px 35px;border-radius:16px;margin-bottom:28px}.hero h1{font-size:42px;margin:0 0 10px}.hero p{color:#ddd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:20px}.product{background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 3px 14px #0001}.product img{width:100%;height:230px;object-fit:cover;background:#eee}.product .pad{padding:16px}.price{font-weight:700;color:#a47d12;font-size:18px}.btn{display:inline-block;border:0;border-radius:8px;padding:10px 15px;background:#111;color:#fff;cursor:pointer}.btn.gold{background:#b08a00}.btn.light{background:#eee;color:#111}.btn.danger{background:#b33}.box{background:#fff;padding:22px;border-radius:14px;box-shadow:0 3px 14px #0001;margin-bottom:20px}.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}input,select,textarea{width:100%;padding:11px;border:1px solid #ccc;border-radius:8px;background:#fff}textarea{min-height:100px}label{font-weight:600;display:block;margin-bottom:6px}table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:11px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}.table-wrap{overflow:auto}.flash{padding:12px 15px;background:#fff4cc;border:1px solid #ecd98a;border-radius:8px;margin-bottom:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px;margin-bottom:25px}.stat{background:#fff;padding:22px;border-radius:12px;box-shadow:0 3px 12px #0001}.stat h2{margin:0;color:#b08a00}.muted{color:#777}.actions{display:flex;gap:7px;flex-wrap:wrap}.qty{width:80px}footer{text-align:center;padding:35px;color:#777}.small{font-size:13px}.success{color:#16733b}.danger-text{color:#b33}.check{display:flex;align-items:center;gap:8px}.check input{width:auto}
</style></head><body><nav><a class="brand" href="{{ url_for('home') }}">JEWEL VOGUE</a><a href="{{ url_for('home') }}">Home</a><a href="{{ url_for('products') }}">Products</a><a href="{{ url_for('wishlist') }}">Wishlist ({{ wishlist_count }})</a><a href="{{ url_for('cart') }}">Cart ({{ cart_count }})</a>{% if session.get('admin_id') %}<a href="{{ url_for('admin_dashboard') }}">Admin</a><a href="{{ url_for('admin_logout') }}">Logout</a>{% else %}<a href="{{ url_for('admin_login') }}">Admin Login</a>{% endif %}</nav><main class="container">{% with messages=get_flashed_messages() %}{% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endwith %}{{BODY}}</main><footer>JEWEL VOGUE © {{ year }}</footer></body></html>'''

def get_db():
    if USE_POSTGRES:
        if not psycopg2: raise RuntimeError('PostgreSQL selected but psycopg2-binary is not installed.')
        return psycopg2.connect(DATABASE_URL)
    conn=sqlite3.connect(SQLITE_DB); conn.row_factory=sqlite3.Row; return conn

def convert_sql(sql): return sql.replace('?', '%s') if USE_POSTGRES else sql

def query(sql, params=(), one=False):
    conn=get_db(); cur=conn.cursor(cursor_factory=RealDictCursor) if USE_POSTGRES else conn.cursor()
    try:
        cur.execute(convert_sql(sql), params); rows=cur.fetchall();
        if one: return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]
    finally: cur.close(); conn.close()

def execute(sql, params=()):
    conn=get_db(); cur=conn.cursor()
    try: cur.execute(convert_sql(sql),params); conn.commit(); return cur.rowcount
    finally: cur.close(); conn.close()

def insert_get_id(sql, params=()):
    conn=get_db(); cur=conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(convert_sql(sql)+' RETURNING id',params); rid=cur.fetchone()[0]
        else:
            cur.execute(sql,params); rid=cur.lastrowid
        conn.commit(); return rid
    finally: cur.close(); conn.close()

def sqlite_column_exists(table,col):
    conn=get_db(); cur=conn.cursor(); cur.execute(f'PRAGMA table_info({table})'); ok=col in [r[1] for r in cur.fetchall()]; cur.close(); conn.close(); return ok

def initialize_database():
    if USE_POSTGRES:
        conn=get_db(); cur=conn.cursor()
        stmts=[
        '''CREATE TABLE IF NOT EXISTS admin_users(id SERIAL PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS categories(id SERIAL PRIMARY KEY,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS materials(id SERIAL PRIMARY KEY,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY,name TEXT NOT NULL,description TEXT,price NUMERIC(12,2) DEFAULT 0,image TEXT,category_id INTEGER,material_id INTEGER,stock INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY,customer_name TEXT,email TEXT,phone TEXT,address TEXT,city TEXT,subtotal NUMERIC(12,2),discount NUMERIC(12,2) DEFAULT 0,shipping NUMERIC(12,2) DEFAULT 0,total NUMERIC(12,2),payment_method TEXT,bank_id INTEGER,payment_note TEXT,status TEXT DEFAULT 'Pending',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS order_items(id SERIAL PRIMARY KEY,order_id INTEGER,product_id INTEGER,product_name TEXT,price NUMERIC(12,2),quantity INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS reviews(id SERIAL PRIMARY KEY,product_id INTEGER,name TEXT,rating INTEGER,comment TEXT,approved INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS coupons(id SERIAL PRIMARY KEY,code TEXT UNIQUE NOT NULL,discount_type TEXT DEFAULT 'percent',discount_value NUMERIC(12,2) DEFAULT 0,min_amount NUMERIC(12,2) DEFAULT 0,active INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)''',
        '''CREATE TABLE IF NOT EXISTS banks(id SERIAL PRIMARY KEY,name TEXT,account_title TEXT,account_number TEXT,iban TEXT,note TEXT,active INTEGER DEFAULT 1)''']
        for s in stmts: cur.execute(s)
        conn.commit(); cur.close(); conn.close()
    else:
        conn=get_db(); cur=conn.cursor()
        cur.executescript('''CREATE TABLE IF NOT EXISTS admin_users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT,price REAL DEFAULT 0,image TEXT,category_id INTEGER,material_id INTEGER,stock INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_name TEXT,email TEXT,phone TEXT,address TEXT,city TEXT,subtotal REAL,discount REAL DEFAULT 0,shipping REAL DEFAULT 0,total REAL,payment_method TEXT,bank_id INTEGER,payment_note TEXT,status TEXT DEFAULT 'Pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,product_id INTEGER,product_name TEXT,price REAL,quantity INTEGER);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,name TEXT,rating INTEGER,comment TEXT,approved INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS coupons(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,discount_type TEXT DEFAULT 'percent',discount_value REAL DEFAULT 0,min_amount REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS banks(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,account_title TEXT,account_number TEXT,iban TEXT,note TEXT,active INTEGER DEFAULT 1);''')
        # Safely handle old SQLite databases whose settings table used a legacy schema.
        # Keep the old table instead of deleting it, then create the modern key/value table.
        cols=[r[1] for r in cur.execute('PRAGMA table_info(settings)').fetchall()]
        if 'key' not in cols or 'value' not in cols:
            legacy='settings_legacy'
            n=1
            while cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(legacy,)).fetchone():
                n+=1; legacy=f'settings_legacy_{n}'
            cur.execute(f'ALTER TABLE settings RENAME TO {legacy}')
            cur.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)')
            legacy_cols=[r[1] for r in cur.execute(f'PRAGMA table_info({legacy})').fetchall()]
            key_col=next((x for x in ('key','name','setting','setting_key') if x in legacy_cols),None)
            value_col=next((x for x in ('value','setting_value','val') if x in legacy_cols),None)
            if key_col and value_col:
                cur.execute(f'INSERT OR IGNORE INTO settings(key,value) SELECT {key_col},{value_col} FROM {legacy} WHERE {key_col} IS NOT NULL')

        # Add columns that may be missing from older versions of the store.
        required={
            'admin_users': [('created_at','TEXT')],
            'categories': [('active','INTEGER DEFAULT 1')],
            'materials': [('active','INTEGER DEFAULT 1')],
            'products': [('description','TEXT'),('price','REAL DEFAULT 0'),('image','TEXT'),('category_id','INTEGER'),('material_id','INTEGER'),('stock','INTEGER DEFAULT 0'),('active','INTEGER DEFAULT 1'),('created_at','TEXT')],
            'orders': [('customer_name','TEXT'),('email','TEXT'),('phone','TEXT'),('address','TEXT'),('city','TEXT'),('subtotal','REAL'),('discount','REAL DEFAULT 0'),('shipping','REAL DEFAULT 0'),('total','REAL'),('payment_method','TEXT'),('bank_id','INTEGER'),('payment_note','TEXT'),('status',"TEXT DEFAULT 'Pending'"),('created_at','TEXT')],
            'order_items': [('order_id','INTEGER'),('product_id','INTEGER'),('product_name','TEXT'),('price','REAL'),('quantity','INTEGER')],
            'reviews': [('product_id','INTEGER'),('name','TEXT'),('rating','INTEGER'),('comment','TEXT'),('approved','INTEGER DEFAULT 1'),('created_at','TEXT')],
            'coupons': [('code','TEXT'),('discount_type',"TEXT DEFAULT 'percent'"),('discount_value','REAL DEFAULT 0'),('min_amount','REAL DEFAULT 0'),('active','INTEGER DEFAULT 1'),('created_at','TEXT')],
            'banks': [('name','TEXT'),('account_title','TEXT'),('account_number','TEXT'),('iban','TEXT'),('note','TEXT'),('active','INTEGER DEFAULT 1')]
        }
        for table,fields in required.items():
            existing={r[1] for r in cur.execute(f'PRAGMA table_info({table})').fetchall()}
            for col,typ in fields:
                if col not in existing:
                    cur.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
        conn.commit(); cur.close(); conn.close()
    seed_data()

def seed_data():
    for k,v in DEFAULT_SETTINGS.items():
        if not query('SELECT key FROM settings WHERE key=?',(k,),one=True): execute('INSERT INTO settings(key,value) VALUES(?,?)',(k,v))
    if not query('SELECT id FROM admin_users WHERE username=?',('admin',),one=True): insert_get_id('INSERT INTO admin_users(username,password_hash) VALUES(?,?)',('admin',generate_password_hash('admin123')))
    cats=['Rings','Necklaces','Earrings','Bracelets','Bangles','Sets','Watches']; mats=['Gold','Silver','Diamond','Pearl','Stainless Steel','Rose Gold']
    for x in cats:
        if not query('SELECT id FROM categories WHERE name=?',(x,),one=True): insert_get_id('INSERT INTO categories(name) VALUES(?)',(x,))
    for x in mats:
        if not query('SELECT id FROM materials WHERE name=?',(x,),one=True): insert_get_id('INSERT INTO materials(name) VALUES(?)',(x,))
    products=[('Classic Gold Ring','Elegant classic gold ring.',4500,'https://images.unsplash.com/photo-1605100804763-247f67b3557e?auto=format&fit=crop&w=700&q=80','Rings','Gold',10),('Pearl Necklace','Elegant pearl necklace.',8500,'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=700&q=80','Necklaces','Pearl',8),('Silver Earrings','Simple silver earrings.',3200,'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=700&q=80','Earrings','Silver',15),('Diamond Bracelet','Premium diamond bracelet.',25000,'https://images.unsplash.com/photo-1611652022419-a9419f74343d?auto=format&fit=crop&w=700&q=80','Bracelets','Diamond',5),('Rose Gold Bangles','Modern rose gold bangles.',12000,'https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=700&q=80','Bangles','Rose Gold',7),('Elegant Jewelry Set','Matching jewelry set.',15000,'https://images.unsplash.com/photo-1611652022419-a9419f74343d?auto=format&fit=crop&w=700&q=80','Sets','Gold',6)]
    for p in products:
        if not query('SELECT id FROM products WHERE name=?',(p[0],),one=True):
            c=query('SELECT id FROM categories WHERE name=?',(p[4],),one=True); m=query('SELECT id FROM materials WHERE name=?',(p[5],),one=True)
            insert_get_id('INSERT INTO products(name,description,price,image,category_id,material_id,stock) VALUES(?,?,?,?,?,?,?)',(p[0],p[1],p[2],p[3],c['id'],m['id'],p[6]))

def get_setting(k,default=''): r=query('SELECT value FROM settings WHERE key=?',(k,),one=True); return r['value'] if r else default
def set_setting(k,v): execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?',(k,v,v)) if USE_POSTGRES else execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,v))
def to_int(v,d=0):
    try:return int(v)
    except:return d
def to_float(v,d=0):
    try:return float(v)
    except:return d
def money(v): return f'{to_float(v):,.2f}'
def get_cart(): return session.setdefault('cart',{})
def cart_count(): return sum(to_int(v) for v in get_cart().values())
def get_wishlist(): return session.setdefault('wishlist',[])
def wishlist_count(): return len(get_wishlist())
def get_cart_items():
    cart=get_cart(); ids=[to_int(x) for x in cart if to_int(x)>0]
    if not ids:return []
    ph=','.join('?' for _ in ids); rows=query(f'''SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id WHERE p.id IN ({ph}) AND p.active=1''',tuple(ids)); out=[]
    for p in rows:
        q=min(to_int(cart.get(str(p['id']),1)),to_int(p['stock'])); out.append({'product':p,'quantity':q,'line_total':q*to_float(p['price'])})
    return out
def active_payment_options(): return [x for x,k in [('Cash on Delivery','cod_enabled'),('Bank Transfer','bank_transfer_enabled'),('EasyPaisa','easypaisa_enabled'),('JazzCash','jazzcash_enabled')] if get_setting(k,'0')=='1']
def active_banks(): return query('SELECT * FROM banks WHERE active=1 ORDER BY id DESC')
def calculate_coupon(code,subtotal):
    if not code:return 0,None
    c=query('SELECT * FROM coupons WHERE UPPER(code)=UPPER(?) AND active=1',(code.strip(),),one=True)
    if not c:return 0,None
    if subtotal<to_float(c['min_amount']):return 0,c
    if c['discount_type']=='percent': d=subtotal*to_float(c['discount_value'])/100
    else:d=to_float(c['discount_value'])
    return min(d,subtotal),c

def render_store(body,title='JEWEL VOGUE',**context):
    # Render the page body FIRST, then place the finished HTML inside the
    # shared JEWEL VOGUE layout. This prevents nested Jinja templates from
    # being treated as literal text and fixes the blank-content issue.
    context.update(
        year=datetime.now().year,
        cart_count=cart_count(),
        wishlist_count=wishlist_count()
    )
    rendered_body = render_template_string(body, title=title, **context)
    page = STORE_LAYOUT.replace('{{BODY}}', rendered_body)
    return render_template_string(page, title=title, **context)

def render_admin(body,title='Admin',**context):
    # Admin uses exactly the same storefront layout.
    return render_store(body,title,**context)
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('admin_id'): return redirect(url_for('admin_login',next=request.path))
        return fn(*a,**kw)
    return wrapper

def product_card_template(): return '''{% for p in products %}<div class="product"><img src="{{p.image or 'https://via.placeholder.com/700x500?text=Jewelry'}}"><div class="pad"><h3>{{p.name}}</h3><p class="muted">{{p.category_name or ''}}{% if p.material_name %} • {{p.material_name}}{% endif %}</p><p class="price">{{currency}} {{ '%.2f'|format(p.price) }}</p><p>{{p.description or ''}}</p><div class="actions"><a class="btn" href="{{url_for('product_detail',product_id=p.id)}}">View</a><form method="post" action="{{url_for('cart_add',product_id=p.id)}}"><button class="btn gold">Add to Cart</button></form></div></div></div>{% endfor %}'''

@app.route('/')
def home():
    products=query('SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id WHERE p.active=1 ORDER BY p.id DESC LIMIT 8')
    body='''<section class="hero"><h1>JEWEL VOGUE</h1><p>{{tagline}}</p><a class="btn gold" href="{{url_for('products')}}">Shop Now</a></section><h2>Featured Jewelry</h2><div class="grid">'''+product_card_template()+'''</div>'''
    return render_store(body,'JEWEL VOGUE',products=products,currency=get_setting('currency','PKR'),tagline=get_setting('tagline','Elegant jewelry for every occasion.'))

@app.route('/products')
def products():
    cat=to_int(request.args.get('category'),0); material=to_int(request.args.get('material'),0); q=request.args.get('q','').strip()
    sql='SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id WHERE p.active=1'; params=[]
    if cat:sql+=' AND p.category_id=?';params.append(cat)
    if material:sql+=' AND p.material_id=?';params.append(material)
    if q:sql+=' AND (p.name LIKE ? OR p.description LIKE ?)';params.extend([f'%{q}%',f'%{q}%'])
    sql+=' ORDER BY p.id DESC'; rows=query(sql,tuple(params)); cats=query('SELECT * FROM categories WHERE active=1 ORDER BY name'); mats=query('SELECT * FROM materials WHERE active=1 ORDER BY name')
    body='''<h1>Products</h1><div class="box"><form class="form-grid"><div><label>Search</label><input name="q" value="{{request.args.get('q','')}}"></div><div><label>Category</label><select name="category"><option value="0">All</option>{% for c in cats %}<option value="{{c.id}}" {% if request.args.get('category')==c.id|string %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select></div><div><label>Material</label><select name="material"><option value="0">All</option>{% for m in mats %}<option value="{{m.id}}" {% if request.args.get('material')==m.id|string %}selected{% endif %}>{{m.name}}</option>{% endfor %}</select></div><div style="align-self:end"><button class="btn">Filter</button></div></form></div><div class="grid">'''+product_card_template()+'''</div>'''
    return render_store(body,'Products',products=rows,cats=cats,mats=mats,currency=get_setting('currency','PKR'))

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    p=query('SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id WHERE p.id=? AND p.active=1',(product_id,),one=True)
    if not p:return render_store('<div class="box"><h2>Product not found</h2></div>','Not Found'),404
    reviews=query('SELECT * FROM reviews WHERE product_id=? AND approved=1 ORDER BY id DESC',(product_id,))
    body='''<div class="box"><div class="form-grid"><div><img style="width:100%;max-height:500px;object-fit:cover;border-radius:12px" src="{{p.image}}"></div><div><h1>{{p.name}}</h1><p>{{p.description}}</p><p>{{p.category_name}}{% if p.material_name %} • {{p.material_name}}{% endif %}</p><p class="price">{{currency}} {{'%.2f'|format(p.price)}}</p><p>Stock: {{p.stock}}</p><form method="post" action="{{url_for('cart_add',product_id=p.id)}}"><input class="qty" type="number" name="quantity" min="1" max="{{p.stock}}" value="1"><button class="btn gold">Add to Cart</button></form><p><a class="btn light" href="{{url_for('wishlist_toggle',product_id=p.id)}}">Add/Remove Wishlist</a></p></div></div></div><div class="box"><h2>Reviews</h2>{% for r in reviews %}<p><b>{{r.name}}</b> — {{r.rating}}/5<br>{{r.comment}}</p><hr>{% else %}<p class="muted">No reviews yet.</p>{% endfor %}<h3>Write a review</h3><form method="post" action="{{url_for('review_add',product_id=p.id)}}" class="form-grid"><div><label>Name</label><input name="name" required></div><div><label>Rating</label><select name="rating">{% for n in range(1,6) %}<option>{{n}}</option>{% endfor %}</select></div><div style="grid-column:1/-1"><label>Comment</label><textarea name="comment" required></textarea></div><div><button class="btn">Submit</button></div></form></div>'''
    return render_store(body,p['name'],p=p,reviews=reviews,currency=get_setting('currency','PKR'))

@app.post('/review/add/<int:product_id>')
def review_add(product_id):
    insert_get_id('INSERT INTO reviews(product_id,name,rating,comment,approved) VALUES(?,?,?,?,1)',(product_id,request.form.get('name','Guest'),max(1,min(5,to_int(request.form.get('rating'),5))),request.form.get('comment','')));flash('Review submitted.');return redirect(url_for('product_detail',product_id=product_id))

@app.post('/cart/add/<int:product_id>')
def cart_add(product_id):
    p=query('SELECT * FROM products WHERE id=? AND active=1',(product_id,),one=True)
    if not p:
        flash('Product not found.')
        return redirect(url_for('products'))
    stock=to_int(p['stock'])
    if stock <= 0:
        flash('This product is out of stock.')
        return redirect(request.referrer or url_for('products'))
    q=max(1,to_int(request.form.get('quantity'),1)); cart=get_cart(); current=to_int(cart.get(str(product_id),0));
    cart[str(product_id)]=min(current+q,stock); session['cart']=cart
    flash('Product added to cart.')
    return redirect(request.referrer or url_for('cart'))

@app.route('/cart')
def cart():
    items=get_cart_items();subtotal=sum(x['line_total'] for x in items);discount,coupon=calculate_coupon(session.get('coupon_code'),subtotal); shipping=0 if subtotal>=to_float(get_setting('free_shipping_min','5000')) else to_float(get_setting('shipping_fee','200'));total=max(0,subtotal-discount+shipping)
    body='''<h1>Cart</h1>{% if items %}<div class="box"><form method="post" action="{{url_for('cart_update')}}"><div class="table-wrap"><table><tr><th>Product</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr>{% for x in items %}<tr><td>{{x.product.name}}</td><td>{{currency}} {{'%.2f'|format(x.product.price)}}</td><td><input class="qty" type="number" min="0" max="{{x.product.stock}}" name="quantity_{{x.product.id}}" value="{{x.quantity}}"></td><td>{{currency}} {{'%.2f'|format(x.line_total)}}</td><td><a class="btn danger" href="{{url_for('cart_remove',product_id=x.product.id)}}">Remove</a></td></tr>{% endfor %}</table></div><button class="btn" name="update" value="1">Update Cart</button></form></div><div class="box"><form method="post" action="{{url_for('coupon_apply')}}" class="form-grid"><div><label>Coupon</label><input name="code" value="{{session.get('coupon_code','')}}"></div><div style="align-self:end"><button class="btn">Apply Coupon</button></div></form><p>Subtotal: <b>{{currency}} {{'%.2f'|format(subtotal)}}</b></p><p>Discount: <b>{{currency}} {{'%.2f'|format(discount)}}</b></p><p>Shipping: <b>{{currency}} {{'%.2f'|format(shipping)}}</b></p><h2>Total: {{currency}} {{'%.2f'|format(total)}}</h2><a class="btn gold" href="{{url_for('checkout')}}">Checkout</a></div>{% else %}<div class="box"><p>Your cart is empty.</p><a class="btn" href="{{url_for('products')}}">Shop Products</a></div>{% endif %}'''
    return render_store(body,'Cart',items=items,subtotal=subtotal,discount=discount,shipping=shipping,total=total,currency=get_setting('currency','PKR'))

@app.post('/cart/update')
def cart_update():
    cart=get_cart()
    for key in list(cart):
        if key.isdigit():
            q=to_int(request.form.get('quantity_'+key),0); p=query('SELECT stock FROM products WHERE id=? AND active=1',(to_int(key),),one=True)
            if not p or q<=0:cart.pop(key,None)
            else:cart[key]=min(q,to_int(p['stock']))
    session['cart']=cart;flash('Cart updated.');return redirect(url_for('cart'))
@app.get('/cart/remove/<int:product_id>')
def cart_remove(product_id): cart=get_cart();cart.pop(str(product_id),None);session['cart']=cart;return redirect(url_for('cart'))
@app.post('/coupon/apply')
def coupon_apply():
    code=request.form.get('code','').strip();subtotal=sum(x['line_total'] for x in get_cart_items());d,c=calculate_coupon(code,subtotal)
    if c:session['coupon_code']=c['code'];flash(f'Coupon applied. Discount: {get_setting("currency","PKR")} {money(d)}')
    else:session.pop('coupon_code',None);flash('Invalid coupon or minimum amount not reached.')
    return redirect(url_for('cart'))

@app.get('/wishlist')
def wishlist():
    ids=get_wishlist(); products=[]
    if ids:
        ph=','.join('?' for _ in ids);products=query(f'SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id WHERE p.id IN ({ph}) AND p.active=1',tuple(ids))
    body='<h1>Wishlist</h1><div class="grid">'+product_card_template()+'</div>' if products else '<div class="box"><h2>Wishlist is empty</h2><a class="btn" href="'+url_for('products')+'">Browse Products</a></div>'
    return render_store(body,'Wishlist',products=products,currency=get_setting('currency','PKR'))
@app.get('/wishlist/toggle/<int:product_id>')
def wishlist_toggle(product_id):
    w=get_wishlist();w.remove(product_id) if product_id in w else w.append(product_id);session['wishlist']=w;return redirect(request.referrer or url_for('wishlist'))

@app.route('/checkout',methods=['GET','POST'])
def checkout():
    items=get_cart_items()
    if not items:flash('Your cart is empty.');return redirect(url_for('cart'))
    subtotal=sum(x['line_total'] for x in items);discount,coupon=calculate_coupon(session.get('coupon_code'),subtotal);shipping=0 if subtotal>=to_float(get_setting('free_shipping_min','5000')) else to_float(get_setting('shipping_fee','200'));total=max(0,subtotal-discount+shipping);banks=active_banks();payments=active_payment_options()
    if request.method=='POST':
        f=request.form; name=f.get('customer_name','').strip();phone=f.get('phone','').strip();address=f.get('address','').strip();method=f.get('payment_method','');bank_id=to_int(f.get('bank_id'),0) or None
        if not name or not phone or not address:flash('Name, phone and address are required.')
        elif method not in payments:flash('Please select a valid payment method.')
        elif method=='Bank Transfer' and not bank_id:flash('Please select a bank.')
        else:
            conn=get_db();cur=conn.cursor()
            try:
                if USE_POSTGRES:cur.execute(convert_sql('INSERT INTO orders(customer_name,email,phone,address,city,subtotal,discount,shipping,total,payment_method,bank_id,payment_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id'),(name,f.get('email',''),phone,address,f.get('city',''),subtotal,discount,shipping,total,method,bank_id,f.get('payment_note','')));oid=cur.fetchone()[0]
                else:cur.execute('INSERT INTO orders(customer_name,email,phone,address,city,subtotal,discount,shipping,total,payment_method,bank_id,payment_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(name,f.get('email',''),phone,address,f.get('city',''),subtotal,discount,shipping,total,method,bank_id,f.get('payment_note','')));oid=cur.lastrowid
                for x in items:
                    cur.execute(convert_sql('INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)'),(oid,x['product']['id'],x['product']['name'],x['product']['price'],x['quantity']))
                    cur.execute(convert_sql('UPDATE products SET stock=stock-? WHERE id=? AND stock>=?'),(x['quantity'],x['product']['id'],x['quantity']))
                conn.commit();session['cart']={};session.pop('coupon_code',None);session['last_order_id']=oid;return redirect(url_for('order_success',order_id=oid))
            except Exception as e:conn.rollback();flash('Order could not be created: '+str(e))
            finally:cur.close();conn.close()
    body='''<h1>Checkout</h1><div class="box"><form method="post"><div class="form-grid"><div><label>Name</label><input name="customer_name" required></div><div><label>Email</label><input type="email" name="email"></div><div><label>Phone</label><input name="phone" required></div><div><label>City</label><input name="city"></div><div style="grid-column:1/-1"><label>Address</label><textarea name="address" required></textarea></div><div><label>Payment</label><select name="payment_method" id="pm" required onchange="document.getElementById('bankbox').style.display=this.value==='Bank Transfer'?'block':'none'">{% for x in payments %}<option>{{x}}</option>{% endfor %}</select></div><div id="bankbox" style="display:none"><label>Bank</label><select name="bank_id"><option value="">Select bank</option>{% for b in banks %}<option value="{{b.id}}">{{b.name}} — {{b.account_title}} — {{b.account_number}}</option>{% endfor %}</select></div><div style="grid-column:1/-1"><label>Payment note</label><textarea name="payment_note"></textarea></div></div><hr><p>Subtotal: {{currency}} {{'%.2f'|format(subtotal)}}</p><p>Discount: {{currency}} {{'%.2f'|format(discount)}}</p><p>Shipping: {{currency}} {{'%.2f'|format(shipping)}}</p><h2>Total: {{currency}} {{'%.2f'|format(total)}}</h2><button class="btn gold">Place Order</button></form></div>'''
    return render_store(body,'Checkout',payments=payments,banks=banks,subtotal=subtotal,discount=discount,shipping=shipping,total=total,currency=get_setting('currency','PKR'))

@app.get('/order/success/<int:order_id>')
def order_success(order_id):
    o=query('SELECT o.*,b.name bank_name FROM orders o LEFT JOIN banks b ON b.id=o.bank_id WHERE o.id=?',(order_id,),one=True)
    if not o:return redirect(url_for('home'))
    body='''<div class="box"><h1>Order Placed</h1><p>Thank you, {{o.customer_name}}.</p><p>Order #{{o.id}}</p><p>Status: {{o.status}}</p><p>Total: {{currency}} {{'%.2f'|format(o.total)}}</p><a class="btn" href="{{url_for('products')}}">Continue Shopping</a></div>'''
    return render_store(body,'Order Success',o=o,currency=get_setting('currency','PKR'))

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        u=query('SELECT * FROM admin_users WHERE username=?',(request.form.get('username',''),),one=True)
        if u and check_password_hash(u['password_hash'],request.form.get('password','')):session['admin_id']=u['id'];return redirect(request.args.get('next') or url_for('admin_dashboard'))
        flash('Invalid username or password.')
    body='''<div class="box" style="max-width:500px;margin:auto"><h1>Admin Login</h1><form method="post"><label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required><br><br><button class="btn gold">Login</button></form><p class="small muted"></p></div>''';return render_store(body,'Admin Login')
@app.get('/admin/logout')
def admin_logout():session.pop('admin_id',None);return redirect(url_for('home'))

@app.get('/admin')
@admin_required
def admin_dashboard():
    stats=[('Products',query('SELECT COUNT(*) n FROM products',one=True)['n']),('Orders',query('SELECT COUNT(*) n FROM orders',one=True)['n']),('Customers',query('SELECT COUNT(DISTINCT phone) n FROM orders',one=True)['n']),('Sales',money(query('SELECT COALESCE(SUM(total),0) n FROM orders WHERE status!=? ',('Cancelled',),one=True)['n']))]
    body='''<h1>JEWEL VOGUE Admin</h1><div class="cards">{% for s in stats %}<div class="stat"><h2>{{s[1]}}</h2><p>{{s[0]}}</p></div>{% endfor %}</div><div class="box"><div class="actions"><a class="btn" href="{{url_for('admin_products')}}">Products</a><a class="btn" href="{{url_for('admin_orders')}}">Orders</a><a class="btn" href="{{url_for('admin_categories')}}">Categories</a><a class="btn" href="{{url_for('admin_materials')}}">Materials</a><a class="btn" href="{{url_for('admin_reviews')}}">Reviews</a><a class="btn" href="{{url_for('admin_coupons')}}">Coupons</a><a class="btn" href="{{url_for('admin_banks')}}">Banks</a><a class="btn" href="{{url_for('admin_settings')}}">Settings</a><a class="btn" href="{{url_for('admin_sales')}}">Sales</a><a class="btn" href="{{url_for('admin_password')}}">Password</a></div></div>''';return render_admin(body,'Admin Dashboard',stats=stats)

def admin_crud_list(title,table,rows,add_endpoint,edit_endpoint,toggle_endpoint,delete_endpoint,columns):
    heads=''.join(f'<th>{h}</th>' for h in columns); cells=''.join('<td>{{{{r.{}}}}}</td>'.format(k) for k in columns.keys())
    body=f'''<h1>{title}</h1><p><a class="btn gold" href="{{{{url_for('{add_endpoint}')}}}}">Add</a> <a class="btn light" href="{{{{url_for('admin_dashboard')}}}}">Dashboard</a></p><div class="box table-wrap"><table><tr>{heads}<th>Actions</th></tr>{{% for r in rows %}}<tr>{cells}<td class="actions"><a class="btn" href="{{{{url_for('{edit_endpoint}',item_id=r.id)}}}}">Edit</a><a class="btn light" href="{{{{url_for('{toggle_endpoint}',item_id=r.id)}}}}">Toggle</a><a class="btn danger" href="{{{{url_for('{delete_endpoint}',item_id=r.id)}}}}">Delete</a></td></tr>{{% endfor %}}</table></div>'''
    return render_admin(body,title,rows=rows)

def simple_admin_form(title,fields,action_endpoint,item=None):
    inputs=''
    for name,label,typ in fields:
        val='' if not item else item.get(name,'')
        if typ=='textarea':inputs+=f'<label>{label}</label><textarea name="{name}">{val}</textarea>'
        else:inputs+=f'<label>{label}</label><input type="{typ}" name="{name}" value="{val}">'
    body=f'<div class="box"><h1>{title}</h1><form method="post">{inputs}<br><button class="btn gold">Save</button></form></div>'
    return render_admin(body,title,item=item)

@app.route('/admin/categories')
@admin_required
def admin_categories():
    rows=query('SELECT * FROM categories ORDER BY id DESC');return admin_crud_list('Categories','categories',rows,'admin_category_add','admin_category_edit','admin_category_toggle','admin_category_delete',{'id':'ID','name':'Name','active':'Active'})
@app.route('/admin/categories/add',methods=['GET','POST'])
@admin_required
def admin_category_add():
    if request.method=='POST':
        try:insert_get_id('INSERT INTO categories(name,active) VALUES(?,1)',(request.form['name'],));flash('Category added.');return redirect(url_for('admin_categories'))
        except Exception as e:flash(str(e))
    return simple_admin_form('Add Category',[('name','Name','text')],'admin_category_add')
@app.route('/admin/categories/edit/<int:item_id>',methods=['GET','POST'])
@admin_required
def admin_category_edit(item_id):
    item=query('SELECT * FROM categories WHERE id=?',(item_id,),one=True)
    if request.method=='POST':execute('UPDATE categories SET name=?,active=? WHERE id=?',(request.form['name'],to_int(request.form.get('active'),1),item_id));return redirect(url_for('admin_categories'))
    return simple_admin_form('Edit Category',[('name','Name','text'),('active','Active (1/0)','number')],'admin_category_edit',item)
@app.get('/admin/categories/toggle/<int:item_id>')
@admin_required
def admin_category_toggle(item_id):execute('UPDATE categories SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_categories'))
@app.get('/admin/categories/delete/<int:item_id>')
@admin_required
def admin_category_delete(item_id):execute('DELETE FROM categories WHERE id=?',(item_id,));return redirect(url_for('admin_categories'))

@app.route('/admin/materials')
@admin_required
def admin_materials():
    rows=query('SELECT * FROM materials ORDER BY id DESC');return admin_crud_list('Materials','materials',rows,'admin_material_add','admin_material_edit','admin_material_toggle','admin_material_delete',{'id':'ID','name':'Name','active':'Active'})
@app.route('/admin/materials/add',methods=['GET','POST'])
@admin_required
def admin_material_add():
    if request.method=='POST':
        try:insert_get_id('INSERT INTO materials(name,active) VALUES(?,1)',(request.form['name'],));flash('Material added.');return redirect(url_for('admin_materials'))
        except Exception as e:flash(str(e))
    return simple_admin_form('Add Material',[('name','Name','text')],'admin_material_add')
@app.route('/admin/materials/edit/<int:item_id>',methods=['GET','POST'])
@admin_required
def admin_material_edit(item_id):
    item=query('SELECT * FROM materials WHERE id=?',(item_id,),one=True)
    if request.method=='POST':execute('UPDATE materials SET name=?,active=? WHERE id=?',(request.form['name'],to_int(request.form.get('active'),1),item_id));return redirect(url_for('admin_materials'))
    return simple_admin_form('Edit Material',[('name','Name','text'),('active','Active (1/0)','number')],'admin_material_edit',item)
@app.get('/admin/materials/toggle/<int:item_id>')
@admin_required
def admin_material_toggle(item_id):execute('UPDATE materials SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_materials'))
@app.get('/admin/materials/delete/<int:item_id>')
@admin_required
def admin_material_delete(item_id):execute('DELETE FROM materials WHERE id=?',(item_id,));return redirect(url_for('admin_materials'))

@app.route('/admin/products')
@admin_required
def admin_products():
    rows=query('SELECT p.*,c.name category_name,m.name material_name FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN materials m ON m.id=p.material_id ORDER BY p.id DESC')
    body='''<h1>Products</h1><p><a class="btn gold" href="{{url_for('admin_product_add')}}">Add Product</a> <a class="btn light" href="{{url_for('admin_dashboard')}}">Dashboard</a></p><div class="box table-wrap"><table><tr><th>ID</th><th>Product</th><th>Price</th><th>Category</th><th>Material</th><th>Stock</th><th>Active</th><th>Actions</th></tr>{% for r in rows %}<tr><td>{{r.id}}</td><td>{{r.name}}</td><td>{{r.price}}</td><td>{{r.category_name}}</td><td>{{r.material_name}}</td><td>{{r.stock}}</td><td>{{r.active}}</td><td class="actions"><a class="btn" href="{{url_for('admin_product_edit',item_id=r.id)}}">Edit</a><a class="btn light" href="{{url_for('admin_product_toggle',item_id=r.id)}}">Toggle</a><a class="btn danger" href="{{url_for('admin_product_delete',item_id=r.id)}}">Delete</a></td></tr>{% endfor %}</table></div>''';return render_admin(body,'Products',rows=rows)
def product_form(item=None):
    cats=query('SELECT * FROM categories ORDER BY name');mats=query('SELECT * FROM materials ORDER BY name')
    body='''<div class="box"><h1>{{'Edit' if item else 'Add'}} Product</h1><form method="post"><div class="form-grid"><div><label>Name</label><input name="name" value="{{item.name if item else ''}}" required></div><div><label>Price</label><input type="number" step="0.01" name="price" value="{{item.price if item else ''}}" required></div><div><label>Stock</label><input type="number" name="stock" value="{{item.stock if item else 0}}"></div><div><label>Category</label><select name="category_id">{% for c in cats %}<option value="{{c.id}}" {% if item and item.category_id==c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select></div><div><label>Material</label><select name="material_id"><option value="">None</option>{% for m in mats %}<option value="{{m.id}}" {% if item and item.material_id==m.id %}selected{% endif %}>{{m.name}}</option>{% endfor %}</select></div><div><label>Active (1/0)</label><input type="number" name="active" value="{{item.active if item else 1}}"></div><div style="grid-column:1/-1"><label>Image URL</label><input name="image" value="{{item.image if item else ''}}"></div><div style="grid-column:1/-1"><label>Description</label><textarea name="description">{{item.description if item else ''}}</textarea></div></div><br><button class="btn gold">Save</button></form></div>''';return render_admin(body,'Product',item=item,cats=cats,mats=mats)
@app.route('/admin/products/add',methods=['GET','POST'])
@admin_required
def admin_product_add():
    if request.method=='POST':insert_get_id('INSERT INTO products(name,description,price,image,category_id,material_id,stock,active) VALUES(?,?,?,?,?,?,?,?)',(request.form['name'],request.form.get('description',''),to_float(request.form['price']),request.form.get('image',''),to_int(request.form.get('category_id')),to_int(request.form.get('material_id')) or None,to_int(request.form.get('stock')),to_int(request.form.get('active'),1)));flash('Product added.');return redirect(url_for('admin_products'))
    return product_form()
@app.route('/admin/products/edit/<int:item_id>',methods=['GET','POST'])
@admin_required
def admin_product_edit(item_id):
    item=query('SELECT * FROM products WHERE id=?',(item_id,),one=True)
    if request.method=='POST':execute('UPDATE products SET name=?,description=?,price=?,image=?,category_id=?,material_id=?,stock=?,active=? WHERE id=?',(request.form['name'],request.form.get('description',''),to_float(request.form['price']),request.form.get('image',''),to_int(request.form.get('category_id')),to_int(request.form.get('material_id')) or None,to_int(request.form.get('stock')),to_int(request.form.get('active'),1),item_id));flash('Product updated.');return redirect(url_for('admin_products'))
    return product_form(item)
@app.get('/admin/products/toggle/<int:item_id>')
@admin_required
def admin_product_toggle(item_id):execute('UPDATE products SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_products'))
@app.get('/admin/products/delete/<int:item_id>')
@admin_required
def admin_product_delete(item_id):execute('DELETE FROM products WHERE id=?',(item_id,));return redirect(url_for('admin_products'))

@app.get('/admin/orders')
@admin_required
def admin_orders():
    rows=query('SELECT o.*,b.name bank_name FROM orders o LEFT JOIN banks b ON o.bank_id=b.id ORDER BY o.id DESC');body='''<h1>Orders</h1><div class="box table-wrap"><table><tr><th>ID</th><th>Customer</th><th>Total</th><th>Payment</th><th>Status</th><th>Date</th><th>Action</th></tr>{% for o in rows %}<tr><td>{{o.id}}</td><td>{{o.customer_name}}<br>{{o.phone}}</td><td>{{currency}} {{'%.2f'|format(o.total)}}</td><td>{{o.payment_method}}{% if o.bank_name %}<br>{{o.bank_name}}{% endif %}</td><td>{{o.status}}</td><td>{{o.created_at}}</td><td><form method="post" action="{{url_for('admin_order_status',item_id=o.id)}}"><select name="status">{% for s in statuses %}<option {% if s==o.status %}selected{% endif %}>{{s}}</option>{% endfor %}</select><button class="btn">Save</button></form></td></tr>{% endfor %}</table></div>''';return render_admin(body,'Orders',rows=rows,currency=get_setting('currency','PKR'),statuses=['Pending','Processing','Shipped','Delivered','Cancelled'])
@app.post('/admin/orders/status/<int:item_id>')
@admin_required
def admin_order_status(item_id):execute('UPDATE orders SET status=? WHERE id=?',(request.form.get('status'),item_id));return redirect(url_for('admin_orders'))

@app.get('/admin/reviews')
@admin_required
def admin_reviews():
    rows=query('SELECT r.*,p.name product_name FROM reviews r LEFT JOIN products p ON p.id=r.product_id ORDER BY r.id DESC');body='''<h1>Reviews</h1><div class="box table-wrap"><table><tr><th>Product</th><th>Name</th><th>Rating</th><th>Comment</th><th>Approved</th><th>Actions</th></tr>{% for r in rows %}<tr><td>{{r.product_name}}</td><td>{{r.name}}</td><td>{{r.rating}}</td><td>{{r.comment}}</td><td>{{r.approved}}</td><td><a class="btn" href="{{url_for('admin_review_toggle',item_id=r.id)}}">Toggle</a><a class="btn danger" href="{{url_for('admin_review_delete',item_id=r.id)}}">Delete</a></td></tr>{% endfor %}</table></div>''';return render_admin(body,'Reviews',rows=rows)
@app.get('/admin/reviews/toggle/<int:item_id>')
@admin_required
def admin_review_toggle(item_id):execute('UPDATE reviews SET approved=CASE approved WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_reviews'))
@app.get('/admin/reviews/delete/<int:item_id>')
@admin_required
def admin_review_delete(item_id):execute('DELETE FROM reviews WHERE id=?',(item_id,));return redirect(url_for('admin_reviews'))

@app.get('/admin/coupons')
@admin_required
def admin_coupons():
    rows=query('SELECT * FROM coupons ORDER BY id DESC');body='''<h1>Coupons</h1><p><a class="btn gold" href="{{url_for('admin_coupon_add')}}">Add Coupon</a></p><div class="box table-wrap"><table><tr><th>Code</th><th>Type</th><th>Value</th><th>Minimum</th><th>Active</th><th>Actions</th></tr>{% for r in rows %}<tr><td>{{r.code}}</td><td>{{r.discount_type}}</td><td>{{r.discount_value}}</td><td>{{r.min_amount}}</td><td>{{r.active}}</td><td><a class="btn" href="{{url_for('admin_coupon_edit',item_id=r.id)}}">Edit</a><a class="btn light" href="{{url_for('admin_coupon_toggle',item_id=r.id)}}">Toggle</a><a class="btn danger" href="{{url_for('admin_coupon_delete',item_id=r.id)}}">Delete</a></td></tr>{% endfor %}</table></div>''';return render_admin(body,'Coupons',rows=rows)
def coupon_form(item=None):
    body='''<div class="box"><h1>{{'Edit' if item else 'Add'}} Coupon</h1><form method="post"><label>Code</label><input name="code" value="{{item.code if item else ''}}" required><label>Type</label><select name="discount_type"><option {% if item and item.discount_type=='percent' %}selected{% endif %}>percent</option><option {% if item and item.discount_type=='fixed' %}selected{% endif %}>fixed</option></select><label>Value</label><input type="number" step="0.01" name="discount_value" value="{{item.discount_value if item else 0}}"><label>Minimum amount</label><input type="number" step="0.01" name="min_amount" value="{{item.min_amount if item else 0}}"><label>Active (1/0)</label><input type="number" name="active" value="{{item.active if item else 1}}"><br><button class="btn gold">Save</button></form></div>''';return render_admin(body,'Coupon',item=item)
@app.route('/admin/coupons/add',methods=['GET','POST'])
@admin_required
def admin_coupon_add():
    if request.method=='POST':insert_get_id('INSERT INTO coupons(code,discount_type,discount_value,min_amount,active) VALUES(?,?,?,?,?)',(request.form['code'].strip().upper(),request.form.get('discount_type','percent'),to_float(request.form.get('discount_value')),to_float(request.form.get('min_amount')),to_int(request.form.get('active'),1)));return redirect(url_for('admin_coupons'))
    return coupon_form()
@app.route('/admin/coupons/edit/<int:item_id>',methods=['GET','POST'])
@admin_required
def admin_coupon_edit(item_id):
    item=query('SELECT * FROM coupons WHERE id=?',(item_id,),one=True)
    if request.method=='POST':execute('UPDATE coupons SET code=?,discount_type=?,discount_value=?,min_amount=?,active=? WHERE id=?',(request.form['code'].strip().upper(),request.form.get('discount_type'),to_float(request.form.get('discount_value')),to_float(request.form.get('min_amount')),to_int(request.form.get('active'),1),item_id));return redirect(url_for('admin_coupons'))
    return coupon_form(item)
@app.get('/admin/coupons/toggle/<int:item_id>')
@admin_required
def admin_coupon_toggle(item_id):execute('UPDATE coupons SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_coupons'))
@app.get('/admin/coupons/delete/<int:item_id>')
@admin_required
def admin_coupon_delete(item_id):execute('DELETE FROM coupons WHERE id=?',(item_id,));return redirect(url_for('admin_coupons'))

@app.get('/admin/banks')
@admin_required
def admin_banks():
    rows=query('SELECT * FROM banks ORDER BY id DESC');body='''<h1>Banks</h1><p><a class="btn gold" href="{{url_for('admin_bank_add')}}">Add Bank</a></p><div class="box table-wrap"><table><tr><th>Name</th><th>Account Title</th><th>Account Number</th><th>IBAN</th><th>Active</th><th>Actions</th></tr>{% for r in rows %}<tr><td>{{r.name}}</td><td>{{r.account_title}}</td><td>{{r.account_number}}</td><td>{{r.iban}}</td><td>{{r.active}}</td><td><a class="btn" href="{{url_for('admin_bank_edit',item_id=r.id)}}">Edit</a><a class="btn light" href="{{url_for('admin_bank_toggle',item_id=r.id)}}">Toggle</a><a class="btn danger" href="{{url_for('admin_bank_delete',item_id=r.id)}}">Delete</a></td></tr>{% endfor %}</table></div>''';return render_admin(body,'Banks',rows=rows)
def bank_form(item=None):
    body='''<div class="box"><h1>{{'Edit' if item else 'Add'}} Bank</h1><form method="post">{% for n,l in [('name','Bank Name'),('account_title','Account Title'),('account_number','Account Number'),('iban','IBAN')]}<label>{{l}}</label><input name="{{n}}" value="{{item[n] if item else ''}}">{% endfor %}<label>Note</label><textarea name="note">{{item.note if item else ''}}</textarea><label>Active (1/0)</label><input type="number" name="active" value="{{item.active if item else 1}}"><br><button class="btn gold">Save</button></form></div>''';return render_admin(body,'Bank',item=item)
@app.route('/admin/banks/add',methods=['GET','POST'])
@admin_required
def admin_bank_add():
    if request.method=='POST':insert_get_id('INSERT INTO banks(name,account_title,account_number,iban,note,active) VALUES(?,?,?,?,?,?)',tuple(request.form.get(x,'') for x in ['name','account_title','account_number','iban','note'])+(to_int(request.form.get('active'),1),));return redirect(url_for('admin_banks'))
    return bank_form()
@app.route('/admin/banks/edit/<int:item_id>',methods=['GET','POST'])
@admin_required
def admin_bank_edit(item_id):
    item=query('SELECT * FROM banks WHERE id=?',(item_id,),one=True)
    if request.method=='POST':execute('UPDATE banks SET name=?,account_title=?,account_number=?,iban=?,note=?,active=? WHERE id=?',(request.form.get('name'),request.form.get('account_title'),request.form.get('account_number'),request.form.get('iban'),request.form.get('note'),to_int(request.form.get('active'),1),item_id));return redirect(url_for('admin_banks'))
    return bank_form(item)
@app.get('/admin/banks/toggle/<int:item_id>')
@admin_required
def admin_bank_toggle(item_id):execute('UPDATE banks SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(item_id,));return redirect(url_for('admin_banks'))
@app.get('/admin/banks/delete/<int:item_id>')
@admin_required
def admin_bank_delete(item_id):execute('DELETE FROM banks WHERE id=?',(item_id,));return redirect(url_for('admin_banks'))

@app.route('/admin/settings',methods=['GET','POST'])
@admin_required
def admin_settings():
    if request.method=='POST':
        for k in DEFAULT_SETTINGS:
            v=request.form.get(k)
            if k.endswith('_enabled'):v='1' if request.form.get(k) else '0'
            if v is not None:set_setting(k,v)
        flash('Settings saved.');return redirect(url_for('admin_settings'))
    body='''<div class="box"><h1>Store Settings</h1><form method="post"><div class="form-grid"><div><label>Store Name</label><input name="store_name" value="{{s.store_name}}"></div><div><label>Tagline</label><input name="tagline" value="{{s.tagline}}"></div><div><label>Currency</label><input name="currency" value="{{s.currency}}"></div><div><label>Shipping Fee</label><input name="shipping_fee" value="{{s.shipping_fee}}"></div><div><label>Free Shipping Minimum</label><input name="free_shipping_min" value="{{s.free_shipping_min}}"></div>{% for k in ['cod_enabled','bank_transfer_enabled','easypaisa_enabled','jazzcash_enabled'] %}<div class="check"><input type="checkbox" name="{{k}}" {% if s[k]=='1' %}checked{% endif %}><label>{{k}}</label></div>{% endfor %}<div><label>EasyPaisa Name</label><input name="easypaisa_name" value="{{s.easypaisa_name}}"></div><div><label>EasyPaisa Number</label><input name="easypaisa_number" value="{{s.easypaisa_number}}"></div><div><label>JazzCash Name</label><input name="jazzcash_name" value="{{s.jazzcash_name}}"></div><div><label>JazzCash Number</label><input name="jazzcash_number" value="{{s.jazzcash_number}}"></div></div><br><button class="btn gold">Save Settings</button></form></div>'''
    s={k:get_setting(k,v) for k,v in DEFAULT_SETTINGS.items()};return render_admin(body,'Settings',s=s)
@app.route('/admin/password',methods=['GET','POST'])
@admin_required
def admin_password():
    if request.method=='POST':
        u=query('SELECT * FROM admin_users WHERE id=?',(session['admin_id'],),one=True)
        if not check_password_hash(u['password_hash'],request.form.get('current','')):flash('Current password is incorrect.')
        elif request.form.get('new')!=request.form.get('confirm'):flash('New passwords do not match.')
        else:execute('UPDATE admin_users SET password_hash=? WHERE id=?',(generate_password_hash(request.form.get('new')),session['admin_id']));flash('Password changed.');return redirect(url_for('admin_dashboard'))
    body='''<div class="box" style="max-width:600px"><h1>Change Password</h1><form method="post"><label>Current Password</label><input type="password" name="current" required><label>New Password</label><input type="password" name="new" required><label>Confirm</label><input type="password" name="confirm" required><br><button class="btn gold">Change Password</button></form></div>''';return render_admin(body,'Password')
@app.get('/admin/sales')
@admin_required
def admin_sales():
    total=to_float(query('SELECT COALESCE(SUM(total),0) n FROM orders WHERE status!=?',('Cancelled',),one=True)['n']);count=query('SELECT COUNT(*) n FROM orders WHERE status!=?',('Cancelled',),one=True)['n'];recent=query('SELECT * FROM orders ORDER BY id DESC LIMIT 10');body='''<h1>Sales</h1><div class="cards"><div class="stat"><h2>{{currency}} {{'%.2f'|format(total)}}</h2><p>Total Sales</p></div><div class="stat"><h2>{{count}}</h2><p>Valid Orders</p></div></div><div class="box table-wrap"><table><tr><th>ID</th><th>Customer</th><th>Total</th><th>Status</th><th>Date</th></tr>{% for r in recent %}<tr><td>{{r.id}}</td><td>{{r.customer_name}}</td><td>{{currency}} {{'%.2f'|format(r.total)}}</td><td>{{r.status}}</td><td>{{r.created_at}}</td></tr>{% endfor %}</table></div>''';return render_admin(body,'Sales',total=total,count=count,recent=recent,currency=get_setting('currency','PKR'))

@app.errorhandler(404)
def not_found(e):return render_store('<div class="box"><h1>404</h1><p>Page not found.</p><a class="btn" href="'+url_for('home')+'">Home</a></div>','404'),404
@app.errorhandler(500)
def server_error(e):return render_store('<div class="box"><h1>Application Error</h1><p>Check the VS Code terminal for the exact error.</p><a class="btn" href="'+url_for('home')+'">Home</a></div>','Error'),500

if __name__=='__main__':
    try:
        initialize_database()
        print('='*70);print('JEWEL VOGUE');print('='*70);print('Database:', 'PostgreSQL' if USE_POSTGRES else 'SQLite')
        if not USE_POSTGRES: print('SQLite file:',SQLITE_DB)
        print('Website: http://127.0.0.1:5051');print('Admin: http://127.0.0.1:5051/admin/login');print('='*70)
        app.run(host='127.0.0.1',port=5051,debug=True)
    except Exception as e:
        print('\nDATABASE STARTUP ERROR\n',e)
        raise
