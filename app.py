from flask import Flask, render_template, request, redirect, url_for, session
import os
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# File paths for data storage
USERS_FILE = "users.txt"
ATTENDANCE_FILE = "attendance.txt"
EVENTS_FILE = "events.txt"
TRANSACTIONS_FILE = "transactions.txt"

# Initialize necessary files
def initialize_files():
    """Ensure necessary .txt files exist."""
    for file in [USERS_FILE, ATTENDANCE_FILE, EVENTS_FILE, TRANSACTIONS_FILE]:
        if not os.path.exists(file):
            with open(file, "w") as f:
                pass
    
    # Ensure default admin exists
    if os.stat(USERS_FILE).st_size == 0:
        with open(USERS_FILE, "w") as f:
            admin_pass = generate_password_hash("adminpass", method="pbkdf2:sha256") if hasattr(hashlib, 'pbkdf2_hmac') else hashlib.sha256("adminpass".encode()).hexdigest()
            f.write(f"admin,{admin_pass},admin\n")

# User Management
def get_users():
    users = {}
    with open(USERS_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 3:
                username, password, role = parts
                users[username] = {"password": password, "role": role}
    return users

def get_members():
    members = []
    users = get_users()
    for username, details in users.items():
        if details["role"] == "member":
            members.append(username)
    print("list:", members)
    return members

def add_user(username, password, role):
    password_hash = generate_password_hash(password, method="pbkdf2:sha256") if hasattr(hashlib, 'pbkdf2_hmac') else hashlib.sha256(password.encode()).hexdigest()
    with open(USERS_FILE, "a") as f:
        f.write(f"{username},{password_hash},{role}\n")

# Attendance Management
def record_attendance(attendance_data):
    with open(ATTENDANCE_FILE, "a") as f:
        for student_name, status in attendance_data.items():
            f.write(f"{student_name},{status},{session.get('user', 'unknown')}\n")

def get_attendance():
    records = {}
    with open(ATTENDANCE_FILE, "r") as f:
        for line in f:
            student_name, status, marked_by = line.strip().split(",")
            records[student_name] = status
    return records

# Event Management
def add_event(event_name, event_date, slots):
    with open(EVENTS_FILE, "a") as f:
        f.write(f"{event_name},{event_date},{slots}\n")

def get_events():
    events = []
    with open(EVENTS_FILE, "r") as f:
        for line in f:
            events.append(line.strip().split(","))
    return events

# Financial Transactions Management
def record_transaction(transaction_name, amount, transaction_type):
    with open(TRANSACTIONS_FILE, "a") as f:
        f.write(f"{transaction_name},{amount},{transaction_type}\n")

def get_transactions():
    transactions = []
    with open(TRANSACTIONS_FILE, "r") as f:
        for line in f:
            transactions.append(line.strip().split(","))
    return transactions

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        users = get_users()
        
        if username in users:
            return "Username already exists."
        
        add_user(username, password, role)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = get_users()
        
        if username in users and check_password_hash(users[username]["password"], password):
            session["user"] = username
            session["role"] = users[username]["role"]
            return redirect(url_for("dashboard"))
        return "Invalid credentials."
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    print(f"User: {session['user']}, Role: {session.get('role')}")

    if session["role"] == "admin":
        return render_template("admin_dashboard.html", user=session["user"])
    return render_template("member_dashboard.html", user=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        attendance_data = {student: request.form[student] for student in request.form}
        record_attendance(attendance_data)
    members = get_members()
    attendance_records = get_attendance()
    return render_template("attendance.html", members=members, attendance_records=attendance_records)

@app.route("/events", methods=["GET", "POST"])
def events():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        event_name = request.form["event_name"]
        event_date = request.form["event_date"]
        slots = request.form["slots"]
        add_event(event_name, event_date, slots)
    events_list = get_events()
    return render_template("events.html", events=events_list)

@app.route("/finances", methods=["GET", "POST"])
def finances():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        transaction_name = request.form["transaction_name"]
        amount = request.form["amount"]
        transaction_type = request.form["transaction_type"]
        record_transaction(transaction_name, amount, transaction_type)
    transactions = get_transactions()
    return render_template("finances.html", transactions=transactions)

@app.route("/view_attendance")
def view_attendance():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    records = get_attendance()  # Fetch all attendance records
    return render_template("view_attendance.html", records=records)

@app.route("/view_events")
def view_events():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    events_list = get_events()  # Fetch all event records
    return render_template("view_events.html", events=events_list)

@app.route("/view_finances")
def view_finances():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    transactions = get_transactions()  # Fetch all transactions
    return render_template("view_finances.html", transactions=transactions)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
