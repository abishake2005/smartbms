from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB = 'business.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    conn.commit()
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
            conn.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, hashed))
            conn.commit()
            conn.close()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
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
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
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
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_services = conn.execute('SELECT COUNT(*) FROM services WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    recent_services = conn.execute('SELECT * FROM services WHERE user_id = ? ORDER BY id DESC LIMIT 5', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('dashboard.html', total_users=total_users, total_services=total_services, recent_services=recent_services)

@app.route('/services')
@login_required
def services():
    conn = get_db()
    all_services = conn.execute('SELECT * FROM services WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
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
            if price < 0:
                raise ValueError
        except ValueError:
            flash('Please enter a valid price.', 'error')
            return render_template('add_service.html')
        conn = get_db()
        conn.execute('INSERT INTO services (user_id, service_name, description, price) VALUES (?, ?, ?, ?)',
                     (session['user_id'], name, desc, price))
        conn.commit()
        conn.close()
        flash('Service added successfully!', 'success')
        return redirect(url_for('services'))
    return render_template('add_service.html')

@app.route('/edit_service/<int:service_id>', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    conn = get_db()
    service = conn.execute('SELECT * FROM services WHERE id = ? AND user_id = ?', (service_id, session['user_id'])).fetchone()
    if not service:
        conn.close()
        flash('Service not found.', 'error')
        return redirect(url_for('services'))
    if request.method == 'POST':
        name = request.form.get('service_name', '').strip()
        desc = request.form.get('description', '').strip()
        price = request.form.get('price', '')
        if not name or not price:
            flash('Service name and price are required.', 'error')
            return render_template('edit_service.html', service=service)
        try:
            price = float(price)
            if price < 0:
                raise ValueError
        except ValueError:
            flash('Please enter a valid price.', 'error')
            return render_template('edit_service.html', service=service)
        conn.execute('UPDATE services SET service_name = ?, description = ?, price = ? WHERE id = ? AND user_id = ?',
                     (name, desc, price, service_id, session['user_id']))
        conn.commit()
        conn.close()
        flash('Service updated successfully!', 'success')
        return redirect(url_for('services'))
    conn.close()
    return render_template('edit_service.html', service=service)

@app.route('/delete_service/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    conn = get_db()
    conn.execute('DELETE FROM services WHERE id = ? AND user_id = ?', (service_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Service deleted.', 'success')
    return redirect(url_for('services'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not check_password_hash(user['password'], old_pw):
            flash('Current password is incorrect.', 'error')
            conn.close()
            return render_template('profile.html', user=user)
        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            conn.close()
            return render_template('profile.html', user=user)
        if new_pw != confirm:
            flash('New passwords do not match.', 'error')
            conn.close()
            return render_template('profile.html', user=user)
        hashed = generate_password_hash(new_pw)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, session['user_id']))
        conn.commit()
        conn.close()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('profile'))
    conn.close()
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
    
