from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartbms-secret-2026')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS services (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        service_name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL
    )''')
    conn.commit()
    cur.close()
    conn.close()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute('INSERT INTO users (name, email, password) VALUES (%s, %s, %s)', (name, email, hashed))
            conn.commit()
            cur.close(); conn.close()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Email already registered.', 'error')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT COUNT(*) as count FROM users')
    total_users = cur.fetchone()['count']
    cur.execute('SELECT COUNT(*) as count FROM services WHERE user_id = %s', (session['user_id'],))
    total_services = cur.fetchone()['count']
    cur.execute('SELECT * FROM services WHERE user_id = %s ORDER BY id DESC LIMIT 5', (session['user_id'],))
    recent_services = cur.fetchall()
    cur.close(); conn.close()
    return render_template('dashboard.html', total_users=total_users,
                           total_services=total_services, recent_services=recent_services)

@app.route('/services')
@login_required
def services():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM services WHERE user_id = %s ORDER BY id DESC', (session['user_id'],))
    all_services = cur.fetchall()
    cur.close(); conn.close()
    return render_template('services.html', services=all_services)

@app.route('/add_service', methods=['GET', 'POST'])
@login_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('service_name', '').strip()
        desc = request.form.get('description', '').strip()
        price = request.form.get('price', '')
        if not name or not price:
            flash('Service name and price are required.', 'error')
            return render_template('add_service.html')
        try:
            price = float(price)
            if price < 0: raise ValueError
        except ValueError:
            flash('Please enter a valid price.', 'error')
            return render_template('add_service.html')
        conn = get_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO services (user_id, service_name, description, price) VALUES (%s, %s, %s, %s)',
                    (session['user_id'], name, desc, price))
        conn.commit()
        cur.close(); conn.close()
        flash('Service added successfully!', 'success')
        return redirect(url_for('services'))
    return render_template('add_service.html')

@app.route('/edit_service/<int:service_id>', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM services WHERE id = %s AND user_id = %s', (service_id, session['user_id']))
    service = cur.fetchone()
    if not service:
        cur.close(); conn.close()
        flash('Service not found.', 'error')
        return redirect(url_for('services'))
    if request.method == 'POST':
        name = request.form.get('service_name', '').strip()
        desc = request.form.get('description', '').strip()
        price = request.form.get('price', '')
        try:
            price = float(price)
            if price < 0: raise ValueError
        except ValueError:
            flash('Please enter a valid price.', 'error')
            return render_template('edit_service.html', service=service)
        cur.execute('UPDATE services SET service_name=%s, description=%s, price=%s WHERE id=%s AND user_id=%s',
                    (name, desc, price, service_id, session['user_id']))
        conn.commit()
        cur.close(); conn.close()
        flash('Service updated successfully!', 'success')
        return redirect(url_for('services'))
    cur.close(); conn.close()
    return render_template('edit_service.html', service=service)

@app.route('/delete_service/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM services WHERE id = %s AND user_id = %s', (service_id, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    flash('Service deleted.', 'success')
    return redirect(url_for('services'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cur.fetchone()
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not check_password_hash(user['password'], old_pw):
            flash('Current password is incorrect.', 'error')
            cur.close(); conn.close()
            return render_template('profile.html', user=user)
        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            cur.close(); conn.close()
            return render_template('profile.html', user=user)
        if new_pw != confirm:
            flash('New passwords do not match.', 'error')
            cur.close(); conn.close()
            return render_template('profile.html', user=user)
        hashed = generate_password_hash(new_pw)
        cur.execute('UPDATE users SET password = %s WHERE id = %s', (hashed, session['user_id']))
        conn.commit()
        cur.close(); conn.close()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('profile'))
    cur.close(); conn.close()
    return render_template('profile.html', user=user)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

init_db()

if __name__ == '__main__':
    app.run(debug=False)
