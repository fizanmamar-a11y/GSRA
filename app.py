from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for session management

DB_NAME = "gsra.db"
import os
from werkzeug.utils import secure_filename

# Uploads folder path
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "mp4"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Helper function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------- DATABASE INITIALIZATION ---------------- #

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    # Groups table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT
    );
    """)

    # Notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Forums table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    """)

    # Forum posts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forum_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forum_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (forum_id) REFERENCES forums(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        chapters_completed INTEGER,
        hours_studied INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Reading list table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reading_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        author TEXT,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Collaboration table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS collaboration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Activity log table (NEW)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    conn.commit()
    conn.close()

# ---------------- AUTH ROUTES ---------------- #

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_pw = generate_password_hash(password)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_pw))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already exists. Try logging in."
    return render_template("signup.html", title="Sign Up")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user"] = user[1]
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials. Please try again."
    return render_template("login.html", title="Login")

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        # TODO: Send reset email
        return "Password reset link sent!"
    return render_template("forgot.html", title="Forgot Password")

# ---------------- DASHBOARD ROUTES ---------------- #

@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM groups")
    groups_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (session["user_id"],))
    notifications_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM progress WHERE user_id = ?", (session["user_id"],))
    progress_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reading_list WHERE user_id = ?", (session["user_id"],))
    reading_count = cursor.fetchone()[0]

    # Fetch recent activity (NEW)
    cursor.execute("""
    SELECT users.name, activity_log.action, activity_log.timestamp
    FROM activity_log
    JOIN users ON users.id = activity_log.user_id
    ORDER BY timestamp DESC LIMIT 5
    """)
    activity_feed = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        title=f"Welcome to GSRA, {session['user']}",
        user_name=session["user"],   # for welcome banner
        groups_count=groups_count,
        notifications_count=notifications_count,
        progress_count=progress_count,
        reading_count=reading_count,
        activity_feed=activity_feed   # pass feed to template
    )

# ---------------- PROFILE ---------------- #

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_pw = generate_password_hash(password)

        cursor.execute("UPDATE users SET name=?, email=?, password=? WHERE id=?", 
                       (name, email, hashed_pw, session["user_id"]))
        conn.commit()
        session["user"] = name
        conn.close()
        return redirect(url_for("dashboard"))

    cursor.execute("SELECT name, email FROM users WHERE id=?", (session["user_id"],))
    user_data = cursor.fetchone()
    conn.close()

    return render_template("profile.html", title="Profile", user=user_data)

# ---------------- NOTIFICATIONS ---------------- #

@app.route("/notifications")
def notifications():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM notifications WHERE user_id=?", (session["user_id"],))
    messages = cursor.fetchall()
    conn.close()

    return render_template("notifications.html", title="Notifications", messages=messages)

# ---------------- GROUPS ---------------- #

@app.route("/groups", methods=["GET", "POST"])
def groups():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Handle group creation
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        cursor.execute(
            "INSERT INTO groups (name, description, creator_id) VALUES (?, ?, ?)", 
            (name, description, session["user_id"])
        )
        conn.commit()

        # Log activity
        cursor.execute(
            "INSERT INTO activity_log (user_id, action) VALUES (?, ?)",
            (session["user_id"], f"created a new group: {name}")
        )
        conn.commit()

    cursor.execute("SELECT id, name, description, creator_id FROM groups")
    all_groups = cursor.fetchall()
    conn.close()

    return render_template("groups.html", title="Study Groups", groups=all_groups)


@app.route("/group/<int:group_id>")
def group_detail(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Fetch group info
    cursor.execute("SELECT id, name, description, creator_id FROM groups WHERE id=?", (group_id,))
    group = cursor.fetchone()

    # Fetch group members
    cursor.execute("""
        SELECT users.name 
        FROM group_members 
        JOIN users ON users.id = group_members.user_id 
        WHERE group_members.group_id=?
    """, (group_id,))
    members = cursor.fetchall()

    # Fetch shared files (include file id + uploader id for deletion checks)
    cursor.execute("""
        SELECT group_files.id, users.name, group_files.filename, group_files.timestamp, group_files.user_id
        FROM group_files
        JOIN users ON users.id = group_files.user_id
        WHERE group_files.group_id=?
        ORDER BY group_files.timestamp DESC
    """, (group_id,))
    files = cursor.fetchall()

    # Fetch recent activity (last 10 actions for this group)
    cursor.execute("""
        SELECT users.name, activity_log.action, activity_log.timestamp
        FROM activity_log
        JOIN users ON users.id = activity_log.user_id
        WHERE activity_log.action LIKE ?
        ORDER BY activity_log.timestamp DESC
        LIMIT 10
    """, (f"%group {group_id}%",))
    activities = cursor.fetchall()

    conn.close()

    return render_template("group_detail.html", group=group, members=members, files=files, activities=activities)


@app.route("/groups/join/<int:group_id>")
def join_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", 
        (group_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    # Log activity
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_log (user_id, action) VALUES (?, ?)",
        (session["user_id"], f"joined group {group_id}")
    )
    conn.commit()
    conn.close()

    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/groups/<int:group_id>/upload", methods=["POST"])
def upload_file(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if "file" not in request.files:
        return "No file part"
    file = request.files["file"]
    if not file.filename or file.filename == "":
        return "No selected file"

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Save metadata in DB
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO group_files (group_id, user_id, filename, filepath)
            VALUES (?, ?, ?, ?)
        """, (group_id, session["user_id"], filename, filepath))
        conn.commit()
        conn.close()

        # Log activity
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_log (user_id, action) VALUES (?, ?)",
            (session["user_id"], f"uploaded {filename} to group {group_id}")
        )
        conn.commit()
        conn.close()

        return redirect(url_for("group_detail", group_id=group_id))
    else:
        return "File type not allowed"


@app.route("/groups/delete/<int:group_id>", methods=["POST"])
def delete_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Check if current user is the creator
    cursor.execute("SELECT creator_id FROM groups WHERE id=?", (group_id,))
    result = cursor.fetchone()
    if not result or result[0] != session["user_id"]:
        conn.close()
        return "Unauthorized: Only the group creator can delete this group."

    # Delete related records first
    cursor.execute("DELETE FROM group_members WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM group_files WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.commit()
    conn.close()

    # Log activity
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_log (user_id, action) VALUES (?, ?)",
        (session["user_id"], f"deleted group {group_id}")
    )
    conn.commit()
    conn.close()

    return redirect(url_for("groups"))


@app.route("/groups/<int:group_id>/delete-file/<int:file_id>", methods=["POST"])
def delete_file(group_id, file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Get file info
    cursor.execute("SELECT user_id, filename FROM group_files WHERE id=?", (file_id,))
    file = cursor.fetchone()

    # Get group creator
    cursor.execute("SELECT creator_id FROM groups WHERE id=?", (group_id,))
    group = cursor.fetchone()

    if not file or not group:
        conn.close()
        return "File or group not found."

    uploader_id, filename = file
    creator_id = group[0]

    # Permission check: only uploader or group creator can delete
    if session["user_id"] != uploader_id and session["user_id"] != creator_id:
        conn.close()
        return "Unauthorized: Only uploader or group creator can delete this file."

    # Delete file record
    cursor.execute("DELETE FROM group_files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

    # Remove file from disk
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Log activity
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_log (user_id, action) VALUES (?, ?)",
        (session["user_id"], f"deleted file {filename} from group {group_id}")
    )
    conn.commit()
    conn.close()

    return redirect(url_for("group_detail", group_id=group_id))


# ---------------- FORUMS ---------------- #

@app.route("/forums", methods=["GET", "POST"])
def forums():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        cursor.execute("INSERT INTO forums (title, created_by) VALUES (?, ?)", (title, session["user_id"]))
        conn.commit()

        # Log activity
        cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (?, ?)", 
                       (session["user_id"], f"created a new forum: {title}"))
        conn.commit()

    cursor.execute("SELECT id, title FROM forums")
    all_forums = cursor.fetchall()
    conn.close()

    return render_template("forums.html", title="Discussion Forums", forums=all_forums)

@app.route("/forum/<int:forum_id>", methods=["GET", "POST"])
def forum_detail(forum_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        content = request.form["content"]
        cursor.execute("INSERT INTO forum_posts (forum_id, user_id, content) VALUES (?, ?, ?)", 
                       (forum_id, session["user_id"], content))
        conn.commit()

        # Log activity
        cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (?, ?)", 
                       (session["user_id"], f"posted in forum {forum_id}"))
        conn.commit()

    cursor.execute("SELECT content, timestamp FROM forum_posts WHERE forum_id=?", (forum_id,))
    posts = cursor.fetchall()
    conn.close()

    return render_template("forum_detail.html", title="Forum Thread", posts=posts)

# ---------------- PROGRESS ---------------- #

@app.route("/progress", methods=["GET", "POST"])
def progress():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        subject = request.form["subject"]
        chapters = int(request.form["chapters"])
        hours = int(request.form["hours"])
        cursor.execute(
            "INSERT INTO progress (user_id, subject, chapters_completed, hours_studied) VALUES (?, ?, ?, ?)",
            (session["user_id"], subject, chapters, hours)
        )
        conn.commit()

        # Log activity
        cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (?, ?)", 
                       (session["user_id"], f"updated progress in {subject}"))
        conn.commit()

    cursor.execute("SELECT subject, chapters_completed, hours_studied FROM progress WHERE user_id=?", (session["user_id"],))
    records = cursor.fetchall()
    conn.close()

    return render_template("progress.html", title="Progress Tracking", records=records)

# ---------------- READING LIST ---------------- #

@app.route("/reading-list", methods=["GET", "POST"])
def reading_list():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        cursor.execute(
            "INSERT INTO reading_list (user_id, title, author) VALUES (?, ?, ?)",
            (session["user_id"], title, author)
        )
        conn.commit()

        # Log activity
        cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (?, ?)", 
                       (session["user_id"], f"added '{title}' to reading list"))
        conn.commit()

    cursor.execute("SELECT title, author, status FROM reading_list WHERE user_id=?", (session["user_id"],))
    resources = cursor.fetchall()
    conn.close()

    return render_template("reading_list.html", title="Reading List", resources=resources)

# ---------------- COLLABORATION ---------------- #

@app.route("/collaboration", methods=["GET", "POST"])
def collaboration():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        note = request.form["note"]
        cursor.execute(
            "INSERT INTO collaboration (user_id, content) VALUES (?, ?)",
            (session["user_id"], note)
        )
        conn.commit()

        # Log activity
        cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (?, ?)", 
                       (session["user_id"], "added a new collaboration note"))
        conn.commit()

    cursor.execute("SELECT content, timestamp FROM collaboration WHERE user_id=?", (session["user_id"],))
    notes = cursor.fetchall()
    conn.close()

    return render_template("collaboration.html", title="Collaboration Workspace", notes=notes)

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    init_db()   # Ensure all tables exist before running
    app.run(debug=True)
