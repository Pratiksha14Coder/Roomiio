from flask import Flask, render_template, request, redirect, url_for, session, flash
from authlib.integrations.flask_client import OAuth
from datetime import datetime
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET  # Import credentials
from werkzeug.utils import secure_filename  # For secure file uploads
from werkzeug.security import generate_password_hash, check_password_hash
from config import DEFAULT_ADMINS, DEFAULT_WARDENS
import sqlite3
import hashlib
import os
import re
import socket
import dns.resolver

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "roomiio_dev_key")
oauth = OAuth(app)

# Google OAuth setup (unchanged)
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    api_base_url='https://www.googleapis.com/oauth2/v2/',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'}
)

# Database and other functions
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # ================== USERS TABLE ==================
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        room_id INTEGER,
        profile_pic TEXT DEFAULT 'static/images/default-profile.png'
    )
    ''')

    # ================== APPLICATIONS TABLE ==================
    c.execute('''
    CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    room_type TEXT,
    status TEXT DEFAULT 'pending',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_fee REAL DEFAULT 0,
    paid REAL DEFAULT 0,
    remaining REAL DEFAULT 0,
    due_date TIMESTAMP
)
''')    
    # ================== ROOMS TABLE ==================
    c.execute('''
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY,
        room_number TEXT,
        capacity INTEGER,
        occupied INTEGER DEFAULT 0
    )
    ''')

    # ================== FEES TABLE ==================
    c.execute('''
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        status TEXT DEFAULT 'unpaid'
    )
    ''')

    # ================== COMPLAINTS TABLE ==================
    c.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    help_topic TEXT,
    subject TEXT,
    complaint TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    reply TEXT DEFAULT NULL,      -- Admin's reply
    replied_at TIMESTAMP          -- When admin replied
)
    ''')
    c.execute('''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount_paid REAL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    method TEXT DEFAULT 'online'
)
''')

    # ================== INSERT ROOMS IF EMPTY ==================
    c.execute("SELECT COUNT(*) FROM rooms")
    room_count = c.fetchone()[0]
    if room_count == 0:
        # AC Girls AG101–AG115
        for i in range(101, 116):
            c.execute(
                "INSERT INTO rooms (room_number, capacity) VALUES (?, ?)",
                (f"AG{i}", 2)
                )
        # AC Boys AB116–AB130
        for i in range(116, 131):
            c.execute(\
                "INSERT INTO rooms (room_number, capacity) VALUES (?, ?)",
                (f"AB{i}", 2)
                )
        # Non AC Girls NAG131–NAG145
        for i in range(131, 146):
            c.execute(
                "INSERT INTO rooms (room_number, capacity) VALUES (?, ?)",
                (f"NAG{i}", 2)
                )
        # Non AC Boys NAB146–NAB160
        for i in range(146, 161):
            c.execute(
                "INSERT INTO rooms (room_number, capacity) VALUES (?, ?)",
                (f"NAB{i}", 2)
                )
    conn.commit()
    conn.close()
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== EMAIL VALIDATION FUNCTIONS ====================
# Add this simple email validation function BEFORE init_db()

def validate_email_simple(email):
    """
    Simple email format validation using regex
    """
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_regex, email):
        return True, "Valid email"
    return False, "Invalid email format!"

def validate_email_format(email):
    """
    Validate email format using regex
    Returns: (True/False, message)
    """
    # Basic email pattern
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_regex, email):
        return False, "Invalid email format!"
    
    # Extract domain
    domain = email.split('@')[1]
    
    # Check for valid domain structure
    if '.' not in domain:
        return False, "Invalid domain!"
    
    return True, "Valid email"

def validate_email_domain(email):
    """
    Validate email domain has valid MX records
    Requires: pip install dnspython
    Returns: (True/False, message)
    """
    domain = email.split('@')[1]
    
    try:
        # Check MX records
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            return True, "Valid email domain"
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, "Domain does not exist or has no mail server!"
    except Exception:
        return False, "Could not validate domain!"
    
    return False, "No mail server found for domain!"

def validate_email(email):
    """
    Complete email validation (format + domain)
    """
    # Step 1: Check format
    is_valid, message = validate_email_format(email)
    if not is_valid:
        return False, message
    
    # Step 2: Check domain (optional - comment out if issues)
    # is_valid, message = validate_email_domain(email)
    # if not is_valid:
    #     return False, message
    
    return True, "Valid email"

init_db()

# Context processor to make user data available in all templates
@app.context_processor
def inject_user():
    if 'user_id' in session:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT name, email, profile_pic FROM users WHERE id=?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        if user:
            return {'current_user': {'name': user[0], 'email': user[1], 'profile_pic': user[2]}}
    return {'current_user': None}
    
# ==================== DATABASE VIEWER ROUTES (ADMIN ONLY) ====================

@app.route('/view_database')
def view_database():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login_page'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied! Admin only.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    tables_data = []
    
    # Get all tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    tables = [t for t in tables if t[0] not in ['fees', 'payments']]  # Exclude fees and payments tables from database viewer
    
    for table in tables:
        table_name = table[0]
        
        # Get row count
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = c.fetchone()[0]
        
        # Get column names
        c.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in c.fetchall()]
        
        # Get data rows
        c.execute(f"SELECT * FROM {table_name}")
        rows = c.fetchall()
        
        tables_data.append({
            'name': table_name,
            'count': row_count,
            'columns': columns,
            'rows': rows
        })
    
    conn.close()
    
    return render_template('view_database.html', tables=tables_data)


@app.route('/view_table/<table_name>')
def view_table(table_name):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login_page'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied! Admin only.', 'error')
        return redirect(url_for('dashboard'))
    
    # Include 'complaints' table
    allowed_tables = ['users', 'rooms', 'applications', 'complaints']
    
    if table_name not in allowed_tables:
        flash('Invalid table name!', 'error')
        return redirect(url_for('view_database'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get row count
    c.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = c.fetchone()[0]
    
    # Get data
    c.execute(f"SELECT * FROM {table_name}")
    rows = c.fetchall()
    
    # Get columns
    c.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in c.fetchall()]
    
    conn.close()
    
    return render_template(
        'view_table.html',
        table_name=table_name,
        row_count=row_count,
        columns=columns,
        rows=rows
    )
# Routes (most unchanged, with additions for profile_pic and /profile)
@app.route('/')
def home():
    return render_template('index.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')
        role = request.form['role']
        secret_key = request.form.get('secret_key', '').strip()

        errors = []

        # Name & password validation
        if len(name) < 2:
            errors.append("Name must be at least 2 characters!")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters!")
        if password != confirm_password:
            errors.append("Password and Confirm Password do not match!")

        # Email validation
        is_valid, message = validate_email_simple(email)
        if not is_valid:
            errors.append(message)

        # Connect to DB
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Admin/Warden secret key + max limit check
        if role == 'admin':
            hashed_key = hashlib.sha256(secret_key.encode()).hexdigest()
            if hashed_key not in DEFAULT_ADMINS.values():
                errors.append("Invalid admin secret key!")
            else:
                c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
                if c.fetchone()[0] >= 2:
                    errors.append("Maximum number of admins reached!")

        elif role == 'warden':
            hashed_key = hashlib.sha256(secret_key.encode()).hexdigest()
            if hashed_key not in DEFAULT_WARDENS.values():
                errors.append("Invalid warden secret key!")
            else:
                c.execute("SELECT COUNT(*) FROM users WHERE role='warden'")
                if c.fetchone()[0] >= 2:
                    errors.append("Maximum number of wardens reached!")

        # Check if email already exists
        c.execute("SELECT email FROM users WHERE email=?", (email,))
        if c.fetchone():
            errors.append("Email already registered!")

        if errors:
            for error in errors:
                flash(error, 'error')
            conn.close()
            return redirect(url_for('register'))

        # Hash password & insert user
        hashed_password = generate_password_hash(password)
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                  (name, email, hashed_password, role))
        conn.commit()
        conn.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login_page'))

    return render_template('register.html')
#new login route that only checks email and password, and auto-fetches role from database for better security

@app.route('/login', methods=['POST'])
def login():

    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Fetch user by email only
    c.execute("SELECT id, name, role, password FROM users WHERE email=?", (email,))
    user = c.fetchone()

    conn.close()

    # Check password securely
    if user and check_password_hash(user[3], password):

        session['user_id'] = user[0]
        session['role'] = user[2]

        flash(f"Welcome back, {user[1]}!", "success")

        next_page = request.args.get('next')
        return redirect(url_for(next_page) if next_page else url_for('dashboard'))

    else:
        flash("Invalid email or password!", "error")
        return redirect(url_for('login_page'))

@app.route('/login_page')
def login_page():
    return render_template('login_page.html')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorized', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorized')
def authorized():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
    email = user_info['email']
    name = user_info['name']
    google_pic = user_info.get('picture', None)  # Google's profile pic

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Fetch user from DB
    c.execute("SELECT id, role, profile_pic FROM users WHERE email=?", (email,))
    user = c.fetchone()

    if not user:
        # New user, save Google pic if exists
        c.execute(
            "INSERT INTO users (name, email, role, profile_pic) VALUES (?, ?, 'student', ?)",
            (name, email, google_pic or 'static/images/default-profile.png')
        )
        conn.commit()
        user_id = c.lastrowid
        role = 'student'
        profile_pic = google_pic or 'static/images/default-profile.png'
    else:
        user_id, role, profile_pic = user
        # Only update profile_pic if it's still default
        if profile_pic == 'static/images/default-profile.png' and google_pic:
            c.execute("UPDATE users SET profile_pic=? WHERE id=?", (google_pic, user_id))
            conn.commit()
            profile_pic = google_pic  # update the variable

    conn.close()
    
    # Set session
    session['user_id'] = user_id
    session['role'] = role
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    role = session['role']
    user_id = session['user_id']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get user name and room_id
    c.execute("SELECT name, room_id FROM users WHERE id=?", (user_id,))
    user = c.fetchone()

    # Initialize data dictionary
    data = {'user': user[0], 'role': role}

    # ==================== STUDENT DASHBOARD ====================
    if role == 'student':
        room_id = user[1]

        room = None
        if room_id:
            c.execute("SELECT room_number FROM rooms WHERE id=?", (room_id,))
            room = c.fetchone()

        # Get approved application details from applications table
        c.execute("""
            SELECT room_type, status, total_fee, paid, remaining, due_date
            FROM applications
            WHERE user_id=? AND status='approved'
            ORDER BY applied_at DESC
            LIMIT 1
        """, (user_id,))
        approved_app = c.fetchone()

        # Calculate fees from approved application
        if approved_app:
            total_fee = approved_app[2] or 0
            paid = approved_app[3] or 0
            remaining = approved_app[4] or 0
            due_date = approved_app[5]
        else:
            total_fee = 0
            paid = 0
            remaining = 0
            due_date = None

        # Get all student applications
        c.execute("""
            SELECT room_type, status, applied_at
            FROM applications
            WHERE user_id=?
            ORDER BY applied_at DESC
        """, (user_id,))
        applications = c.fetchall()

        data.update({
            'room': room[0] if room else "Not Allocated",
            'total_fee': total_fee,
            'paid': paid,
            'remaining': remaining,
            'due_date': due_date,
            'applications': applications,
            'approved_application': approved_app
        })

    # ================= WARDEN DASHBOARD =================
    elif role == 'warden':
        total_seats = 120
        seats_per_category = 30
        seats_per_room = 2
        total_rooms = 60

        # Get total occupied from DB
        c.execute("SELECT SUM(occupied) FROM rooms")
        total_occupied = c.fetchone()[0] or 0

        available_seats = total_seats - total_occupied

        # Students without rooms
        c.execute("SELECT id, name FROM users WHERE role='student' AND room_id IS NULL")
        students = c.fetchall()

        # Room applications
        c.execute("""
            SELECT applications.id, users.name, applications.room_type, applications.status
            FROM applications
            JOIN users ON applications.user_id = users.id
            ORDER BY applications.applied_at DESC
        """)
        applications = c.fetchall()

        # Available rooms
        c.execute("""
            SELECT id, room_number, occupied, capacity
            FROM rooms
            WHERE occupied < capacity
            ORDER BY 
            CASE 
                WHEN room_number LIKE 'AG%' THEN 1
                WHEN room_number LIKE 'AB%' THEN 2
                WHEN room_number LIKE 'NAG%' THEN 3
                WHEN room_number LIKE 'NAB%' THEN 4
            END,
            CAST(SUBSTR(room_number, 3) AS INTEGER)
        """)
        rooms = c.fetchall()

        # Allocated students
        c.execute("""
            SELECT users.id, users.name, rooms.room_number, rooms.occupied, rooms.capacity
            FROM users
            JOIN rooms ON users.room_id = rooms.id
            WHERE users.role='student'
        """)
        allocated_students = c.fetchall()

        data.update({
            'total_seats': total_seats,
            'total_rooms': total_rooms,
            'seats_per_category': seats_per_category,
            'total_occupied': total_occupied,
            'available_seats': available_seats,
            'students': students,
            'rooms': rooms,
            'allocated_students': allocated_students,
            'applications': applications
        })

    # ================= ADMIN DASHBOARD =================
    elif role == 'admin':
        # Total students
        c.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        students = c.fetchone()[0]

        # Total unpaid fees
        c.execute("SELECT SUM(amount) FROM fees WHERE status='unpaid'")
        unpaid = c.fetchone()[0] or 0

        data.update({
            'students': students,
            'unpaid': unpaid
        })

    conn.close()

    return render_template('dashboard.html', **data)
@app.route('/deallocate/<int:user_id>')
def deallocate(user_id):
    if session.get('role') != 'warden':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Get current room
    c.execute("SELECT room_id FROM users WHERE id=?", (user_id,))
    room = c.fetchone()
    if room and room[0]:
        # Remove student room
        c.execute("UPDATE users SET room_id=NULL WHERE id=?", (user_id,))
        # Reduce occupancy
        c.execute("UPDATE rooms SET occupied=occupied-1 WHERE id=?", (room[0],))
        conn.commit()
    conn.close()
    flash("Student deallocated successfully!", "success")
    return redirect(url_for('dashboard'))
@app.route('/approve_application/<int:app_id>')
def approve_application(app_id):
    if session.get('role') != 'warden':
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    try:
        # Get the application info
        c.execute("SELECT room_type FROM applications WHERE id=?", (app_id,))
        row = c.fetchone()
        if not row:
            flash("Application not found!", "error")
            conn.close()
            return redirect(url_for('dashboard'))

        room_type = row[0]

        # Determine fee based on room type (AC = 8000, Non-AC = 5000)
        if 'AC' in room_type.upper():
            total_fee = 8000
        else:
            total_fee = 5000

        # Update application with approval and fee info
        c.execute("""
            UPDATE applications
            SET status='approved',
                total_fee=?,
                paid=0,
                remaining=?,
                due_date=date('now', '+30 days')
            WHERE id=?
        """, (total_fee, total_fee, app_id))

        conn.commit()
        conn.close()

        flash("Application approved! Fees initialized.", "success")
        return redirect(url_for('dashboard'))

    except sqlite3.OperationalError as e:
        conn.rollback()
        conn.close()
        flash(f"Database error: {str(e)}. Please check database schema.", "error")
        return redirect(url_for('dashboard'))
@app.route('/allocate_room', methods=['POST'])
def allocate_room():
    if session.get('role') != 'warden':
        flash('Access denied! Warden only.', 'error')
        return redirect(url_for('dashboard'))

    user_id = request.form.get('user_id')
    room_id = request.form.get('room_id')

    if not user_id or not room_id:
        flash('Student and Room must be selected!', 'error')
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    try:
        # Check if student already has a room
        c.execute("SELECT room_id FROM users WHERE id=?", (user_id,))
        existing_room = c.fetchone()

        if existing_room and existing_room[0]:
            flash('Student already has a room allocated!', 'warning')
            conn.close()
            return redirect(url_for('dashboard'))

        # Check if room is available
        c.execute("SELECT occupied, capacity FROM rooms WHERE id=?", (room_id,))
        room = c.fetchone()

        if not room:
            flash('Room not found!', 'error')
            conn.close()
            return redirect(url_for('dashboard'))

        if room[0] >= room[1]:
            flash('Room is already full!', 'error')
            conn.close()
            return redirect(url_for('dashboard'))

        # Allocate room to student (UPDATE users table)
        c.execute("UPDATE users SET room_id=? WHERE id=?", (room_id, user_id))

        # Update room occupancy
        c.execute("UPDATE rooms SET occupied=occupied+1 WHERE id=?", (room_id,))

        conn.commit()
        conn.close()

        flash('Room allocated successfully!', 'success')
        return redirect(url_for('dashboard'))

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    
@app.route('/reject_application/<int:app_id>')
def reject_application(app_id):

    if session.get('role') != 'warden':
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    UPDATE applications
    SET status='rejected'
    WHERE id=?
    """, (app_id,))

    conn.commit()
    conn.close()

    flash("Application rejected!", "success")

    return redirect(url_for('dashboard'))
@app.route('/pay_installment', methods=['POST'])
def pay_installment():
    if 'user_id' not in session:
        flash("Please login first!", "error")
        return redirect(url_for('login_page'))

    student_id = session['user_id']
    amount = int(request.form['amount'])

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get total_fee, paid, and remaining from applications table
    c.execute("SELECT total_fee, paid, remaining FROM applications WHERE user_id=?", (student_id,))
    row = c.fetchone()
    
    if not row:
        flash("No approved application found!", "error")
        conn.close()
        return redirect(url_for('dashboard'))

    # Unpack the values
    total_fee, paid, remaining = row
    
    # Update paid and remaining
    paid += amount
    remaining -= amount

    # Ensure remaining doesn't go below 0
    if remaining < 0:
        remaining = 0
        paid = total_fee

    c.execute("""
        UPDATE applications
        SET paid=?, remaining=?
        WHERE user_id=?
    """, (paid, remaining, student_id))

    conn.commit()
    conn.close()

    flash(f"₹{amount} paid successfully! Remaining: ₹{remaining}", "success")
    return redirect(url_for('dashboard'))
@app.route('/admin/payments')
def admin_payments():
    if session.get('role') != 'admin':
        flash("Access denied!", "error")
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
    SELECT student_id, name, room_type, total_fee, paid, remaining, due_date
    FROM applications
    WHERE status='approved'
    """)
    students = c.fetchall()
    conn.close()
    return render_template('admin_payments.html', students=students)

    return redirect(url_for('dashboard'))
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('home'))

# New /profile route for viewing/editing profile (including profile pic upload)
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page', next='profile'))
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        profile_pic = request.files.get('profile_pic')
        pic_path = None
        if profile_pic and profile_pic.filename:
            filename = secure_filename(profile_pic.filename)
            pic_path = os.path.join('static', 'images', f"{user_id}_{filename}")
            profile_pic.save(pic_path)
        # Update user data
        if name or email or pic_path:
            update_fields = []
            params = []
            if name:
                update_fields.append("name=?")
                params.append(name)
            if email:
                update_fields.append("email=?")
                params.append(email)
            if pic_path:
                update_fields.append("profile_pic=?")
                params.append(pic_path)
            params.append(user_id)
            c.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id=?", params)
            conn.commit()
            flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    # GET: Fetch current user data
    c.execute("SELECT name, email, profile_pic FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return render_template('profile.html', user=user)

# Other routes (unchanged)
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/service/<service_type>')
def service(service_type):
    services = {
        'laundry': {'name': 'Laundry Service', 'image': 'laundry.jpg', 'details': '24/7 laundry with washing and drying.', 'price': '$5 per load'},
        'wifi': {'name': 'WiFi Service', 'image': 'wifi.jpg', 'details': 'High-speed internet access.', 'price': '$10/month'},
        'cleaning': {'name': 'Cleaning Service', 'image': 'cleaning.jpg', 'details': 'Daily room cleaning.', 'price': '$20/week'}
    }
    service_info = services.get(service_type, {'name': 'Service Not Found', 'image': '', 'details': '', 'price': ''})
    return render_template('service_info.html', service=service_info)

@app.route('/room/<room_type>')
def room(room_type):
    rooms = {
        'ac-boys': {
            'name': 'AC Room - Boys',
            'image': 'ac-boys.jpeg',
            'details': 'We provide a comfortable AC room for boys with beds, study tables, storage space, and proper ventilation. Shared washroom, 24/7 water supply,free wifi service, and regular cleaning included.',
            'price': '₹8000/month'
        },
        'ac-girls': {
            'name': 'AC Room - Girls',
            'image': 'ac-girls.jpeg',
            'details': 'We provide a comfortable AC room for girls with beds, study tables, storage space, and proper ventilation. Shared washroom, 24/7 water supply, free wifi service,and regular cleaning included.',
            'price': '₹8000/month'
        },
        'nonac-boys': {
            'name': 'Non-AC Room - Boys',
            'image': 'nonac-boys.jpeg',
            'details': 'We provide a comfortable non-AC room for boys with two beds, study tables, shelves, mirrors, and a ceiling fan. Shared washroom, 24/7 water supply,free wifi service, and regular cleaning included.',
            'price': '₹5000/month'
        },
        'nonac-girls': {
            'name': 'Non-AC Room - Girls',
            'image': 'nonac-girls.jpeg',
            'details': 'We provide a comfortable non-AC room for girls with two beds, study tables, shelves, mirrors, and a ceiling fan. Shared washroom, 24/7 water supply,free wifi service, and regular cleaning included.',
            'price': '₹5000/month'
        }
    }
    room_info = rooms.get(room_type, {'name': 'Room Not Found', 'image': '', 'details': '', 'price': ''})
    return render_template('room_info.html', room=room_info, room_type=room_type)

@app.route('/apply/<room_type>', methods=['GET', 'POST'])
def apply_room(room_type):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    # Only students can apply
    if session.get('role') != 'student':
        flash('Only students can apply for rooms.', 'error')
        return redirect(url_for('dashboard'))

    # Check if already applied for this specific room type
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE user_id=? AND room_type=?", (session['user_id'], room_type))
    existing = c.fetchone()
    
    if request.method == 'POST':
        if existing:
            flash('You have already applied for this room type!', 'warning')
        else:
            c.execute("INSERT INTO applications (user_id, room_type) VALUES (?, ?)", (session['user_id'], room_type))
            conn.commit()
            flash('Your accommodation request has been submitted successfully. The hostel warden will review your application and allocate a room shortly.', 'success')
        conn.close()
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('apply_room.html', room_type=room_type)
@app.route('/available_rooms')
def available_rooms():
    # If not logged in, redirect to login
    if 'user_id' not in session:
        return redirect(url_for('login_page', next='available_rooms'))
    
    # Define room data to pass to the template
    rooms = [
        {'type': 'ac-boys', 'name': 'AC Room - Boys', 'price': '₹8000/month', 'img': 'ac-boys.jpeg'},
        {'type': 'ac-girls', 'name': 'AC Room - Girls', 'price': '₹8000/month', 'img': 'ac-girls.jpeg'},
        {'type': 'nonac-boys', 'name': 'Non-AC Room - Boys', 'price': '₹5000/month', 'img': 'nonac-boys.jpeg'},
        {'type': 'nonac-girls', 'name': 'Non-AC Room - Girls', 'price': '₹5000/month', 'img': 'nonac-girls.jpeg'}
    ]
    return render_template('available_rooms.html', rooms=rooms)

#checking with server side explore room working or not 
@app.route('/check_auth_rooms')
def check_auth_rooms():
    if 'user_id' in session:
        return redirect(url_for('available_rooms'))
    else:
        return redirect(url_for('login_page'))


@app.route('/contact')
def contact():
    if 'user_id' not in session:
        return redirect(url_for('login_page', next='contact'))
    return render_template('contact.html')

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    user_id = session['user_id']
    help_topic = request.form.get('help_topic')
    subject = request.form.get('subject')
    complaint_text = request.form.get('complaint')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO complaints (user_id, help_topic, subject, complaint)
        VALUES (?, ?, ?, ?)
    ''', (user_id, help_topic, subject, complaint_text))
    conn.commit()
    conn.close()

    flash('Complaint submitted successfully!', 'success')
    return redirect(url_for('contact'))

@app.route('/reply_complaint/<int:complaint_id>', methods=['POST'])
def reply_complaint(complaint_id):
    if session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    reply_text = request.form.get('reply')
    if not reply_text:
        flash('Reply cannot be empty!', 'error')
        return redirect(url_for('view_table', table_name='complaints'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        UPDATE complaints
        SET reply=?, replied_at=CURRENT_TIMESTAMP, status='replied'
        WHERE id=?
    """, (reply_text, complaint_id))
    conn.commit()
    conn.close()

    flash('Reply sent successfully!', 'success')
    return redirect(url_for('view_table', table_name='complaints'))
if __name__ == '__main__':
    app.run(debug=True)