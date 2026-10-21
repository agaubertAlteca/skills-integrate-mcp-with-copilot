"""
High School Management System API

A FastAPI application for extracurricular activities, student registrations,
and attendance tracking.
"""

from contextlib import asynccontextmanager
from datetime import date
import os
from pathlib import Path
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


current_dir = Path(__file__).parent
DATABASE_PATH = Path(
    os.getenv("ACTIVITY_DATABASE_PATH", current_dir / "activities.sqlite3")
)

DEFAULT_ACTIVITIES = {
    "Chess Club": (
        "Learn strategies and compete in chess tournaments",
        "Fridays, 3:30 PM - 5:00 PM",
        12,
        ["michael@mergington.edu", "daniel@mergington.edu"],
    ),
    "Programming Class": (
        "Learn programming fundamentals and build software projects",
        "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        20,
        ["emma@mergington.edu", "sophia@mergington.edu"],
    ),
    "Gym Class": (
        "Physical education and sports activities",
        "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        30,
        ["john@mergington.edu", "olivia@mergington.edu"],
    ),
    "Soccer Team": (
        "Join the school soccer team and compete in matches",
        "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        22,
        ["liam@mergington.edu", "noah@mergington.edu"],
    ),
    "Basketball Team": (
        "Practice and play basketball with the school team",
        "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        15,
        ["ava@mergington.edu", "mia@mergington.edu"],
    ),
    "Art Club": (
        "Explore your creativity through painting and drawing",
        "Thursdays, 3:30 PM - 5:00 PM",
        15,
        ["amelia@mergington.edu", "harper@mergington.edu"],
    ),
    "Drama Club": (
        "Act, direct, and produce plays and performances",
        "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        20,
        ["ella@mergington.edu", "scarlett@mergington.edu"],
    ),
    "Math Club": (
        "Solve challenging problems and participate in math competitions",
        "Tuesdays, 3:30 PM - 4:30 PM",
        10,
        ["james@mergington.edu", "benjamin@mergington.edu"],
    ),
    "Debate Team": (
        "Develop public speaking and argumentation skills",
        "Fridays, 4:00 PM - 5:30 PM",
        12,
        ["charlotte@mergington.edu", "henry@mergington.edu"],
    ),
}


class StudentProfile(BaseModel):
    email: str = Field(min_length=1)
    name: str = Field(min_length=1)
    grade_level: str = Field(min_length=1)


class SessionCreate(BaseModel):
    session_date: date


class AttendanceUpdate(BaseModel):
    student_email: str = Field(min_length=1)
    status: Literal["present", "absent"]


def connect_to_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize_database() -> None:
    connection = connect_to_database()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants >= 0)
            );
            CREATE TABLE IF NOT EXISTS students (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                grade_level TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS registrations (
                activity_id INTEGER NOT NULL REFERENCES activities(id),
                student_email TEXT NOT NULL REFERENCES students(email),
                PRIMARY KEY (activity_id, student_email)
            );
            CREATE TABLE IF NOT EXISTS activity_sessions (
                id INTEGER PRIMARY KEY,
                activity_id INTEGER NOT NULL REFERENCES activities(id),
                session_date TEXT NOT NULL,
                UNIQUE (activity_id, session_date)
            );
            CREATE TABLE IF NOT EXISTS attendance (
                session_id INTEGER NOT NULL REFERENCES activity_sessions(id),
                student_email TEXT NOT NULL REFERENCES students(email),
                status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
                PRIMARY KEY (session_id, student_email)
            );
            """
        )
        for name, (description, schedule, capacity, participants) in (
            DEFAULT_ACTIVITIES.items()
        ):
            inserted_activity = connection.execute(
                """
                INSERT OR IGNORE INTO activities
                    (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, schedule, capacity),
            ).rowcount == 1
            if not inserted_activity:
                continue
            activity_id = connection.execute(
                "SELECT id FROM activities WHERE name = ?", (name,)
            ).fetchone()["id"]
            for email in participants:
                connection.execute(
                    "INSERT OR IGNORE INTO students (email, name, grade_level) "
                    "VALUES (?, ?, ?)",
                    (email, email.split("@", maxsplit=1)[0], "Unknown"),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO registrations "
                    "(activity_id, student_email) VALUES (?, ?)",
                    (activity_id, email),
                )
        connection.commit()
    finally:
        connection.close()


def activity_or_404(connection: sqlite3.Connection, activity_name: str) -> sqlite3.Row:
    activity = connection.execute(
        "SELECT * FROM activities WHERE name = ?", (activity_name,)
    ).fetchone()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Mergington High School API",
    description="API for activities, student registrations, and attendance",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    connection = connect_to_database()
    try:
        activities = connection.execute(
            "SELECT * FROM activities ORDER BY name"
        ).fetchall()
        result = {}
        for activity in activities:
            participants = connection.execute(
                """
                SELECT student_email FROM registrations
                WHERE activity_id = ? ORDER BY student_email
                """,
                (activity["id"],),
            ).fetchall()
            result[activity["name"]] = {
                "description": activity["description"],
                "schedule": activity["schedule"],
                "max_participants": activity["max_participants"],
                "participants": [row["student_email"] for row in participants],
            }
        return result
    finally:
        connection.close()


@app.put("/students")
def save_student(profile: StudentProfile):
    connection = connect_to_database()
    try:
        connection.execute(
            """
            INSERT INTO students (email, name, grade_level) VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                name = excluded.name,
                grade_level = excluded.grade_level
            """,
            (profile.email, profile.name, profile.grade_level),
        )
        connection.commit()
        return profile.model_dump()
    finally:
        connection.close()


@app.get("/students")
def get_students():
    connection = connect_to_database()
    try:
        students = connection.execute(
            "SELECT email, name, grade_level FROM students ORDER BY name, email"
        ).fetchall()
        return [dict(student) for student in students]
    finally:
        connection.close()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Register a student profile, without exceeding the activity capacity."""
    connection = connect_to_database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        activity = activity_or_404(connection, activity_name)
        student = connection.execute(
            "SELECT email FROM students WHERE email = ?", (email,)
        ).fetchone()
        if student is None:
            raise HTTPException(status_code=404, detail="Student profile not found")

        already_registered = connection.execute(
            "SELECT 1 FROM registrations WHERE activity_id = ? AND student_email = ?",
            (activity["id"], email),
        ).fetchone()
        if already_registered:
            raise HTTPException(
                status_code=400, detail="Student is already signed up"
            )

        participant_count = connection.execute(
            "SELECT COUNT(*) FROM registrations WHERE activity_id = ?",
            (activity["id"],),
        ).fetchone()[0]
        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        connection.execute(
            "INSERT INTO registrations (activity_id, student_email) VALUES (?, ?)",
            (activity["id"], email),
        )
        connection.commit()
        return {"message": f"Signed up {email} for {activity_name}"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student and release the activity spot."""
    connection = connect_to_database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        activity = activity_or_404(connection, activity_name)
        registration = connection.execute(
            "SELECT 1 FROM registrations WHERE activity_id = ? AND student_email = ?",
            (activity["id"], email),
        ).fetchone()
        if registration is None:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )
        connection.execute(
            "DELETE FROM registrations WHERE activity_id = ? AND student_email = ?",
            (activity["id"], email),
        )
        connection.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.post("/activities/{activity_name}/sessions", status_code=201)
def create_activity_session(activity_name: str, session: SessionCreate):
    connection = connect_to_database()
    try:
        activity = activity_or_404(connection, activity_name)
        try:
            cursor = connection.execute(
                "INSERT INTO activity_sessions (activity_id, session_date) "
                "VALUES (?, ?)",
                (activity["id"], session.session_date.isoformat()),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="A session already exists for this date"
            ) from error
        connection.commit()
        return {"id": cursor.lastrowid, "session_date": session.session_date.isoformat()}
    finally:
        connection.close()


@app.get("/activities/{activity_name}/sessions")
def get_activity_sessions(activity_name: str):
    connection = connect_to_database()
    try:
        activity = activity_or_404(connection, activity_name)
        rows = connection.execute(
            """
            SELECT s.id, s.session_date, st.email, st.name, st.grade_level, a.status
            FROM activity_sessions AS s
            LEFT JOIN registrations AS r ON r.activity_id = s.activity_id
            LEFT JOIN students AS st ON st.email = r.student_email
            LEFT JOIN attendance AS a
                ON a.session_id = s.id AND a.student_email = st.email
            WHERE s.activity_id = ?
            ORDER BY s.session_date, st.name, st.email
            """,
            (activity["id"],),
        ).fetchall()
        sessions = {}
        for row in rows:
            session = sessions.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "session_date": row["session_date"],
                    "attendance": [],
                },
            )
            if row["email"] is not None:
                session["attendance"].append(
                    {
                        "email": row["email"],
                        "name": row["name"],
                        "grade_level": row["grade_level"],
                        "status": row["status"],
                    }
                )
        return list(sessions.values())
    finally:
        connection.close()


@app.put("/sessions/{session_id}/attendance")
def set_attendance(session_id: int, attendance: AttendanceUpdate):
    connection = connect_to_database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        session = connection.execute(
            "SELECT activity_id FROM activity_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        registration = connection.execute(
            "SELECT 1 FROM registrations WHERE activity_id = ? AND student_email = ?",
            (session["activity_id"], attendance.student_email),
        ).fetchone()
        if registration is None:
            raise HTTPException(
                status_code=404, detail="Student is not registered for this activity"
            )
        connection.execute(
            """
            INSERT INTO attendance (session_id, student_email, status)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id, student_email)
            DO UPDATE SET status = excluded.status
            """,
            (session_id, attendance.student_email, attendance.status),
        )
        connection.commit()
        return {
            "session_id": session_id,
            "student_email": attendance.student_email,
            "status": attendance.status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.get("/students/{student_email}/attendance")
def get_student_attendance(student_email: str):
    connection = connect_to_database()
    try:
        student = connection.execute(
            "SELECT email FROM students WHERE email = ?", (student_email,)
        ).fetchone()
        if student is None:
            raise HTTPException(status_code=404, detail="Student profile not found")
        records = connection.execute(
            """
            SELECT s.session_date, a.status, activity.name AS activity_name
            FROM attendance AS a
            JOIN activity_sessions AS s ON s.id = a.session_id
            JOIN activities AS activity ON activity.id = s.activity_id
            WHERE a.student_email = ?
            ORDER BY s.session_date, activity.name
            """,
            (student_email,),
        ).fetchall()
        return [dict(record) for record in records]
    finally:
        connection.close()


@app.get("/activities/{activity_name}/attendance")
def get_activity_attendance(activity_name: str):
    connection = connect_to_database()
    try:
        activity = activity_or_404(connection, activity_name)
        records = connection.execute(
            """
            SELECT s.session_date, st.email, st.name, st.grade_level, a.status
            FROM attendance AS a
            JOIN activity_sessions AS s ON s.id = a.session_id
            JOIN students AS st ON st.email = a.student_email
            WHERE s.activity_id = ?
            ORDER BY s.session_date, st.name, st.email
            """,
            (activity["id"],),
        ).fetchall()
        return [dict(record) for record in records]
    finally:
        connection.close()
