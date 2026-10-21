document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const attendanceStudent = document.getElementById("attendance-student");
  const studentAttendance = document.getElementById("student-attendance");

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, (character) => {
      const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return entities[character];
    });
  }

  function showMessage(message, type) {
    messageDiv.textContent = message;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");
    setTimeout(() => messageDiv.classList.add("hidden"), 5000);
  }

  async function loadSessions(activityName, target) {
    const response = await fetch(
      `/activities/${encodeURIComponent(activityName)}/sessions`
    );
    if (!response.ok) {
      throw new Error("Failed to load sessions");
    }
    const sessions = await response.json();
    target.innerHTML = sessions
      .map(
        (session) => `
          <article class="session-card">
            <h5>Session: ${escapeHTML(session.session_date)}</h5>
            ${
              session.attendance.length
                ? session.attendance
                    .map(
                      (record) => `
                        <div class="attendance-row">
                          <span>${escapeHTML(record.name)} (${escapeHTML(record.email)})</span>
                          <select aria-label="Attendance for ${escapeHTML(record.name)}">
                            <option value="">Not marked</option>
                            <option value="present" ${record.status === "present" ? "selected" : ""}>Present</option>
                            <option value="absent" ${record.status === "absent" ? "selected" : ""}>Absent</option>
                          </select>
                          <button type="button" class="save-attendance"
                            data-session-id="${session.id}"
                            data-email="${escapeHTML(record.email)}">Save</button>
                        </div>
                      `
                    )
                    .join("")
                : "<p>No registered students for this session.</p>"
            }
          </article>`
      )
      .join("");

    target.querySelectorAll(".save-attendance").forEach((button) => {
      button.addEventListener("click", async () => {
        const row = button.closest(".attendance-row");
        const status = row.querySelector("select").value;
        if (!status) {
          showMessage("Choose present or absent before saving.", "error");
          return;
        }
        try {
          const response = await fetch(
            `/sessions/${button.dataset.sessionId}/attendance`,
            {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                student_email: button.dataset.email,
                status,
              }),
            }
          );
          const result = await response.json();
          if (!response.ok) {
            throw new Error(result.detail || "Failed to save attendance");
          }
          showMessage("Attendance saved.", "success");
        } catch (error) {
          showMessage(error.message, "error");
        }
      });
    });
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error("Failed to load activities");
      }
      const activities = await response.json();
      activitiesList.innerHTML = "";
      activitySelect.querySelectorAll("option:not(:first-child)").forEach((option) => {
        option.remove();
      });

      Object.entries(activities).forEach(([name, details], index) => {
        const safeName = escapeHTML(name);
        const sessionDateId = `session-date-${index}`;
        const participantsHTML = details.participants.length
          ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map(
                    (email) => `
                      <li><span class="participant-email">${escapeHTML(email)}</span>
                        <button class="delete-btn" data-activity="${safeName}"
                          data-email="${escapeHTML(email)}" type="button">Unregister</button>
                      </li>`
                  )
                  .join("")}
              </ul>
            </div>`
          : "<p><em>No participants yet</em></p>";
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";
        activityCard.innerHTML = `
          <h4>${safeName}</h4>
          <p>${escapeHTML(details.description)}</p>
          <p><strong>Schedule:</strong> ${escapeHTML(details.schedule)}</p>
          <p><strong>Availability:</strong>
            ${details.max_participants - details.participants.length} spots left</p>
          <div class="participants-container">${participantsHTML}</div>
          <form class="session-form" data-activity="${safeName}">
            <label for="${sessionDateId}">Add attendance session:</label>
            <input id="${sessionDateId}" type="date" required />
            <button type="submit">Create session</button>
          </form>
          <div class="session-list"></div>
        `;
        activitiesList.appendChild(activityCard);
        const sessionForm = activityCard.querySelector(".session-form");
        sessionForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          const sessionDate = sessionForm.querySelector('input[type="date"]').value;
          try {
            const createResponse = await fetch(
              `/activities/${encodeURIComponent(name)}/sessions`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_date: sessionDate }),
              }
            );
            const result = await createResponse.json();
            if (!createResponse.ok) {
              throw new Error(result.detail || "Failed to create session");
            }
            await loadSessions(name, activityCard.querySelector(".session-list"));
            showMessage("Attendance session created.", "success");
          } catch (error) {
            showMessage(error.message, "error");
          }
        });
        const sessionList = activityCard.querySelector(".session-list");
        loadSessions(name, sessionList).catch((error) => {
          sessionList.textContent = "Failed to load sessions.";
          console.error(error);
        });

        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
      await loadStudents();
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  async function loadStudents() {
    const response = await fetch("/students");
    if (!response.ok) {
      throw new Error("Failed to load students");
    }
    const students = await response.json();
    attendanceStudent.querySelectorAll("option:not(:first-child)").forEach((option) => {
      option.remove();
    });
    students.forEach((student) => {
      const option = document.createElement("option");
      option.value = student.email;
      option.textContent = `${student.name} (${student.email})`;
      attendanceStudent.appendChild(option);
    });
  }

  attendanceStudent.addEventListener("change", async () => {
    const email = attendanceStudent.value;
    studentAttendance.innerHTML = "";
    if (!email) {
      return;
    }
    try {
      const response = await fetch(
        `/students/${encodeURIComponent(email)}/attendance`
      );
      const records = await response.json();
      if (!response.ok) {
        throw new Error(records.detail || "Failed to load attendance");
      }
      studentAttendance.innerHTML = records.length
        ? `<ul>${records
            .map(
              (record) =>
                `<li>${escapeHTML(record.session_date)} — ${escapeHTML(record.activity_name)}: ${escapeHTML(record.status)}</li>`
            )
            .join("")}</ul>`
        : "<p>No attendance records yet.</p>";
    } catch (error) {
      studentAttendance.textContent = error.message;
    }
  });

  async function handleUnregister(event) {
    const button = event.currentTarget;
    const activity = button.dataset.activity;
    const email = button.dataset.email;
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/unregister?email=${encodeURIComponent(email)}`,
        { method: "DELETE" }
      );
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "An error occurred");
      }
      showMessage(result.message, "success");
      await fetchActivities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  }

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const profile = {
      name: document.getElementById("name").value.trim(),
      email: document.getElementById("email").value.trim(),
      grade_level: document.getElementById("grade-level").value.trim(),
    };
    const activity = activitySelect.value;
    try {
      const profileResponse = await fetch("/students", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      const profileResult = await profileResponse.json();
      if (!profileResponse.ok) {
        throw new Error(profileResult.detail || "Failed to save student profile");
      }
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/signup?email=${encodeURIComponent(profile.email)}`,
        { method: "POST" }
      );
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "An error occurred");
      }
      showMessage(result.message, "success");
      signupForm.reset();
      await fetchActivities();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });

  fetchActivities();
});
