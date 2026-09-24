from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "capstone-it-lab-secret-key"
DB = "lab_management.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'staff'
    );
    CREATE TABLE IF NOT EXISTS labs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        room TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available'
    );
    CREATE TABLE IF NOT EXISTS computers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lab_id INTEGER NOT NULL,
        asset_tag TEXT UNIQUE NOT NULL,
        computer_name TEXT NOT NULL,
        ip_address TEXT,
        specs TEXT,
        status TEXT NOT NULL DEFAULT 'Working',
        FOREIGN KEY(lab_id) REFERENCES labs(id)
    );
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        condition TEXT NOT NULL DEFAULT 'Good',
        location TEXT
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lab_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        purpose TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        FOREIGN KEY(lab_id) REFERENCES labs(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lab_id INTEGER,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'Medium',
        status TEXT NOT NULL DEFAULT 'Open',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(lab_id) REFERENCES labs(id)
    );
    CREATE TABLE IF NOT EXISTS maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        computer_id INTEGER,
        lab_id INTEGER,
        issue TEXT NOT NULL,
        technician TEXT,
        scheduled_date TEXT,
        status TEXT NOT NULL DEFAULT 'Scheduled',
        FOREIGN KEY(computer_id) REFERENCES computers(id),
        FOREIGN KEY(lab_id) REFERENCES labs(id)
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                     ("Administrator","admin@itlab.local","admin123","admin"))
        conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                     ("Lab Staff","staff@itlab.local","staff123","staff"))
    if conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0] == 0:
        labs = [
            ("Computer Lab 1","Room 101",30,"Available"),
            ("Computer Lab 2","Room 102",40,"Available"),
            ("Networking Lab","Room 201",25,"Available"),
            ("AI & Data Science Lab","Room 202",35,"Available")
        ]
        conn.executemany("INSERT INTO labs(name,room,capacity,status) VALUES(?,?,?,?)", labs)
    if conn.execute("SELECT COUNT(*) FROM computers").fetchone()[0] == 0:
        labs = conn.execute("SELECT id FROM labs").fetchall()
        n = 1
        for lab in labs:
            for i in range(1, 9):
                conn.execute("""INSERT INTO computers
                    (lab_id,asset_tag,computer_name,ip_address,specs,status)
                    VALUES(?,?,?,?,?,?)""",
                    (lab["id"],f"PC-{n:03}",f"LABPC-{n:03}",f"192.168.{lab['id']}.{i}",
                     "Core i5 / 8GB RAM / 512GB SSD","Working" if i != 8 else "Under Maintenance"))
                n += 1
    if conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
        equipment = [
            ("Projector","AV",4,"Good","Main Store"),
            ("Network Switch","Networking",8,"Good","Networking Lab"),
            ("Router","Networking",6,"Good","Networking Lab"),
            ("Keyboard","Computer Accessory",50,"Good","Main Store"),
            ("Mouse","Computer Accessory",50,"Good","Main Store"),
            ("UPS","Power",20,"Good","Main Store")
        ]
        conn.executemany("INSERT INTO equipment(name,category,quantity,condition,location) VALUES(?,?,?,?,?)", equipment)
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return redirect(url_for("dashboard")) if "user_id" in session else redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email,password)).fetchone()
        conn.close()
        if user:
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    stats = {
        "labs": conn.execute("SELECT COUNT(*) c FROM labs").fetchone()["c"],
        "computers": conn.execute("SELECT COUNT(*) c FROM computers").fetchone()["c"],
        "working": conn.execute("SELECT COUNT(*) c FROM computers WHERE status='Working'").fetchone()["c"],
        "complaints": conn.execute("SELECT COUNT(*) c FROM complaints WHERE status!='Resolved'").fetchone()["c"],
        "bookings": conn.execute("SELECT COUNT(*) c FROM bookings WHERE status='Approved'").fetchone()["c"]
    }
    recent = conn.execute("""SELECT c.*,u.name user_name,l.name lab_name
                            FROM complaints c JOIN users u ON u.id=c.user_id
                            LEFT JOIN labs l ON l.id=c.lab_id
                            ORDER BY c.id DESC LIMIT 5""").fetchall()
    conn.close()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/labs")
@login_required
def labs():
    conn=get_db()
    rows=conn.execute("""SELECT l.*, COUNT(c.id) computers,
                         SUM(CASE WHEN c.status='Working' THEN 1 ELSE 0 END) working
                         FROM labs l LEFT JOIN computers c ON c.lab_id=l.id
                         GROUP BY l.id ORDER BY l.id""").fetchall()
    conn.close()
    return render_template("labs.html", labs=rows)

@app.route("/computers")
@login_required
def computers():
    conn=get_db()
    rows=conn.execute("""SELECT c.*,l.name lab_name FROM computers c
                         JOIN labs l ON l.id=c.lab_id ORDER BY c.id""").fetchall()
    labs=conn.execute("SELECT * FROM labs ORDER BY name").fetchall()
    conn.close()
    return render_template("computers.html", computers=rows, labs=labs)

@app.route("/computers/add", methods=["POST"])
@admin_required
def add_computer():
    conn=get_db()
    try:
        conn.execute("""INSERT INTO computers(lab_id,asset_tag,computer_name,ip_address,specs,status)
                        VALUES(?,?,?,?,?,?)""",
                     (request.form["lab_id"],request.form["asset_tag"],request.form["computer_name"],
                      request.form["ip_address"],request.form["specs"],request.form["status"]))
        conn.commit()
        flash("Computer added.", "success")
    except sqlite3.IntegrityError:
        flash("Asset tag must be unique.", "danger")
    conn.close()
    return redirect(url_for("computers"))

@app.route("/computers/status/<int:cid>", methods=["POST"])
@admin_required
def computer_status(cid):
    conn=get_db()
    conn.execute("UPDATE computers SET status=? WHERE id=?", (request.form["status"],cid))
    conn.commit(); conn.close()
    return redirect(url_for("computers"))

@app.route("/equipment")
@login_required
def equipment():
    conn=get_db()
    rows=conn.execute("SELECT * FROM equipment ORDER BY name").fetchall()
    conn.close()
    return render_template("equipment.html", equipment=rows)

@app.route("/equipment/add", methods=["POST"])
@admin_required
def add_equipment():
    conn=get_db()
    conn.execute("""INSERT INTO equipment(name,category,quantity,condition,location)
                    VALUES(?,?,?,?,?)""",
                 (request.form["name"],request.form["category"],request.form["quantity"],
                  request.form["condition"],request.form["location"]))
    conn.commit(); conn.close()
    flash("Equipment added.", "success")
    return redirect(url_for("equipment"))

@app.route("/bookings", methods=["GET","POST"])
@login_required
def bookings():
    conn=get_db()
    if request.method=="POST":
        conn.execute("""INSERT INTO bookings(lab_id,user_id,date,start_time,end_time,purpose)
                        VALUES(?,?,?,?,?,?)""",
                     (request.form["lab_id"],session["user_id"],request.form["date"],
                      request.form["start_time"],request.form["end_time"],request.form["purpose"]))
        conn.commit()
        flash("Booking request submitted.", "success")
        return redirect(url_for("bookings"))
    rows=conn.execute("""SELECT b.*,l.name lab_name,u.name user_name
                         FROM bookings b JOIN labs l ON l.id=b.lab_id JOIN users u ON u.id=b.user_id
                         ORDER BY b.date DESC,b.start_time DESC""").fetchall()
    labs=conn.execute("SELECT * FROM labs ORDER BY name").fetchall()
    conn.close()
    return render_template("bookings.html", bookings=rows, labs=labs)

@app.route("/bookings/status/<int:bid>", methods=["POST"])
@admin_required
def booking_status(bid):
    conn=get_db()
    conn.execute("UPDATE bookings SET status=? WHERE id=?", (request.form["status"],bid))
    conn.commit(); conn.close()
    return redirect(url_for("bookings"))

@app.route("/complaints", methods=["GET","POST"])
@login_required
def complaints():
    conn=get_db()
    if request.method=="POST":
        conn.execute("""INSERT INTO complaints(user_id,lab_id,title,description,priority,status,created_at)
                        VALUES(?,?,?,?,?,'Open',?)""",
                     (session["user_id"],request.form["lab_id"],request.form["title"],
                      request.form["description"],request.form["priority"],
                      datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        flash("Complaint submitted.", "success")
        return redirect(url_for("complaints"))
    rows=conn.execute("""SELECT c.*,u.name user_name,l.name lab_name
                         FROM complaints c JOIN users u ON u.id=c.user_id
                         LEFT JOIN labs l ON l.id=c.lab_id ORDER BY c.id DESC""").fetchall()
    labs=conn.execute("SELECT * FROM labs ORDER BY name").fetchall()
    conn.close()
    return render_template("complaints.html", complaints=rows, labs=labs)

@app.route("/complaints/status/<int:cid>", methods=["POST"])
@admin_required
def complaint_status(cid):
    conn=get_db()
    conn.execute("UPDATE complaints SET status=? WHERE id=?", (request.form["status"],cid))
    conn.commit(); conn.close()
    return redirect(url_for("complaints"))

@app.route("/maintenance")
@login_required
def maintenance():
    conn=get_db()
    rows=conn.execute("""SELECT m.*,c.asset_tag,l.name lab_name
                         FROM maintenance m
                         LEFT JOIN computers c ON c.id=m.computer_id
                         LEFT JOIN labs l ON l.id=m.lab_id ORDER BY m.id DESC""").fetchall()
    computers=conn.execute("SELECT c.*,l.name lab_name FROM computers c JOIN labs l ON l.id=c.lab_id").fetchall()
    labs=conn.execute("SELECT * FROM labs").fetchall()
    conn.close()
    return render_template("maintenance.html", maintenance=rows, computers=computers, labs=labs)

@app.route("/maintenance/add", methods=["POST"])
@admin_required
def add_maintenance():
    conn=get_db()
    conn.execute("""INSERT INTO maintenance(computer_id,lab_id,issue,technician,scheduled_date,status)
                    VALUES(?,?,?,?,?,'Scheduled')""",
                 (request.form["computer_id"] or None, request.form["lab_id"] or None,
                  request.form["issue"],request.form["technician"],request.form["scheduled_date"]))
    conn.commit(); conn.close()
    flash("Maintenance task scheduled.", "success")
    return redirect(url_for("maintenance"))

@app.route("/maintenance/status/<int:mid>", methods=["POST"])
@admin_required
def maintenance_status(mid):
    conn=get_db()
    conn.execute("UPDATE maintenance SET status=? WHERE id=?", (request.form["status"],mid))
    conn.commit(); conn.close()
    return redirect(url_for("maintenance"))

@app.route("/users")
@admin_required
def users():
    conn=get_db()
    rows=conn.execute("SELECT id,name,email,role FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("users.html", users=rows)

@app.route("/users/add", methods=["POST"])
@admin_required
def add_user():
    conn=get_db()
    try:
        conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                     (request.form["name"],request.form["email"],request.form["password"],request.form["role"]))
        conn.commit(); flash("User created.", "success")
    except sqlite3.IntegrityError:
        flash("Email already exists.", "danger")
    conn.close()
    return redirect(url_for("users"))

@app.route("/api/stats")
@login_required
def api_stats():
    conn=get_db()
    data = {
        "working": conn.execute("SELECT COUNT(*) c FROM computers WHERE status='Working'").fetchone()["c"],
        "maintenance": conn.execute("SELECT COUNT(*) c FROM computers WHERE status='Under Maintenance'").fetchone()["c"],
        "faulty": conn.execute("SELECT COUNT(*) c FROM computers WHERE status='Faulty'").fetchone()["c"],
        "complaints": conn.execute("SELECT COUNT(*) c FROM complaints WHERE status!='Resolved'").fetchone()["c"]
    }
    conn.close()
    return jsonify(data)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
