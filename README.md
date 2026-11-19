# EduGrade - Student Grading Portal (DevSecOps Project)

**EduGrade** is a lightweight web application built with **Flask** and **PostgreSQL**. It is designed as an educational application for DevSecOps training (threat modeling, SAST, DAST, SCA, container hardening, CI/CD blocking policies, and runtime observability).

---

## 1. Quick Start with Docker Compose

### Prerequisites
- Docker & Docker Compose installed and running.

### Launch Containers
```bash
docker compose up --build
```

- **Application**: [http://localhost:5000](http://localhost:5000)
- **Health Check**: [http://localhost:5000/health](http://localhost:5000/health)

To stop containers:
```bash
docker compose down -v
```

---

## 2. Running Unit Tests

Standalone unit tests in [test_app.py](file:///c:/Users/zak/Desktop/devseccops/test_app.py) run directly without requiring a database:
```bash
# Using standard Python unittest
python test_app.py

# Or using pytest
pytest
```

---

## 3. Fictive Accounts & Seeded Data

On startup, tables (`users`, `grades`) are automatically created and seeded:

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `prof_smith` | `teacher123` | `teacher` | Course Instructor (can view all grades) |
| `alice` | `student123` | `student` | Student (ID: 2) |
| `bob` | `student123` | `student` | Student (ID: 3) |
| `charlie` | `student123` | `student` | Student (ID: 4) |

### Fictive Grades Seeded:
- **Alice (ID: 2)**: Math (18.5/20), DevSecOps (16.0/20)
- **Bob (ID: 3)**: Math (11.0/20), DevSecOps (14.5/20)
- **Charlie (ID: 4)**: Math (09.0/20), DevSecOps (17.0/20)

---

## 4. Security Hardening & Vulnerability Remediation

In accordance with the DevSecOps project milestone, all 5 deliberate vulnerabilities have been remediated and hardened against exploitation, while maintaining runtime threat detection and telemetry logging.

### Summary of Changes

| # | Vulnerability | OWASP Top 10 | Status | Target File | Line(s) | Fix Summary |
|---|---|---|---|---|---|---|
| **1** | SQL Injection (SQLi) | A03:2021 - Injection | **FIXED** | [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py) | L111–112 | Parameterized SQL query placeholder `%s`. |
| **2** | IDOR | A01:2021 - Broken Access Control | **FIXED** | [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py) | L131–134 | Ownership & role authorization check (`role == teacher` or owning student). |
| **3** | Reflected XSS | A03:2021 - Injection | **FIXED** | [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py) | L27 | Removed `|safe` filter; enabled Jinja2 automatic HTML escaping. |
| **4a** | Hardcoded Secret Fallback | A05:2021 - Security Misconfiguration | **FIXED** | [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py) | L15–18 | `SECRET_KEY` read strictly from env; fails startup if missing. |
| **4b** | Debug Mode Enabled | A05:2021 - Security Misconfiguration | **FIXED** | [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py) | L147 | `debug=False` enforced in application runner. |
| **5** | Vulnerable Dependency | A06:2021 - Outdated Components | **FIXED** | [app/requirements.txt](file:///c:/Users/zak/Desktop/devseccops/app/requirements.txt) | L1–2 | Upgraded to `Flask>=3.0.0` and `Werkzeug>=3.0.6`. |

---

### Detailed Breakdown of Applied Fixes

#### Change 1: Parameterized SQL Queries in `/search`
- **File**: [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py#L111-L112)
- **Vulnerable Code (Before)**:
  ```python
  query = f"SELECT g.id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.subject ILIKE '%{q}%'"
  cur.execute(query)
  ```
- **Remediated Code (After)**:
  ```python
  query = "SELECT g.id, u.username, g.subject, g.grade, g.comment FROM grades g JOIN users u ON g.student_id = u.id WHERE g.subject ILIKE %s"
  cur.execute(query, (f"%{q}%",))
  ```
- **Security Impact**: User input is now treated strictly as a data literal rather than executable SQL syntax. SQL injection payloads (such as `' UNION SELECT ... --`) are rendered completely harmless.
- **Threat Observability**: The `SECURITY_ALERT type=sqli_attempt ip=...` logging hook is preserved to provide real-time SIEM alerts when attack payloads are detected.

---

#### Change 2: Ownership & Authorization Check on `/grades/<id>`
- **File**: [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py#L131-L134)
- **Vulnerable Code (Before)**:
  ```python
  cur.execute("SELECT ... WHERE g.id = %s", (grade_id,))
  grade = cur.fetchone()
  return render_template_string(GRADE_HTML, grade=grade)
  ```
- **Remediated Code (After)**:
  ```python
  if session.get("role") != "teacher" and grade["student_id"] != session.get("user_id"):
      logger.warning(f"SECURITY_ALERT type=unauthorized_access user={session.get('username')} grade_id={grade_id} ip={ip}")
      return "Forbidden: You are not authorized to view this grade record", 403
  ```
- **Security Impact**: Enforces strict horizontal and vertical access control. Students can only view their own grades (`grade.student_id == session.user_id`), instructors can view all student grades, and unauthorized attempts are rejected with HTTP 403 and logged as security alerts.

---

#### Change 3: Contextual HTML Auto-Escaping in `/search`
- **File**: [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py#L27)
- **Vulnerable Code (Before)**:
  ```html
  <h4>Search results for: {{ q_raw|safe }}</h4>
  ```
- **Remediated Code (After)**:
  ```html
  <h4>Search results for: {{ q_val }}</h4>
  ```
- **Security Impact**: Removing the Jinja2 `|safe` filter enables default contextual escaping. Input characters such as `<`, `>`, `"`, and `&` are automatically converted to their respective HTML entities (`&lt;`, `&gt;`), neutralizing reflected XSS attempts (e.g., `<script>alert(1)</script>`).

---

#### Change 4: Strict `SECRET_KEY` Environment Loading & `debug=False`
- **File**: [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py#L15-L18) and [app/app.py](file:///c:/Users/zak/Desktop/devseccops/app/app.py#L147)
- **Vulnerable Code (Before)**:
  ```python
  SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-hardcoded-secret-key-edugrade-2026")
  ...
  app.run(host="0.0.0.0", port=5000, debug=True)
  ```
- **Remediated Code (After)**:
  ```python
  SECRET_KEY = os.environ.get("SECRET_KEY")
  if not SECRET_KEY:
      logger.error("FATAL: SECRET_KEY environment variable is required and must not be empty.")
      sys.exit(1)
  ...
  app.run(host="0.0.0.0", port=5000, debug=False)
  ```
- **Security Impact**:
  - Eliminates the predictable fallback key, preventing attackers from forging session cookies and escalating privileges.
  - Disabling debug mode eliminates the Werkzeug interactive web debugger on exceptions, preventing unauthenticated Remote Code Execution (RCE).

---

#### Change 5: Upgrade Vulnerable Dependency (`Werkzeug>=3.0.6`)
- **File**: [app/requirements.txt](file:///c:/Users/zak/Desktop/devseccops/app/requirements.txt)
- **Vulnerable Versions (Before)**:
  ```text
  Flask==2.2.5
  Werkzeug==2.2.2
  psycopg2-binary==2.9.9
  ```
- **Remediated Versions (After)**:
  ```text
  Flask>=3.0.0
  Werkzeug>=3.0.6
  psycopg2-binary==2.9.9
  ```
- **Security Impact**:
  - Resolves **CVE-2023-25577** (CVSS 7.5 - High): Denial of service through high multipart field counts.
  - Resolves **CVE-2023-46136** (CVSS 6.5 - Medium): High form-part parsing Denial of Service.
  - SCA tools (Trivy, pip-audit, Safety) now report 0 high/critical known vulnerabilities.

---

## 5. Telemetry & Security Alerts

The application produces single-line structured events to `stdout`:

```text
2026-11-19 01:12:00,100 [WARNING] SECURITY_ALERT type=sqli_attempt ip=192.168.1.50
2026-11-19 01:12:05,230 [WARNING] SECURITY_ALERT type=unauthorized_access user=bob grade_id=1 ip=192.168.1.50
2026-11-19 01:12:10,400 [WARNING] SECURITY_ALERT type=failed_login ip=192.168.1.50 username=admin
```

- **Sensitive Data Privacy**: User passwords, session tokens, and cryptographic keys are strictly excluded from all log streams.
