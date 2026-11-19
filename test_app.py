import os
import sys
import unittest

# Ensure SECRET_KEY is set in environment for testing
os.environ.setdefault("SECRET_KEY", "testing-secret-key-edugrade-env-variable-123456")

# Add app directory to sys.path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
from app import app

class EduGradeStandaloneTests(unittest.TestCase):
    """Unit tests for EduGrade endpoints that require no database connection."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_health_check(self):
        """Verify GET /health returns 200 OK and expected JSON payload."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIsNotNone(json_data)
        self.assertEqual(json_data.get("status"), "ok")
        self.assertEqual(json_data.get("app"), "EduGrade")

    def test_login_page_renders(self):
        """Verify GET /login returns 200 OK and contains login form without contacting DB."""
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EduGrade - Login", response.data)
        self.assertIn(b"Sign In", response.data)

    def test_index_unauthenticated_redirect(self):
        """Verify GET / redirects unauthenticated visitor to /login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    def test_unauthenticated_access_grades_redirects(self):
        """Verify accessing /grades/<id> without login redirects to /login."""
        response = self.client.get("/grades/1")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

if __name__ == "__main__":
    unittest.main()
