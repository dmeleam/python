from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import sqlite3
import os
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash, email, is_admin):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.is_admin = is_admin == 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_administrator(self):
        return self.is_admin

# Database setup
DB_PATH = 'volunteer_tracker.db'

# Add this to your init_db function in your Flask app

def init_db():
    # Create database if it doesn't exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create volunteer logs table (existing table)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS volunteer_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_name TEXT NOT NULL,
        animal_name TEXT NOT NULL,
        location TEXT NOT NULL,
        log_date TEXT NOT NULL,
        hours REAL NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    
    # Create locations table (existing table)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        active INTEGER DEFAULT 1
    )
    ''')
    
    # Create users table (new table)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')
    
    # Insert default locations if table is empty
    cursor.execute('SELECT COUNT(*) FROM locations')
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_locations = [
            ('Park',), 
            ('School',), 
            ('Hospital',), 
            ('Nursing Home',), 
            ('Community Center',), 
            ('Library',),
            ('Other',)
        ]
        cursor.executemany('INSERT INTO locations (name) VALUES (?)', default_locations)
    
    # Create an admin user if users table is empty
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Create admin user with password "admin123"
        from werkzeug.security import generate_password_hash
        admin_password_hash = generate_password_hash('admin123')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
        INSERT INTO users (username, password_hash, email, is_admin, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', ('admin', admin_password_hash, 'admin@example.com', 1, timestamp))
    
    conn.commit()
    conn.close()

# Initialize database when the app starts
init_db()

@app.route('/')
def home():
    # Fetch logs from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    
    # Fetch logs
    cursor.execute('SELECT * FROM volunteer_logs ORDER BY timestamp DESC')
    logs = [dict(row) for row in cursor.fetchall()]
    
    # Fetch active locations for the dropdown
    cursor.execute('SELECT name FROM locations WHERE active = 1 ORDER BY name')
    locations = [row['name'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('index.html', logs=logs, locations=locations)

@app.route('/admin')
@login_required
def admin():
    # Check if user is an admin
    if not current_user.is_administrator():
        return redirect(url_for('home'))
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get basic stats
    cursor.execute('SELECT COUNT(*) as total_logs FROM volunteer_logs')
    total_logs = cursor.fetchone()['total_logs']
    
    cursor.execute('SELECT COUNT(DISTINCT volunteer_name) as total_volunteers FROM volunteer_logs')
    total_volunteers = cursor.fetchone()['total_volunteers']
    
    cursor.execute('SELECT COUNT(DISTINCT animal_name) as total_animals FROM volunteer_logs')
    total_animals = cursor.fetchone()['total_animals']
    
    cursor.execute('SELECT SUM(hours) as total_hours FROM volunteer_logs')
    total_hours = cursor.fetchone()['total_hours'] or 0
    
    # Recent logs
    cursor.execute('SELECT * FROM volunteer_logs ORDER BY timestamp DESC LIMIT 10')
    recent_logs = [dict(row) for row in cursor.fetchall()]
    
    # Top volunteers
    cursor.execute('''
        SELECT volunteer_name, SUM(hours) as total_hours 
        FROM volunteer_logs 
        GROUP BY volunteer_name 
        ORDER BY total_hours DESC 
        LIMIT 5
    ''')
    top_volunteers = [dict(row) for row in cursor.fetchall()]
    
    # Top locations
    cursor.execute('''
        SELECT location, COUNT(*) as visit_count 
        FROM volunteer_logs 
        GROUP BY location 
        ORDER BY visit_count DESC
    ''')
    top_locations = [dict(row) for row in cursor.fetchall()]
    
    # Top animals
    cursor.execute('''
        SELECT animal_name, COUNT(*) as visit_count, SUM(hours) as total_hours
        FROM volunteer_logs 
        GROUP BY animal_name 
        ORDER BY total_hours DESC
    ''')
    top_animals = [dict(row) for row in cursor.fetchall()]
    
    # Monthly hours
    cursor.execute('''
        SELECT 
            strftime('%Y-%m', log_date) as month,
            SUM(hours) as monthly_hours
        FROM volunteer_logs
        GROUP BY month
        ORDER BY month
    ''')
    monthly_hours = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin.html', 
                          total_logs=total_logs,
                          total_volunteers=total_volunteers,
                          total_animals=total_animals,
                          total_hours=total_hours,
                          recent_logs=recent_logs,
                          top_volunteers=top_volunteers,
                          top_locations=top_locations,
                          top_animals=top_animals,
                          monthly_hours=monthly_hours)

@app.route('/admin/locations')
def manage_locations():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM locations ORDER BY name')
    locations = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('manage_locations.html', locations=locations)

@app.route('/admin/locations/add', methods=['POST'])
def add_location():
    location_name = request.form.get('location_name', '').strip()
    
    if location_name:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO locations (name) VALUES (?)', (location_name,))
            conn.commit()
        except sqlite3.IntegrityError:
            # Location already exists
            pass
        finally:
            conn.close()
    
    return redirect(url_for('manage_locations'))

@app.route('/admin/logs')
def manage_logs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM volunteer_logs ORDER BY log_date DESC, timestamp DESC')
    logs = [dict(row) for row in cursor.fetchall()]
    
    # Fetch locations for the edit form
    cursor.execute('SELECT name FROM locations WHERE active = 1 ORDER BY name')
    locations = [row['name'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('manage_logs.html', logs=logs, locations=locations)

@app.route('/admin/logs/edit/<int:log_id>', methods=['GET', 'POST'])
def edit_log(log_id):
    if request.method == 'POST':
        # Update log with form data
        volunteer_name = request.form.get('volunteer_name')
        animal_name = request.form.get('animal_name')
        location = request.form.get('location')
        log_date = request.form.get('log_date')
        hours = float(request.form.get('hours'))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE volunteer_logs 
            SET volunteer_name = ?, animal_name = ?, location = ?, log_date = ?, hours = ? 
            WHERE id = ?
        ''', (volunteer_name, animal_name, location, log_date, hours, log_id))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('manage_logs'))
    else:
        # Display edit form
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get log details
        cursor.execute('SELECT * FROM volunteer_logs WHERE id = ?', (log_id,))
        log = dict(cursor.fetchone())
        
        # Get locations for dropdown
        cursor.execute('SELECT name FROM locations ORDER BY name')
        locations = [row['name'] for row in cursor.fetchall()]
        
        conn.close()
        
        return render_template('edit_log.html', log=log, locations=locations)

@app.route('/admin/logs/delete/<int:log_id>')
def delete_log(log_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM volunteer_logs WHERE id = ?', (log_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('manage_logs'))

@app.route('/admin/locations/toggle/<int:location_id>')
def toggle_location(location_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current active state
    cursor.execute('SELECT active FROM locations WHERE id = ?', (location_id,))
    result = cursor.fetchone()
    
    if result:
        current_state = result[0]
        # Toggle state
        new_state = 0 if current_state == 1 else 1
        cursor.execute('UPDATE locations SET active = ? WHERE id = ?', (new_state, location_id))
        conn.commit()
    
    conn.close()
    
    return redirect(url_for('manage_locations'))

@app.route('/admin/locations/delete/<int:location_id>')
def delete_location(location_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if location is used in any logs
    cursor.execute('SELECT COUNT(*) FROM volunteer_logs WHERE location = (SELECT name FROM locations WHERE id = ?)', (location_id,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Safe to delete
        cursor.execute('DELETE FROM locations WHERE id = ?', (location_id,))
        conn.commit()
    
    conn.close()
    
    return redirect(url_for('manage_locations'))


@app.route('/log', methods=['POST'])
def log_hours():
    if request.method == 'POST':
        name = request.form.get('volunteer_name')
        animal_name = request.form.get('animal_name')
        location = request.form.get('location')
        date_str = request.form.get('date')
        hours = float(request.form.get('hours'))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert into database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO volunteer_logs 
        (volunteer_name, animal_name, location, log_date, hours, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, animal_name, location, date_str, hours, timestamp))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('home'))
    
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    conn.close()
    
    if user_data:
        return User(
            id=user_data['id'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            email=user_data['email'],
            is_admin=user_data['is_admin']
        )
    
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        conn.close()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                email=user_data['email'],
                is_admin=user_data['is_admin']
            )
            login_user(user)
            
            # Redirect to the page the user was trying to access, or home
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('home')
            
            return redirect(next_page)
        else:
            error = 'Invalid username or password'
    
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            error = 'Username already exists'
        else:
            # Create new user
            password_hash = generate_password_hash(password)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
            INSERT INTO users (username, password_hash, email, created_at)
            VALUES (?, ?, ?, ?)
            ''', (username, password_hash, email, timestamp))
            
            conn.commit()
            conn.close()
            
            return redirect(url_for('login'))
    
    return render_template('register.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)