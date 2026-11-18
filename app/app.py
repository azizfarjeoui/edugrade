import os, sys, time, logging, psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EduGrade")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "edugrade")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

# VULNERABILITY 4: Fake hardcoded fallback secret key
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-hardcoded-secret-key-edugrade-2026")

app = Flask(__name__)
app.secret_key = SECRET_KEY

BASE_STYLE = "<style>body{font-family:Arial,sans-serif;margin:30px;background:#f7f9fa}.card{background:#fff;padding:20px;border-radius:8px;max-width:700px;margin:auto}table{width:100%;border-collapse:collapse;margin-top:15px}th,td{border:1px solid #ddd;padding:8px}input{width:100%;padding:8px;margin:8px 0;box-sizing:border-box}button{background:#0066cc;color:#fff;padding:8px 16px;border:none;border-radius:4px;cursor:pointer}.alert{color:red}</style>"
LOGIN_HTML = BASE_STYLE + """<div class="card"><h2>EduGrade - Login</h2>{% if error %}<div class="alert">{{ error }}</div>{% endif %}
<form method="POST"><label>Username</label><input type="text" name="username" required><label>Password</label><input type="password" name="password" required><button type="submit">Sign In</button></form></div>"""
SEARCH_HTML = BASE_STYLE + """<div class="card"><p><b>EduGrade</b> | User: <b>{{ session.get('username') }}</b> ({{ session.get('role') }}) | <a href="/logout">Logout</a></p>
<h3>Search Student Grades</h3><form method="GET"><input type="text" name="q" value="{{ q_val }}" placeholder="Subject (e.g. Math, DevSecOps)"><button type="submit">Search</button></form>
{% if searched %}<!-- VULNERABILITY 3: Reflected XSS (q printed unescaped) --><h4>Search results for: {{ q_raw|safe }}</h4>
<table><tr><th>ID</th><th>Student</th><th>Subject</th><th>Grade</th><th>Comment</th><th>Action</th></tr>
{% for g in grades %}<tr><td>{{ g.id }}</td><td>{{ g.username }}</td><td>{{ g.subject }}</td><td>{{ g.grade }}</td><td>{{ g.comment }}</td><td><a href="/grades/{{ g.id }}">View</a></td></tr>{% endfor %}</table>{% endif %}</div>"""
GRADE_HTML = BASE_STYLE + """<div class="card"><p><a href="/search">&larr; Back to Search</a> | <a href="/logout">Logout</a></p>
<h3>Grade Record #{{ grade.id }}</h3><p><b>Student:</b> {{ grade.username }}</p><p><b>Subject:</b> {{ grade.subject }}</p><p><b>Grade:</b> {{ grade.grade }} / 20</p><p><b>Comment:</b> {{ grade.comment }}</p></div>"""

def get_db():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, cursor_factory=RealDictCursor)

def init_db():
    retries = 15
    while retries > 0:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL);
                CREATE TABLE IF NOT EXISTS grades (id SERIAL PRIMARY KEY, student_id INTEGER REFERENCES users(id), subject VARCHAR(50) NOT NULL, grade NUMERIC(4, 2) NOT NULL, comment TEXT);
            """)
            cur.execute("SELECT COUNT(*) AS count FROM users;")
            if cur.fetchone()["count"] == 0:
                t_pw, s_pw = generate_password_hash("teacher123"), generate_password_hash("student123")
                cur.execute("INSERT INTO users (username, password_hash, role) VALUES ('prof_smith', %s, 'teacher'), ('alice', %s, 'student'), ('bob', %s, 'student'), ('charlie', %s, 'student');", (t_pw, s_pw, s_pw, s_pw))
                cur.execute("""
                    INSERT INTO grades (student_id, subject, grade, comment) VALUES
                    (2, 'Math', 18.5, 'Excellent performance and rigor'), (2, 'DevSecOps', 16.0, 'Good pipeline design'),
                    (3, 'Math', 11.0, 'Needs to revise basics'), (3, 'DevSecOps', 14.5, 'Solid practical work'),
                    (4, 'Math', 9.0, 'Insufficient effort this semester'), (4, 'DevSecOps', 17.0, 'Outstanding CTF challenge solver');
                """)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Database initialized and fictive data seeded successfully.")
            return
        except psycopg2.OperationalError as e:
            retries -= 1
            logger.warning(f"Database connection failed: {e}. Retrying ({retries} left)...")
            time.sleep(2)
    logger.error("Database connection failed after maximum retries.")

@app.route("/")
def index():
    return redirect(url_for("search")) if "user_id" in session else redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    ip, error = request.remote_addr or "127.0.0.1", None
    if request.method == "POST":
        username, password = request.form.get("username", "").strip(), request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"], session["username"], session["role"] = user["id"], user["username"], user["role"]
            logger.info(f"Login success: user={username} role={user['role']} ip={ip}")
            return redirect(url_for("search"))
        else:
            logger.warning(f"SECURITY_ALERT type=failed_login ip={ip} username={username}")
            error = "Invalid username or password"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    logger.info(f"User logged out: user={session.get('username', 'anonymous')} ip={request.remote_addr or '127.0.0.1'}")
    session.clear()
    return redirect(url_for("login"))

@app.route("/search")
def search():
    if "user_id" not in session:
        return redirect(url_for("login"))
    q, ip = request.args.get("q", ""), request.remote_addr or "127.0.0.1"
    if any(pat in q.upper() for pat in ["'", "--", "UNION"]):
        logger.warning(f"SECURITY_ALERT type=sqli_attempt ip={ip}")
    grades = []
    if q:
        logger.info(f"Search query executed: q_len={len(q)} user={session.get('username')} ip={ip}")
        conn = get_db()
        cur = conn.cursor()
        # VULNERABILITY 1: SQL Injection via string concatenation
        query = f"SELECT g.id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.subject ILIKE '%{q}%'"
        cur.execute(query)
        grades = cur.fetchall()
        cur.close()
        conn.close()
    # VULNERABILITY 3: Reflected XSS passed via q_raw
    return render_template_string(SEARCH_HTML, q_raw=q, q_val=q, searched=bool(q), grades=grades)

@app.route("/grades/<int:grade_id>")
def grade_detail(grade_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    ip = request.remote_addr or "127.0.0.1"
    logger.info(f"Grade detail accessed: grade_id={grade_id} user={session.get('username')} ip={ip}")
    conn = get_db()
    cur = conn.cursor()
    # VULNERABILITY 2: Insecure Direct Object Reference (IDOR) - no ownership check
    cur.execute("SELECT g.id, g.student_id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.id = %s", (grade_id,))
    grade = cur.fetchone()
    cur.close()
    conn.close()
    return render_template_string(GRADE_HTML, grade=grade) if grade else ("Grade record not found", 404)

@app.route("/health")
def health():
    logger.info(f"Health check probe ip={request.remote_addr or '127.0.0.1'}")
    return jsonify({"status": "ok", "app": "EduGrade"}), 200

if __name__ == "__main__":
    init_db()
    # VULNERABILITY 4: debug=True enabled in execution
    app.run(host="0.0.0.0", port=5000, debug=True)
