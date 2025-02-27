from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer


app = Flask(__name__)
app.secret_key = "supersecretkey"

# File paths for data storage
USERS_FILE = "users.txt"
ATTENDANCE_FILE = "attendance.txt"
EVENTS_FILE = "events.txt"
TRANSACTIONS_FILE = "transactions.txt"
REGISTRATIONS_FILE = "registrations.txt"
PAYMENT_REQUESTS_FILE = "payment_requests.txt"

# Initialize necessary files
def initialize_files():
    """Ensure necessary .txt files exist."""
    for file in [USERS_FILE, ATTENDANCE_FILE, EVENTS_FILE, TRANSACTIONS_FILE, REGISTRATIONS_FILE, PAYMENT_REQUESTS_FILE]:
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
    today = datetime.today().strftime('%Y-%m-%d')
    
    # Read existing attendance data
    records = []
    with open(ATTENDANCE_FILE, "r") as f:
        for line in f:
            record_date, student_name, status, marked_by = line.strip().split(",")
            if record_date != today or student_name not in attendance_data:
                records.append(line.strip())

    # Add the new records for today
    with open(ATTENDANCE_FILE, "w") as f:
        for record in records:
            f.write(record + "\n")
        for student_name, status in attendance_data.items():
            f.write(f"{today},{student_name},{status},{session.get('user', 'unknown')}\n")

def get_attendance():
    records = {}
    with open(ATTENDANCE_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 4:  # Ensure correct format
                record_date, student_name, status, marked_by = parts
                if student_name not in records:
                    records[student_name] = []
                records[student_name].append({"date": record_date, "status": status})
            else:
                print(f"Skipping invalid record: {line.strip()}")  # Debugging print
    return records



# Event Management
def add_event(event_name, event_date, slots):
    events = get_events()
    for event in events:
        if event[0] == event_name and event[1] == event_date:
            return  # Prevent duplicate events
    with open(EVENTS_FILE, "a") as f:
        f.write(f"{event_name},{event_date},{slots}\n")

def get_events():
    events = []
    with open(EVENTS_FILE, "r") as f:
        for line in f:
            events.append(line.strip().split(","))
    return events

def delete_event(event_name):
    events = get_events()
    with open(EVENTS_FILE, "w") as f:
        for event in events:
            if event[0] != event_name:  # Keep all events except the one to delete
                f.write(",".join(event) + "\n")
    
    # Remove registrations for the deleted event
    registrations = []
    with open(REGISTRATIONS_FILE, "r") as f:
        for line in f:
            registered_user, registered_event, event_date = line.strip().split(",")
            if registered_event != event_name:  # Keep only events that are not deleted
                registrations.append(f"{registered_user},{registered_event},{event_date}")

    # Overwrite registrations file with updated data
    with open(REGISTRATIONS_FILE, "w") as f:
        for registration in registrations:
            f.write(registration + "\n")


def register_for_event(user, event_name):
    events = get_events()
    updated_events = []
    event_found = False
    event_date = None
    
    for event in events:
        if event[0] == event_name and int(event[2]) > 0:
            event[2] = str(int(event[2]) - 1)  # Decrease available slots by 1
            event_found = True
            event_date = event[1]  # Capture event date
        updated_events.append(event)
    
    if event_found:
        with open(EVENTS_FILE, "w") as f:
            for event in updated_events:
                f.write(",".join(event) + "\n")
        if not is_user_registered(user, event_name):
            with open(REGISTRATIONS_FILE, "a") as f:
                f.write(f"{user},{event_name},{event_date}\n")

def is_user_registered(user, event_name):
    with open(REGISTRATIONS_FILE, "r") as f:
        for line in f:
            registered_user, registered_event, _ = line.strip().split(",")
            if registered_user == user and registered_event == event_name:
                return True
    return False

def get_user_registrations(user):
    user_events = []
    with open(REGISTRATIONS_FILE, "r") as f:
        for line in f:
            registered_user, event_name, event_date = line.strip().split(",")
            if registered_user == user:
                user_events.append((event_name, event_date))
    return user_events

#------------------ Financial Transactions Management------------------------------------------
def request_payment(amount, description):
    members = get_members()
    with open(PAYMENT_REQUESTS_FILE, "a") as f:
        for member in members:
            f.write(f"{member},{amount},{description},Pending\n")

def get_payment_requests():
    payments = []
    with open(PAYMENT_REQUESTS_FILE, "r") as f:
        for line in f:
            payments.append(line.strip().split(","))
    return payments

def mark_payment_as_paid(user, description):
    payments = get_payment_requests()
    updated_payments = []
    for payment in payments:
        if payment[0] == user and payment[2] == description:
            payment[3] = "Paid"
            record_transaction(f"Payment from {user}", payment[1])  # Record in transactions
        updated_payments.append(payment)
    with open(PAYMENT_REQUESTS_FILE, "w") as f:
        for payment in updated_payments:
            f.write(",".join(payment) + "\n")

def record_expense(expense_name, amount):
    with open(TRANSACTIONS_FILE, "a") as f:
        f.write(f"{expense_name},{amount},Expense\n")

def record_transaction(transaction_name, amount):
    with open(TRANSACTIONS_FILE, "a") as f:
        f.write(f"{transaction_name},{amount},Income\n")

def get_transactions():
    transactions = []
    with open(TRANSACTIONS_FILE, "r") as f:
        for line in f:
            transactions.append(line.strip().split(","))
    return transactions

def get_member_payments(user):
    payments = get_payment_requests()
    return [payment for payment in payments if payment[0] == user]

def generate_financial_report():
    transactions = get_transactions()
    pdf_file = "Financial Report.pdf"
    doc = SimpleDocTemplate(pdf_file, pagesize=letter)
    elements = []
    
    # Title
    title = [["Financial Transactions Report"]]
    title_table = Table(title)
    title_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12)
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 12))
    
    # Table Header
    data = [["Transaction", "Amount", "Type"]]
    total_income = 0
    total_expense = 0
    styles = []
    for index, transaction in enumerate(transactions, start=1):
        data.append(transaction)
        if transaction[2] == "Income":
            total_income += float(transaction[1])
            styles.append(('BACKGROUND', (2, index), (2, index), colors.lightgreen))
        elif transaction[2] == "Expense":
            total_expense += float(transaction[1])
            styles.append(('BACKGROUND', (2, index), (2, index), colors.pink))
    
    net_income = total_income - total_expense
    
    table = Table(data, colWidths=[200, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ] + styles))
    elements.append(table)
    elements.append(Spacer(1, 12))
    
    # Net Income Section
    net_income_data = [["Total Income:", f"${total_income}"],
                       ["Total Expense:", f"${total_expense}"],
                       ["Net Income:", f"${net_income}"]]
    net_income_table = Table(net_income_data, colWidths=[200, 100])
    net_income_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(net_income_table)
    
    doc.build(elements)
    return pdf_file

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
            return render_template("register.html", error="Username already exists. Try a different one.")
        
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
        return render_template("login.html", error="Invalid credentials. Please try again.")
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

@app.route("/delete_event/<event_name>")
def delete_event_route(event_name):
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    delete_event(event_name)
    return redirect(url_for("events"))

@app.route("/finances", methods=["GET", "POST"])
def finances():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        if "expense_name" in request.form:
            expense_name = request.form["expense_name"]
            amount = request.form["amount"]
            record_expense(expense_name, amount)
        elif "fee_amount" in request.form:
            amount = request.form["fee_amount"]
            description = request.form["description"]
            request_payment(amount, description)
    transactions = get_transactions()
    payments = get_payment_requests()
    return render_template("finances.html", transactions=transactions, payments=payments)

@app.route("/download_financial_report")
def download_financial_report():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    pdf_file = generate_financial_report()
    return send_file(pdf_file, as_attachment=True)


@app.route("/view_attendance")
def view_attendance():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    
    user = session["user"]
    records = get_attendance()
    
    # Only show the logged-in member's attendance
    member_attendance = {user: records.get(user, "Not Marked")}

    return render_template("view_attendance.html", records=member_attendance)


@app.route("/view_events", methods=["GET", "POST"])
def view_events():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    if request.method == "POST":
        event_name = request.form["event_name"]
        register_for_event(session["user"], event_name)
    events_list = get_events()
    registered_events = get_user_registrations(session["user"])
    return render_template("view_events.html", events=events_list, registered_events=registered_events)


@app.route("/view_finances", methods=["GET", "POST"])
def view_finances():
    if "user" not in session or session["role"] != "member":
        return redirect(url_for("login"))
    if request.method == "POST":
        description = request.form["description"]
        mark_payment_as_paid(session["user"], description)
    transactions = get_transactions()
    member_payments = get_member_payments(session["user"])
    return render_template("view_finances.html", transactions=transactions, member_payments=member_payments)



if __name__ == "__main__":
    initialize_files()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
