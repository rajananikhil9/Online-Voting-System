from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session,
    flash,
)

from datetime import datetime

from models import (
    db,
    Student,
    Election,
    VoterEligibility,
)


student_dashboard_bp = Blueprint(
    "student_dashboard",
    __name__,
    url_prefix="/student"
)


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@student_dashboard_bp.route("/dashboard")
def dashboard():

    print("\n========== STUDENT DASHBOARD DEBUG ==========")
    print("Session Data:", dict(session))

    # Check login
    student_id = session.get("student_id")

    print("Student ID:", student_id)

    if not student_id:
        print("ERROR: Student session is missing.")
        print("============================================\n")

        flash("Please log in first.", "error")
        return redirect(url_for("auth.login"))

    # Fetch student
    student = db.session.get(Student, student_id)

    if student is None:
        print("ERROR: Student record not found.")
        print("Student ID:", student_id)
        print("============================================\n")

        flash(
            "Student account could not be found. Please contact the administrator.",
            "error"
        )

        return redirect(url_for("auth.login"))

    print("SUCCESS: Student session is valid.")
    print("Registration Number:", student.reg_no)

    # No forced password change on first login

    now = datetime.now()

    # Get elections this student is eligible for
    eligibility_records = VoterEligibility.query.filter_by(
        student_id=student.id
    ).all()

    ongoing_count = 0
    completed_count = 0
    voted_count = 0

    for eligibility in eligibility_records:

        election = db.session.get(
            Election,
            eligibility.election_id
        )

        if election is None:
            continue

        if election.status != "active":
            continue

        if election.start_at <= now < election.end_at:
            ongoing_count += 1

        elif now >= election.end_at:
            completed_count += 1

        if eligibility.has_voted:
            voted_count += 1

    print("Dashboard loaded successfully.")
    print("============================================\n")

    return render_template(
        "student/dashboard.html",
        student=student,
        ongoing_count=ongoing_count,
        completed_count=completed_count,
        voted_count=voted_count
    )