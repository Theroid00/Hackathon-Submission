from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime
from ledger import generate_transaction_hash
import random
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For session management

# Directory for file uploads
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect('loan_system.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize SQLite DB (tables and default admin)
def init_db():
    conn = sqlite3.connect('loan_system.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        aadhaar_id TEXT,
        age INTEGER,
        gender TEXT,
        trust_score INTEGER DEFAULT 50
    )''')

    # Loans table
    cursor.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        loan_duration TEXT,
        loan_purpose TEXT,
        referrer_phone TEXT,
        community TEXT,
        previous_loans INTEGER,
        monthly_income INTEGER,
        income_source TEXT,
        status TEXT,
        txn_hash TEXT
    )''')

    # Ledger table (Blockchain simulation)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        txn_type TEXT,
        user_id INTEGER,
        amount INTEGER,
        txn_hash TEXT,
        prev_hash TEXT
    )''')

    # Admins table
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    # Insert default admin if not exists
    cursor.execute("SELECT * FROM admins")
    if not cursor.fetchall():
        cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ("admin", "password"))

    conn.commit()
    conn.close()

# Call init_db() to initialize tables
init_db()

# Home Page - List Loans
@app.route('/')
def home():
    conn = get_db_connection()
    loans = conn.execute('SELECT * FROM loans').fetchall()
    conn.close()
    return render_template('index.html', loans=loans)

# Loan Request Submission
@app.route('/request_loan', methods=['GET', 'POST'])
def request_loan():
    if request.method == 'POST':
        # Get the form data
        name = request.form['name']
        phone = request.form['phone']
        aadhaar_id = request.form['aadhaar_id']
        age = request.form['age']
        gender = request.form['gender']
        amount = request.form['amount']
        loan_purpose = request.form['loan_purpose']
        loan_duration = request.form['loan_duration']
        referrer_phone = request.form.get('referrer_phone', '')
        community = request.form.get('community', '')
        previous_loans = request.form.get('previous_loans', 0)
        monthly_income = request.form['monthly_income']
        income_source = request.form['income_source']

        # Generate a transaction hash
        transaction_data = f"Loan Request: Name {name}, Amount {amount}"
        txn_hash = generate_transaction_hash(transaction_data)
        timestamp = datetime.now().isoformat()

        conn = get_db_connection()

        # Get previous hash
        cursor = conn.cursor()
        cursor.execute("SELECT txn_hash FROM ledger ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        prev_hash = result[0] if result else "0"

        # Insert into users table
        cursor.execute('''INSERT INTO users (name, phone, aadhaar_id, age, gender) 
                          VALUES (?, ?, ?, ?, ?)''', (name, phone, aadhaar_id, age, gender))

        # Get user_id of the newly inserted user
        user_id = cursor.lastrowid

        # Insert into loans table (no OTP)
        cursor.execute('''INSERT INTO loans (user_id, amount, loan_duration, loan_purpose, referrer_phone, community,
                                              previous_loans, monthly_income, income_source, status, txn_hash)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (user_id, amount, loan_duration, loan_purpose, referrer_phone, community, previous_loans, 
                        monthly_income, income_source, "Pending", txn_hash))

        # Insert into ledger table
        cursor.execute("INSERT INTO ledger (timestamp, txn_type, user_id, amount, txn_hash, prev_hash) VALUES (?, ?, ?, ?, ?, ?)",
                       (timestamp, "loan_request", user_id, amount, txn_hash, prev_hash))

        conn.commit()
        conn.close()

        return redirect(url_for('home'))

    return render_template('loan.html')

# Route to display the ledger
@app.route('/ledger')
def ledger():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    conn = get_db_connection()
    ledger_entries = conn.execute('SELECT * FROM ledger ORDER BY id DESC').fetchall()
    conn.close()

    return render_template('ledger.html', ledger_entries=ledger_entries)

# Admin Login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('loan_system.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['admin_logged_in'] = True
            return redirect('/admin_dashboard')
        else:
            return "Invalid credentials"

    return render_template('admin_login.html')

@app.route('/transaction_history')
def transaction_history():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    conn = get_db_connection()
    
    # Fetch all transactions from the ledger
    all_transactions = conn.execute('SELECT * FROM ledger ORDER BY id DESC').fetchall()
    
    # Fetch approved transactions
    approved_transactions = conn.execute("SELECT * FROM ledger WHERE txn_type='loan_approval' ORDER BY id DESC").fetchall()
    
    # Fetch denied transactions
    denied_transactions = conn.execute("SELECT * FROM ledger WHERE txn_type='loan_denial' ORDER BY id DESC").fetchall()
    
    # Calculate stats
    total_transactions = len(all_transactions)
    total_amount = sum(txn['amount'] for txn in all_transactions)
    pending_requests = conn.execute("SELECT COUNT(*) FROM loans WHERE status='Pending'").fetchone()[0]
    approval_rate = (len(approved_transactions) / total_transactions * 100) if total_transactions > 0 else 0
    
    stats = {
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'pending_requests': pending_requests,
        'approval_rate': round(approval_rate, 2)
    }
    
    conn.close()
    
    return render_template('transaction_history.html', 
                          all_transactions=all_transactions, 
                          approved_transactions=approved_transactions, 
                          denied_transactions=denied_transactions, 
                          stats=stats)



# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    conn = sqlite3.connect('loan_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loans WHERE status='Pending'")
    loans = cursor.fetchall()
    conn.close()

    return render_template('admin_dashboard.html', loans=loans)

# Approve Loan
@app.route('/approve_loan/<int:loan_id>')
def approve_loan(loan_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    conn = sqlite3.connect('loan_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET status='Approved' WHERE id=?", (loan_id,))
    conn.commit()
    conn.close()

    return redirect('/admin_dashboard')

# Deny Loan
@app.route('/deny_loan/<int:loan_id>')
def deny_loan(loan_id):  # Renamed this function to deny_loan
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    conn = sqlite3.connect('loan_system.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET status='Denied' WHERE id=?", (loan_id,))
    conn.commit()
    conn.close()

    return redirect('/admin_dashboard')

# Logout Admin
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin_login')

if __name__ == '__main__':
    app.run(debug=True)
