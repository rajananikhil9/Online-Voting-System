from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    session,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from models import (
    db,
    Student,
    Election,
    VoterEligibility,
    CandidateApplication,
    ElectionPosition,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ==========================================
# STUDENT LOGIN
# ==========================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        reg_no = request.form.get("reg_no", "").strip()
        password = request.form.get("password", "")

        # Validate empty fields
        if not reg_no or not password:

            flash(
                "Enter your registration number and password.",
                "error",
            )

            return render_template("auth/login.html")

        # Find student
        student = Student.query.filter_by(
            reg_no=reg_no
        ).first()

        # Check student existence
        if not student:

            print("LOGIN DEBUG: Student not found:", reg_no)

            flash(
                "Invalid registration number or password.",
                "error",
            )

            return render_template("auth/login.html"), 401

        # Check password hash
        if not student.password_hash:

            print("LOGIN DEBUG: Password hash is missing:", reg_no)

            flash(
                "Invalid registration number or password.",
                "error",
            )

            return render_template("auth/login.html"), 401

        # Verify password
        try:

            password_valid = check_password_hash(
                student.password_hash,
                password,
            )

        except (ValueError, TypeError) as e:

            print("LOGIN DEBUG: Password hash error:", str(e))

            password_valid = False

        if not password_valid:

            print("LOGIN DEBUG: Password does not match:", reg_no)

            flash(
                "Invalid registration number or password.",
                "error",
            )

            return render_template("auth/login.html"), 401

        # Authentication successful
        print("LOGIN DEBUG: Student authentication successful:", reg_no)

        # Remove only previous student session data.
        # Preserve admin session data.
        session.pop("student_id", None)
        session.pop("reg_no", None)

        session["student_id"] = student.id
        session["reg_no"] = student.reg_no

        flash(
            "Login successful. Welcome!",
            "success",
        )

        return redirect(url_for("auth.dashboard"))

    return render_template("auth/login.html")


# ==========================================
# CHANGE PASSWORD
# ==========================================

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():

    student_id = session.get("student_id")

    if not student_id:

        return redirect(url_for("auth.login"))

    student = db.session.get(Student, student_id)

    if student is None:

        session.pop("student_id", None)
        session.pop("reg_no", None)

        return redirect(url_for("auth.login"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Password length validation
        if len(password) < 12:

            flash(
                "Your new password must contain at least 12 characters.",
                "error",
            )

            return render_template("auth/change_password.html")

        # Confirm password
        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error",
            )

            return render_template("auth/change_password.html")

        # Prevent using the same password
        if student.password_hash:

            if check_password_hash(
                student.password_hash,
                password,
            ):

                flash(
                    "Choose a password different from your current password.",
                    "error",
                )

                return render_template("auth/change_password.html")

        # Generate secure password hash
        student.password_hash = generate_password_hash(password)

        student.must_change_password = False

        try:

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print("CHANGE PASSWORD ERROR:", str(e))

            flash(
                "Could not update your password. Please try again.",
                "error",
            )

            return render_template("auth/change_password.html")

        flash(
            "Password changed successfully.",
            "success",
        )

        return redirect(url_for("auth.dashboard"))

    return render_template("auth/change_password.html")


# ==========================================
# STUDENT DASHBOARD
# ==========================================

@auth_bp.route("/dashboard")
def dashboard():

    from datetime import datetime
    from models import Ballot

    student_id = session.get("student_id")

    if not student_id:

        return redirect(url_for("auth.login"))

    student = db.session.get(Student, student_id)

    if student is None:

        session.pop("student_id", None)
        session.pop("reg_no", None)

        return redirect(url_for("auth.login"))

    now = datetime.now()

    eligibility_records = VoterEligibility.query.filter_by(
        student_id=student.id
    ).all()

    ongoing_count = 0
    completed_count = 0
    voted_count = 0

    available_elections = []

    for eligibility in eligibility_records:

        election = db.session.get(
            Election,
            eligibility.election_id,
        )

        if election is None:
            continue

        ballot = Ballot.query.filter_by(
            election_id=election.id,
            voter_id=student.id,
        ).first()

        has_voted = ballot is not None

        # Count each vote only once.
        if has_voted:

            voted_count += 1

        # Only show active elections assigned to this student.
        if election.status != "active":

            continue

        # Determine election status based on dates.
        if now < election.start_at:

            election_state = "Upcoming"

        elif election.start_at <= now < election.end_at:

            election_state = "Ongoing"

            ongoing_count += 1

        else:

            election_state = "Completed"

            completed_count += 1

        available_elections.append(
            {
                "election": election,
                "has_voted": has_voted,
                "election_state": election_state,
            }
        )

    return render_template(
        "student/dashboard.html",
        student=student,
        ongoing_count=ongoing_count,
        completed_count=completed_count,
        voted_count=voted_count,
        available_elections=available_elections,
        now=now,
    )


# ==========================================
# STUDENT LOGOUT
# ==========================================

@auth_bp.route("/logout", methods=["POST"])
def logout():

    if not session.get("student_id"):

        return redirect(url_for("auth.login"))

    # Remove only student session data.
    # Preserve admin session data.
    session.pop("student_id", None)
    session.pop("reg_no", None)

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(url_for("auth.login"))


# ==========================================
# CANDIDATE APPLICATION
# ==========================================

ALLOWED_POSITIONS = [
    "President",
    "Vice President",
    "General Secretary",
    "Secretary",
    "Joint Secretary",
    "Treasurer",
    "Sports Secretary",
]


@auth_bp.route("/candidate-application", methods=["GET", "POST"])
def candidate_application():

    student_id = session.get("student_id")

    if not student_id:

        return redirect(url_for("auth.login"))

    student = db.session.get(Student, student_id)

    if student is None:

        session.pop("student_id", None)
        session.pop("reg_no", None)

        return redirect(url_for("auth.login"))

    # Fetch all draft elections.
    eligible_elections = (
        Election.query
        .filter_by(status="draft")
        .order_by(Election.id.desc())
        .all()
    )

    print("Logged-in Student ID:", student.id)

    print("Draft Elections Found:", len(eligible_elections))

    for election in eligible_elections:

        print("Election:", election.id, election.title)

        print(
            "Positions:",
            [p.name for p in election.available_positions]
        )

    if request.method == "POST":

        election_id = request.form.get(
            "election_id",
            type=int,
        )

        position = request.form.get(
            "position",
            "",
        ).strip()

        manifesto = request.form.get(
            "manifesto",
            "",
        ).strip()

        if not election_id or not position:

            flash(
                "Please select an election and position.",
                "error",
            )

            return redirect(
                url_for("auth.candidate_application")
            )

        election = db.session.get(
            Election,
            election_id,
        )

        if not election or election.status != "draft":

            flash(
                "Applications are not available for this election.",
                "error",
            )

            return redirect(
                url_for("auth.candidate_application")
            )

        # Verify that the position belongs to this election.
        available_position = ElectionPosition.query.filter_by(
            election_id=election.id,
            name=position,
        ).first()

        if not available_position:

            flash(
                "This position is not available for the selected election.",
                "error",
            )

            return redirect(
                url_for("auth.candidate_application")
            )

        # Prevent duplicate applications.
        existing_application = CandidateApplication.query.filter_by(
            election_id=election.id,
            student_id=student.id,
            position=position,
        ).first()

        if existing_application:

            flash(
                "You have already applied for this position.",
                "error",
            )

            return redirect(
                url_for("auth.candidate_application")
            )

        application = CandidateApplication(
            student_id=student.id,
            election_id=election.id,
            position=position,
            manifesto=manifesto,
            status="pending",
        )

        try:

            db.session.add(application)

            db.session.commit()

            flash(
                "Application submitted successfully. Waiting for admin approval.",
                "success",
            )

        except Exception as e:

            db.session.rollback()

            print(
                "Candidate application error:",
                str(e),
            )

            flash(
                "Could not submit your application. Please try again.",
                "error",
            )

        return redirect(
            url_for("auth.my_candidate_applications")
        )

    return render_template(
        "student/candidate_application.html",
        student=student,
        elections=eligible_elections,
    )


# ==========================================
# MY CANDIDATE APPLICATIONS
# ==========================================

@auth_bp.route("/my-candidate-applications")
def my_candidate_applications():

    print("\n===== MY APPLICATIONS DEBUG =====")

    print("Session:", dict(session))

    student_id = session.get("student_id")

    print("Student ID:", student_id)

    if not student_id:

        print("ERROR: Student ID missing from session")

        return redirect(url_for("auth.login"))

    student = db.session.get(
        Student,
        student_id,
    )

    print(
        "Student found:",
        student is not None,
    )

    if student is None:

        print("ERROR: Student record not found")

        session.pop("student_id", None)
        session.pop("reg_no", None)

        return redirect(url_for("auth.login"))

    applications = (
        CandidateApplication.query
        .filter_by(student_id=student.id)
        .order_by(CandidateApplication.applied_at.desc())
        .all()
    )

    print(
        "Applications found:",
        len(applications),
    )

    print("===== END DEBUG =====\n")

    return render_template(
        "student/my_candidate_applications.html",
        student=student,
        applications=applications,
    )