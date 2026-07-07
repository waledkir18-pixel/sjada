from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json, os, uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production-!@#$%')

BASE_DIR      = os.path.dirname(__file__)
DATA_DIR      = os.path.join(BASE_DIR, 'data')
USERS_FILE    = os.path.join(DATA_DIR, 'users.json')
PRODUCTS_FILE = os.path.join(DATA_DIR, 'products.json')
ORDERS_FILE   = os.path.join(DATA_DIR, 'orders.json')
STORE_EMAIL   = 'zarreen.store@gmail.com'

# ── JSON helpers ──────────────────────────────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('ليس لديك صلاحية الوصول', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Auth routes ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        users_data = load_json(USERS_FILE, {})
        if not name or not email or not password:
            flash('جميع الحقول مطلوبة', 'danger'); return render_template('auth/signup.html')
        if password != confirm:
            flash('كلمتا المرور غير متطابقتين', 'danger'); return render_template('auth/signup.html')
        if len(password) < 6:
            flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'danger'); return render_template('auth/signup.html')
        if email in users_data:
            flash('البريد الإلكتروني مسجل مسبقاً', 'danger'); return render_template('auth/signup.html')
        users_data[email] = {
            'id': str(uuid.uuid4()), 'name': name, 'email': email,
            'password': generate_password_hash(password),
            'is_admin': False, 'created_at': datetime.now().isoformat()
        }
        save_json(USERS_FILE, users_data)
        flash('تم إنشاء حسابك بنجاح!', 'success')
        return redirect(url_for('login'))
    return render_template('auth/signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email      = request.form.get('email', '').strip().lower()
        password   = request.form.get('password', '')
        users_data = load_json(USERS_FILE, {})
        user       = users_data.get(email)
        if user and check_password_hash(user['password'], password):
            session.permanent   = True
            session['user_id']  = user['id']
            session['name']     = user['name']
            session['email']    = email
            session['is_admin'] = user.get('is_admin', False)
            flash(f'مرحباً {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/home.html')

# ── Store ─────────────────────────────────────────────────────────────────────
@app.route('/store')
@login_required
def store():
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    return render_template('store/index.html',
                           product_items=data.get('items', []),
                           product_cats=data.get('categories', []))

@app.route('/store/order', methods=['POST'])
@login_required
def place_order():
    product_id  = request.form.get('product_id', '')
    notes       = request.form.get('notes', '').strip()
    custom_size = request.form.get('custom_size', '').strip()
    color       = request.form.get('color', '').strip()

    data    = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    product = next((p for p in data['items'] if p['id'] == product_id), None)
    if not product:
        flash('المنتج غير موجود', 'danger')
        return redirect(url_for('store'))

    orders = load_json(ORDERS_FILE, [])
    orders.append({
        'id':           str(uuid.uuid4()),
        'product_id':   product_id,
        'product_name': product['name'],
        'price':        product['price'],
        'category':     product['category'],
        'user_id':      session['user_id'],
        'user_name':    session['name'],
        'user_email':   session['email'],
        'notes':        notes,
        'custom_size':  custom_size,
        'color':        color,
        'status':       'pending',
        'created_at':   datetime.now().isoformat()
    })
    save_json(ORDERS_FILE, orders)
    flash('تم إرسال طلبك بنجاح! سنتواصل معك قريباً', 'success')
    return redirect(url_for('my_orders'))

@app.route('/store/my-orders')
@login_required
def my_orders():
    orders = load_json(ORDERS_FILE, [])
    my = [o for o in orders if o['user_id'] == session['user_id']]
    my.sort(key=lambda x: x['created_at'], reverse=True)
    return render_template('store/my_orders.html', orders=my)

# ── Web Design ────────────────────────────────────────────────────────────────
@app.route('/webdesign')
@login_required
def webdesign():
    return render_template('web_design/index.html')

# ── Admin ─────────────────────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_panel():
    data        = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    users_data  = load_json(USERS_FILE, {})
    orders      = load_json(ORDERS_FILE, [])
    pending     = [o for o in orders if o['status'] == 'pending']
    return render_template('admin/panel.html',
                           product_items=data.get('items', []),
                           product_cats=data.get('categories', []),
                           user_count=len(users_data),
                           orders=orders,
                           pending_count=len(pending),
                           store_email=STORE_EMAIL)

@app.route('/admin/product/add', methods=['POST'])
@admin_required
def admin_add_product():
    name     = request.form.get('name', '').strip()
    price    = request.form.get('price', '0')
    category = request.form.get('category', '').strip()
    desc     = request.form.get('description', '').strip()
    badge    = request.form.get('badge', '').strip()
    if not name or not category:
        flash('اسم المنتج والتصنيف مطلوبان', 'danger')
        return redirect(url_for('admin_panel'))
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    if category not in data['categories']:
        data['categories'].append(category)
    data['items'].append({
        'id': str(uuid.uuid4()), 'name': name,
        'price': float(price), 'category': category,
        'description': desc, 'badge': badge,
        'created_at': datetime.now().isoformat()
    })
    save_json(PRODUCTS_FILE, data)
    flash(f'تمت إضافة "{name}" بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/category/add', methods=['POST'])
@admin_required
def admin_add_category():
    cat = request.form.get('category', '').strip()
    if not cat:
        flash('اسم التصنيف مطلوب', 'danger')
        return redirect(url_for('admin_panel'))
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    if cat not in data['categories']:
        data['categories'].append(cat)
        save_json(PRODUCTS_FILE, data)
        flash(f'تمت إضافة تصنيف "{cat}"', 'success')
    else:
        flash('التصنيف موجود مسبقاً', 'warning')
    return redirect(url_for('admin_panel'))

@app.route('/admin/category/delete', methods=['POST'])
@admin_required
def admin_delete_category():
    cat  = request.form.get('category', '').strip()
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    data['categories'] = [c for c in data['categories'] if c != cat]
    save_json(PRODUCTS_FILE, data)
    flash(f'تم حذف تصنيف "{cat}"', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/product/delete/<product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    data['items'] = [p for p in data['items'] if p['id'] != product_id]
    save_json(PRODUCTS_FILE, data)
    flash('تم حذف المنتج', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/product/edit/<product_id>', methods=['POST'])
@admin_required
def admin_edit_product(product_id):
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    for item in data['items']:
        if item['id'] == product_id:
            item['name']        = request.form.get('name', item['name']).strip()
            item['price']       = float(request.form.get('price', item['price']))
            item['category']    = request.form.get('category', item['category']).strip()
            item['description'] = request.form.get('description', item['description']).strip()
            item['badge']       = request.form.get('badge', item.get('badge', '')).strip()
            break
    save_json(PRODUCTS_FILE, data)
    flash('تم تحديث المنتج', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/order/<order_id>/status', methods=['POST'])
@admin_required
def admin_update_order(order_id):
    status = request.form.get('status', '')
    orders = load_json(ORDERS_FILE, [])
    for o in orders:
        if o['id'] == order_id:
            o['status'] = status
            o['updated_at'] = datetime.now().isoformat()
            break
    save_json(ORDERS_FILE, orders)
    flash(f'تم تحديث حالة الطلب إلى: {status}', 'success')
    return redirect(url_for('admin_panel'))

# ── Seed ──────────────────────────────────────────────────────────────────────
def seed_data():
    # Admin
    users_data  = load_json(USERS_FILE, {})
    admin_email = 'admin@zarreen.com'
    if admin_email not in users_data:
        users_data[admin_email] = {
            'id': str(uuid.uuid4()), 'name': 'مدير المتجر',
            'email': admin_email,
            'password': generate_password_hash('admin123'),
            'is_admin': True, 'created_at': datetime.now().isoformat()
        }
        save_json(USERS_FILE, users_data)
        print('✅ Admin → admin@zarreen.com / admin123')

    # Demo products
    data = load_json(PRODUCTS_FILE, {'categories': [], 'items': []})
    if not data['items']:
        data['categories'] = ['شراشف جاهزة', 'تفصيل شراشف', 'إكسسوارات']
        data['items'] = [
            {'id': str(uuid.uuid4()), 'name': 'شرشف قطن فاخر', 'price': 89.00,
             'category': 'شراشف جاهزة', 'description': 'قطن 100% ناعم ومريح',
             'badge': 'الأكثر مبيعاً', 'created_at': datetime.now().isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'شرشف ساتان ملكي', 'price': 145.00,
             'category': 'شراشف جاهزة', 'description': 'ساتان فاخر بلمسة ملكية',
             'badge': 'جديد', 'created_at': datetime.now().isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'شرشف مطرز يدوي', 'price': 220.00,
             'category': 'شراشف جاهزة', 'description': 'تطريز يدوي أصيل',
             'badge': '', 'created_at': datetime.now().isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'تفصيل شرشف بمقاساتك', 'price': 0,
             'category': 'تفصيل شراشف', 'description': 'حدد مقاساتك وسنفصّل لك',
             'badge': 'حسب الطلب', 'created_at': datetime.now().isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'تفصيل مطرز خاص', 'price': 0,
             'category': 'تفصيل شراشف', 'description': 'تطريز باسمك أو اختيارك',
             'badge': 'مخصص', 'created_at': datetime.now().isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'حقيبة حفظ الشرشف', 'price': 35.00,
             'category': 'إكسسوارات', 'description': 'حقيبة قماش أنيقة للحفظ',
             'badge': '', 'created_at': datetime.now().isoformat()},
        ]
        save_json(PRODUCTS_FILE, data)
        print('✅ Demo products seeded')

if __name__ == '__main__':
    seed_data()
    app.run(debug=True, port=5000)