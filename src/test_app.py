from concurrent.futures import ThreadPoolExecutor
from datetime import date
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app


class ActivityApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.database_patch = patch.object(app, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        app.initialize_database()
        connection = app.connect_to_database()
        try:
            connection.execute(
                """
                INSERT INTO activities (name, description, schedule, max_participants)
                VALUES ('Test Activity', 'Test', 'Monday', 1)
                """
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def save_student(self, email):
        app.save_student(
            app.StudentProfile(email=email, name=email.split("@")[0], grade_level="11")
        )

    def test_unregister_releases_capacity(self):
        self.save_student("first@example.edu")
        self.save_student("second@example.edu")
        app.signup_for_activity("Test Activity", "first@example.edu")
        with self.assertRaises(HTTPException) as error:
            app.signup_for_activity("Test Activity", "second@example.edu")
        self.assertEqual(error.exception.status_code, 400)

        app.unregister_from_activity("Test Activity", "first@example.edu")
        result = app.signup_for_activity("Test Activity", "second@example.edu")
        self.assertIn("second@example.edu", result["message"])

    def test_concurrent_signups_cannot_exceed_capacity(self):
        emails = ["one@example.edu", "two@example.edu"]
        for email in emails:
            self.save_student(email)

        def attempt_signup(email):
            try:
                app.signup_for_activity("Test Activity", email)
                return "registered"
            except HTTPException as error:
                return error.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt_signup, emails))

        self.assertCountEqual(results, ["registered", 400])
        activity = app.get_activities()["Test Activity"]
        self.assertEqual(len(activity["participants"]), 1)

    def test_profiles_sessions_and_attendance_persist(self):
        self.save_student("student@example.edu")
        app.signup_for_activity("Test Activity", "student@example.edu")
        created = app.create_activity_session(
            "Test Activity", app.SessionCreate(session_date=date(2026, 10, 21))
        )
        app.set_attendance(
            created["id"],
            app.AttendanceUpdate(
                student_email="student@example.edu", status="present"
            ),
        )

        app.initialize_database()

        sessions = app.get_activity_sessions("Test Activity")
        self.assertEqual(sessions[0]["attendance"][0]["status"], "present")
        self.assertEqual(
            app.get_student_attendance("student@example.edu"),
            [
                {
                    "session_date": "2026-10-21",
                    "status": "present",
                    "activity_name": "Test Activity",
                }
            ],
        )

    def test_restart_does_not_restore_unregistered_seed_students(self):
        app.unregister_from_activity("Chess Club", "michael@mergington.edu")

        app.initialize_database()

        participants = app.get_activities()["Chess Club"]["participants"]
        self.assertNotIn("michael@mergington.edu", participants)


if __name__ == "__main__":
    unittest.main()
