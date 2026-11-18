# EduGrade - Student Grading Portal (DevSecOps Security Exercise)

**EduGrade** is a lightweight web application built with **Flask** and **PostgreSQL**. It is designed as a practical educational target for DevSecOps training (SAST, DAST, SCA, Container Security, CI/CD blocking, and Runtime Telemetry).

---

## 1. Quick Start with Docker Compose

### Prerequisites
- Docker & Docker Compose installed.

### Run Application
Start the application and PostgreSQL database:
```bash
docker compose up --build
```

The web application will be accessible at:
- **URL**: [http://localhost:5000](http://localhost:5000)
- **Health check**: [http://localhost:5000/health](http://localhost:5000/health)

To stop and remove containers:
```bash
docker compose down -v
```

---

## 2. Running Unit Tests

The repository includes standalone unit tests in `test_app.py` that execute without requiring a running database:
```bash
# Using Python standard library unittest:
python test_app.py

# Or using pytest:
pytest
```

---

## 3. Fictive Test Accounts & Data

The database is automatically created and seeded on startup with the following fictive accounts:

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `prof_smith` | `teacher123` | `teacher` | Course Instructor |
| `alice` | `student123` | `student` | Student (ID: 2) |
| `bob` | `student123` | `student` | Student (ID: 3) |
| `charlie` | `student123` | `student` | Student (ID: 4) |

### Fictive Grades Seeded:
- **Alice**: Math (18.5/20 - "Excellent performance and rigor"), DevSecOps (16.0/20 - "Good pipeline design")
- **Bob**: Math (11.0/20 - "Needs to revise basics"), DevSecOps (14.5/20 - "Solid practical work")
- **Charlie**: Math (09.0/20 - "Insufficient effort this semester"), DevSecOps (17.0/20 - "Outstanding CTF challenge solver")

---

## 4. Application Routes

- `GET /` : Redirects authenticated users to `/search` or unauthenticated users to `/login`.
- `GET /login`, `POST /login` : User authentication form and submission.
- `GET /logout` : Session termination and redirect.
- `GET /search?q=` : Search grades by subject keyword.
- `GET /grades/<id>` : View detailed grade record and instructor comment.
- `GET /health` : JSON health status probe (`{"status": "ok", "app": "EduGrade"}`).

---

## 5. Security Exercise: Deliberate Vulnerabilities

As part of this security exercise, the application deliberately includes **5 vulnerabilities** across distinct OWASP Top 10 categories:

| # | Vulnerability | OWASP Top 10 | File | Exact Line(s) |
|---|---|---|---|---|
| **1** | SQL Injection (SQLi) | A03:2021 - Injection | `app/app.py` | Line 108-109 |
| **2** | Insecure Direct Object Reference (IDOR) | A01:2021 - Broken Access Control | `app/app.py` | Lines 124-129 |
| **3** | Reflected Cross-Site Scripting (XSS) | A03:2021 - Injection | `app/app.py` | Line 25, Line 114 |
| **4** | Hardcoded Secret Fallback & `debug=True` | A05:2021 - Security Misconfiguration | `app/app.py` | Line 15, Line 139 |
| **5** | Outdated Vulnerable Dependency | A06:2021 - Vulnerable Components | `app/requirements.txt` | Line 2 |

---

### Vulnerability 1: SQL Injection (SQLi) in `/search`
- **File**: `app/app.py`
- **Line(s)**: Lines 108–109
  ```python
  query = f"SELECT g.id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.subject ILIKE '%{q}%'"
  cur.execute(query)
  ```
- **Cause**: The user query string parameter `q` is formatted directly into the SQL string via Python f-string interpolation instead of using parameterized queries (`%s`).
- **Impact**: An attacker can inject SQL syntax to bypass authentication, read unauthorized database records, or extract all hashed user credentials using `UNION SELECT`:
  ```sql
  ' UNION SELECT id, username, password_hash, 0, role FROM users --
  ```
- **Remediation**: Use parameterized queries:
  ```python
  cur.execute("SELECT g.id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.subject ILIKE %s", (f"%{q}%",))
  ```

---

### Vulnerability 2: Insecure Direct Object Reference (IDOR) in `/grades/<id>`
- **File**: `app/app.py`
- **Line(s)**: Lines 124–129
  ```python
  cur.execute("SELECT g.id, g.student_id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.id = %s", (grade_id,))
  grade = cur.fetchone()
  ...
  return render_template_string(GRADE_HTML, grade=grade)
  ```
- **Cause**: The endpoint fetches and renders grade details by integer ID without verifying that the authenticated user (`session.get('user_id')`) actually owns the record, or holds a `teacher` role.
- **Impact**: Any authenticated student can view confidential grades and teacher comments of all other students by simply iterating through IDs (e.g., `/grades/1`, `/grades/2`, `/grades/3`, ...).
- **Remediation**: Enforce an authorization ownership check:
  ```python
  if session.get('role') != 'teacher' and grade['student_id'] != session.get('user_id'):
      abort(403)
  ```

---

### Vulnerability 3: Reflected Cross-Site Scripting (XSS) in `/search`
- **File**: `app/app.py`
- **Line(s)**: Line 25 and Line 114
  ```python
  # Line 25 in SEARCH_HTML template:
  <h4>Search results for: {{ q_raw|safe }}</h4>

  # Line 114:
  return render_template_string(SEARCH_HTML, q_raw=q, q_val=q, searched=bool(q), grades=grades)
  ```
- **Cause**: The search query parameter `q` is rendered back to the user interface with Jinja2's `|safe` filter, explicitly disabling contextual HTML escaping.
- **Impact**: Attackers can construct phishing links with embedded JavaScript payloads (`/search?q=<script>alert('XSS')</script>`), leading to session hijacking, credential harvesting, or unauthorized client-side actions.
- **Remediation**: Remove the `|safe` filter and allow Jinja2 to perform automatic HTML escaping:
  ```html
  <h4>Search results for: {{ q }}</h4>
  ```

---

### Vulnerability 4: Hardcoded `SECRET_KEY` Fallback & `debug=True`
- **File**: `app/app.py`
- **Line(s)**: Line 15 and Line 139
  ```python
  # Line 15:
  SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-hardcoded-secret-key-edugrade-2026")

  # Line 139:
  app.run(host="0.0.0.0", port=5000, debug=True)
  ```
- **Cause**: 
  1. A predictable fallback string is hardcoded in the codebase when `SECRET_KEY` is not provided in environment variables.
  2. Flask's debug mode (`debug=True`) is permanently enabled in the runtime invocation.
- **Impact**:
  - The static secret key enables attackers to forge cryptographic Flask session cookies, elevating privileges to any user or teacher account.
  - `debug=True` enables Werkzeug's interactive web debugger on unhandled exceptions, allowing arbitrary code execution (RCE) on the server.
- **Remediation**:
  - Require a strong random secret key from environment variables (fail startup if not set).
  - Disable debug mode in production: `app.run(host="0.0.0.0", port=5000, debug=False)`.

---

### Vulnerability 5: Outdated Vulnerable Dependency (`Werkzeug==2.2.2`)
- **File**: `app/requirements.txt`
- **Line(s)**: Line 2
  ```text
  Werkzeug==2.2.2
  ```
- **Cause**: The dependency is intentionally pinned to an outdated version with known publicly disclosed security advisories.
- **Impact**:
  - **CVE-2023-25577** (CVSS 7.5 - High): Vulnerability in parsing multipart form data where excessive boundary markers cause excessive CPU and memory consumption, leading to a Denial of Service (DoS).
  - **CVE-2023-46136** (CVSS 6.5 - Medium): High number of form parts causing Denial of Service.
- **Remediation**: Upgrade `Werkzeug` to a patched version (e.g., `>=3.0.3`):
  ```text
  Werkzeug>=3.0.3
  ```

---

## 6. Observability & Security Incident Alerts

The application outputs structured single-line log events to `stdout`.

### Security Alert Format
When suspicious SQL characters (`'`, `--`, `UNION`) are detected in the query or failed logins occur, a dedicated security alert is emitted:
- **SQLi attempt detection**:
  ```text
  2026-11-18 18:10:05,123 [WARNING] SECURITY_ALERT type=sqli_attempt ip=192.168.1.100
  ```
- **Failed login attempt**:
  ```text
  2026-11-18 18:10:12,456 [WARNING] SECURITY_ALERT type=failed_login ip=192.168.1.100 username=admin
  ```
- **Zero Secrets Logged**: Passwords, secrets, and auth tokens are strictly omitted from log streams.
