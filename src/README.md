# Mergington High School Activities API

FastAPI application for viewing extracurricular activities, registering students,
and recording attendance for individual sessions. SQLite stores activities,
student profiles, registrations, sessions, and attendance between server restarts.

## Run the application

From the repository root, install dependencies and start the server:

```sh
pip install -r requirements.txt
uvicorn src.app:app --reload
```

The SQLite database is created at `src/activities.sqlite3` by default. Set
`ACTIVITY_DATABASE_PATH` to use a different database file.

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/activities` | List activities, participant emails, and capacity |
| `PUT` | `/students` | Create or update a student profile (`email`, `name`, `grade_level`) |
| `GET` | `/students` | List student profiles |
| `POST` | `/activities/{activity_name}/signup?email=student@example.edu` | Register an existing student profile |
| `DELETE` | `/activities/{activity_name}/unregister?email=student@example.edu` | Remove a registration and release its spot |
| `POST` | `/activities/{activity_name}/sessions` | Create a session with JSON `{"session_date":"2026-10-21"}` |
| `GET` | `/activities/{activity_name}/sessions` | List sessions and registered students' attendance |
| `PUT` | `/sessions/{session_id}/attendance` | Record attendance with JSON `{"student_email":"student@example.edu","status":"present"}` |
| `GET` | `/activities/{activity_name}/attendance` | Review attendance records for an activity |
| `GET` | `/students/{student_email}/attendance` | Review attendance records for a student |

Registration is serialized in a SQLite write transaction, so simultaneous
requests cannot exceed an activity's capacity. A student profile must exist
before the student can register.

## Tests

Run the API tests from the repository root:

```sh
python -m unittest discover -s src -p 'test_*.py'
```
