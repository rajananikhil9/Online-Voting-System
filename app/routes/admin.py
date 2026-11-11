from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from datetime import datetime
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError

from models import (
    db,
    Student,
    Election,
    Ballot,
    Candidate,
    CandidateApplication,
    VoterEligibility,
    ElectionPosition,
    PREDEFINED_POSITIONS,
)

admin_dashboard_bp = Blueprint(
    "admin_dashboard", __name__, url_prefix="/admin/dashboard"
)


def admin_required(view):
    """Require an authenticated administrator for every admin dashboard route."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in as an administrator.", "error")
            return redirect(url_for("admin_auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


# =====================================================
# ADMIN DASHBOARD
# =====================================================


@admin_dashboard_bp.route("/", methods=["GET"])
@admin_required
def dashboard():

    now = datetime.now()

    elections = Election.query.order_by(Election.id.desc()).all()

    students = Student.query.order_by(Student.name.asc()).all()

    candidates_by_election = {}
    eligible_ids_by_election = {}

    total_eligible = 0
    total_completed_voters = 0

    for election in elections:

        candidates_by_election[election.id] = Candidate.query.filter_by(
            election_id=election.id
        ).all()

        eligible_records = VoterEligibility.query.filter_by(
            election_id=election.id
        ).all()

        eligible_ids_by_election[election.id] = {
            item.student_id for item in eligible_records
        }

        total_eligible += len(eligible_records)

        total_completed_voters += sum(1 for item in eligible_records if item.has_voted)

    total_students = Student.query.count()
    total_elections = len(elections)
    total_candidates = Candidate.query.count()
    total_votes = Ballot.query.count()

    active_elections = sum(
        1
        for election in elections
        if election.status == "active" and election.start_at <= now < election.end_at
    )

    upcoming_elections = sum(
        1
        for election in elections
        if election.status == "active" and now < election.start_at
    )

    completed_elections = sum(
        1
        for election in elections
        if election.status == "completed"
        or (election.status == "active" and now >= election.end_at)
    )

    voter_turnout = (
        round(total_completed_voters / total_eligible * 100, 2) if total_eligible else 0
    )

    return render_template(
        "admin/dashboard.html",
        elections=elections,
        students=students,
        candidates_by_election=candidates_by_election,
        eligible_ids_by_election=eligible_ids_by_election,
        total_students=total_students,
        total_elections=total_elections,
        total_candidates=total_candidates,
        total_votes=total_votes,
        active_elections=active_elections,
        upcoming_elections=upcoming_elections,
        completed_elections=completed_elections,
        voter_turnout=voter_turnout,
    )


# =====================================================
# ADD ELECTION PAGE
# =====================================================


@admin_dashboard_bp.route("/add-election", methods=["GET"])
@admin_required
def add_election_page():

    return render_template("admin/add_election.html")


# =====================================================
# MANAGE DRAFT ELECTIONS
# =====================================================


@admin_dashboard_bp.route("/draft-elections", methods=["GET"])
@admin_required
def manage_draft_elections():

    elections = (
        Election.query.filter_by(status="draft").order_by(Election.id.desc()).all()
    )

    return render_template("admin/draft_elections.html", elections=elections)


# =====================================================
# DELETE ELECTION
# =====================================================


@admin_dashboard_bp.route("/draft-election/<int:election_id>/delete", methods=["POST"])
@admin_required
def delete_draft_election(election_id):

    election = db.session.get(Election, election_id)

    if election is None:
        flash("Election not found.", "error")
        return redirect(url_for("admin_dashboard.candidates_page"))

    # Allow deletion only for draft or active elections.
    if election.status not in ["draft", "active"]:
        flash("This election cannot be deleted.", "error")
        return redirect(url_for("admin_dashboard.candidates_page"))

    # Do not delete expired elections.
    if election.end_at and election.end_at <= datetime.now():
        flash("Expired elections cannot be deleted.", "error")
        return redirect(url_for("admin_dashboard.candidates_page"))

    # Protect all recorded votes.
    existing_vote = Ballot.query.filter_by(election_id=election.id).first()

    if existing_vote:
        flash(
            "This election cannot be deleted because votes have already been recorded.",
            "error",
        )
        return redirect(url_for("admin_dashboard.candidates_page"))

    try:
        CandidateApplication.query.filter_by(election_id=election.id).delete(
            synchronize_session=False
        )

        VoterEligibility.query.filter_by(election_id=election.id).delete(
            synchronize_session=False
        )

        Candidate.query.filter_by(election_id=election.id).delete(
            synchronize_session=False
        )

        ElectionPosition.query.filter_by(election_id=election.id).delete(
            synchronize_session=False
        )

        db.session.delete(election)
        db.session.commit()

        flash("Election deleted successfully!", "success")

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Election deletion failed")

        flash("Could not delete election. Please check the server logs.", "error")

    return redirect(url_for("admin_dashboard.candidates_page"))


# =====================================================
# EDIT DRAFT ELECTION
# =====================================================


@admin_dashboard_bp.route(
    "/draft-election/<int:election_id>/edit", methods=["GET", "POST"]
)
@admin_required
def edit_draft_election(election_id):

    election = db.session.get(Election, election_id)

    if election is None or election.status != "draft":
        flash("Draft election not found.", "error")
        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        start_at_text = request.form.get("start_at", "").strip()
        end_at_text = request.form.get("end_at", "").strip()

        if not title or not start_at_text or not end_at_text:
            flash("Please fill in all required fields.", "error")
            return redirect(
                url_for("admin_dashboard.edit_draft_election", election_id=election.id)
            )

        try:
            start_at = datetime.fromisoformat(start_at_text)
            end_at = datetime.fromisoformat(end_at_text)

            if end_at <= start_at:
                raise ValueError

            election.title = title
            election.description = description
            election.start_at = start_at
            election.end_at = end_at

            db.session.commit()

            flash("Draft election updated successfully.", "success")

            return redirect(url_for("admin_dashboard.manage_draft_elections"))

        except ValueError:
            db.session.rollback()
            flash("Please enter valid election dates.", "error")

        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not update the election.", "error")

    return render_template("admin/edit_draft_election.html", election=election)


# =====================================================
# CREATE ELECTION
# =====================================================


@admin_dashboard_bp.route("/create-election", methods=["POST"])
@admin_required
def create_election():

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()

    start_at_text = request.form.get("start_at", "").strip()
    end_at_text = request.form.get("end_at", "").strip()

    selected_positions = request.form.getlist("positions")

    if not title or not start_at_text or not end_at_text:
        flash("Please fill in all required election fields.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    if not selected_positions:
        flash("Please select at least one election position.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    # Validate positions on the server.
    if len(selected_positions) != len(set(selected_positions)) or any(
        position not in PREDEFINED_POSITIONS for position in selected_positions
    ):
        flash("Invalid election position selection.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    try:
        start_at = datetime.fromisoformat(start_at_text)
        end_at = datetime.fromisoformat(end_at_text)

    except ValueError:
        flash("Please enter valid start and end dates.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    if end_at <= start_at:
        flash("The end time must be after the start time.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    election = Election(
        title=title,
        description=description,
        start_at=start_at,
        end_at=end_at,
        status="draft",
    )

    try:
        db.session.add(election)
        db.session.flush()

        for position in selected_positions:
            db.session.add(ElectionPosition(election_id=election.id, name=position))

        db.session.commit()

        flash("Election and positions created successfully!", "success")

    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not create the election. Please try again.", "error")
        return redirect(url_for("admin_dashboard.add_election_page"))

    return redirect(url_for("admin_dashboard.candidates_page"))


# =====================================================
# MANAGE ELECTIONS / CANDIDATES PAGE
# =====================================================


@admin_dashboard_bp.route("/candidates", methods=["GET"])
@admin_required
def candidates_page():
    elections = Election.query.order_by(Election.id.desc()).all()

    candidates = Candidate.query.order_by(Candidate.id.desc()).all()

    return render_template(
        "admin/candidates.html", elections=elections, candidates=candidates
    )


# =====================================================
# MANAGE VOTERS
# =====================================================


@admin_dashboard_bp.route("/manage-voters", methods=["GET"])
@admin_required
def manage_voters():

    elections = Election.query.order_by(Election.id.desc()).all()

    election_id = request.args.get("election_id", type=int)

    selected_election = None
    students = []
    eligible_student_ids = set()

    if election_id:
        selected_election = db.session.get(Election, election_id)

    if selected_election:
        students = Student.query.order_by(Student.name.asc()).all()

        eligible_records = VoterEligibility.query.filter_by(
            election_id=selected_election.id
        ).all()

        eligible_student_ids = {record.student_id for record in eligible_records}

    return render_template(
        "admin/manage_voters.html",
        elections=elections,
        students=students,
        selected_election=selected_election,
        eligible_student_ids=eligible_student_ids,
    )


# =====================================================
# DELETE CANDIDATE
# =====================================================


@admin_dashboard_bp.route("/candidate/<int:candidate_id>/delete", methods=["POST"])
@admin_required
def delete_candidate(candidate_id):
    candidate = db.session.get(Candidate, candidate_id)

    if candidate is None:
        flash("Candidate not found.", "error")
        return redirect(url_for("admin_dashboard.candidates_page"))

    election = db.session.get(Election, candidate.election_id)
    if election is None or election.status != "draft":
        flash("Candidates can only be deleted while the election is in draft.", "error")
        return redirect(url_for("admin_dashboard.candidates_page"))

    try:
        # A candidate with recorded ballots must not be removed independently.
        if Ballot.query.filter_by(candidate_id=candidate.id).first():
            flash("This candidate has recorded votes and cannot be deleted.", "error")
            return redirect(url_for("admin_dashboard.candidates_page"))

        db.session.delete(candidate)
        db.session.commit()
        flash("Candidate deleted successfully.", "success")

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Candidate deletion error:", str(e))
        flash("Could not delete candidate. Check the server terminal.", "error")

    return redirect(url_for("admin_dashboard.candidates_page"))


# =====================================================
# ASSIGN ELIGIBLE STUDENTS
# =====================================================


@admin_dashboard_bp.route("/<int:election_id>/assign-students", methods=["POST"])
@admin_required
def assign_students(election_id):

    election = db.session.get(Election, election_id)

    if election is None:

        flash("Election not found.", "error")

        return redirect(url_for("admin_dashboard.dashboard"))

    if election.status != "draft":

        flash(
            "Student eligibility can only be changed while the election is in draft.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard.manage_voters", election_id=election.id)
        )

    student_ids = request.form.getlist("student_ids")

    if not student_ids:

        flash("Select at least one student.", "error")

        return redirect(url_for("admin_dashboard.dashboard"))

    try:

        student_ids = list(set(int(sid) for sid in student_ids))

    except (ValueError, TypeError):

        flash("Invalid student selection.", "error")

        return redirect(url_for("admin_dashboard.dashboard"))

    students = Student.query.filter(Student.id.in_(student_ids)).all()

    if len(students) != len(student_ids):

        flash("One or more selected students do not exist.", "error")

        return redirect(url_for("admin_dashboard.dashboard"))

    try:

        for student in students:

            existing = VoterEligibility.query.filter_by(
                election_id=election.id, student_id=student.id
            ).first()

            if existing is None:

                db.session.add(
                    VoterEligibility(
                        election_id=election.id, student_id=student.id, has_voted=False
                    )
                )

        db.session.commit()

        flash(
            f"Eligibility assigned to {len(students)} selected student(s).", "success"
        )

    except SQLAlchemyError:

        db.session.rollback()

        flash("Could not assign student eligibility. Please try again.", "error")

    return redirect(url_for("admin_dashboard.dashboard"))


# =====================================================
# ACTIVATE ELECTION
# =====================================================


@admin_dashboard_bp.route("/<int:election_id>/activate", methods=["POST"])
@admin_required
def activate_election(election_id):

    election = db.session.get(Election, election_id)

    if election is None:

        flash("Election not found.", "error")

        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    if election.status != "draft":

        flash("Only draft elections can be activated.", "error")

        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    candidates_count = Candidate.query.filter_by(election_id=election.id).count()

    if candidates_count < 2:

        flash("Add at least two candidates before activating the election.", "error")

        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    eligible_count = VoterEligibility.query.filter_by(election_id=election.id).count()

    if eligible_count == 0:

        flash(
            "Assign at least one eligible student before activating the election.",
            "error",
        )

        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    if election.end_at <= election.start_at:

        flash("The election dates are invalid.", "error")

        return redirect(url_for("admin_dashboard.manage_draft_elections"))

    try:

        election.status = "active"

        db.session.commit()

        flash("Election activated successfully!", "success")

    except SQLAlchemyError:

        db.session.rollback()

        flash("Could not activate the election. Please try again.", "error")

    return redirect(url_for("admin_dashboard.manage_draft_elections"))


# =====================================================
# STUDENT MANAGEMENT
# =====================================================


@admin_dashboard_bp.route("/students", methods=["GET"])
@admin_required
def student_list():

    search = request.args.get("search", "").strip()

    query = Student.query

    if search:

        query = query.filter(
            db.or_(
                Student.reg_no.ilike(f"%{search}%"),
                Student.name.ilike(f"%{search}%"),
                Student.email.ilike(f"%{search}%"),
                Student.department.ilike(f"%{search}%"),
            )
        )

    students = Student.query.order_by(Student.reg_no.asc()).all()

    return render_template(
        "admin/students.html",
        students=students,
        search=search,
    )


# =====================================================
# CANDIDATE APPLICATIONS
# =====================================================


@admin_dashboard_bp.route("/candidate-applications", methods=["GET"])
@admin_required
def candidate_applications():

    status_filter = request.args.get("status", "all").strip().lower()

    query = (
        db.session.query(CandidateApplication, Student, Election)
        .join(Student, CandidateApplication.student_id == Student.id)
        .join(Election, CandidateApplication.election_id == Election.id)
    )

    if status_filter in {"pending", "approved", "rejected"}:

        query = query.filter(CandidateApplication.status == status_filter)

    else:

        status_filter = "all"

    applications = query.order_by(CandidateApplication.applied_at.desc()).all()

    return render_template(
        "admin/candidate_applications.html",
        applications=applications,
        status_filter=status_filter,
    )


@admin_dashboard_bp.route("/elections", methods=["GET"])
@admin_required
def elections_page():
    elections = Election.query.order_by(Election.id.desc()).all()
    candidates = Candidate.query.order_by(Candidate.id.desc()).all()

    return render_template(
        "admin/elections.html",
        elections=elections,
        candidates=candidates
    )

# =====================================================
# APPROVE CANDIDATE APPLICATION
# =====================================================


@admin_dashboard_bp.route(
    "/candidate-application/<int:application_id>/approve", methods=["POST"]
)
@admin_required
def approve_candidate_application(application_id):

    application = db.session.get(CandidateApplication, application_id)

    if application is None:

        flash("Candidate application not found.", "error")

        return redirect(url_for("admin_dashboard.candidate_applications"))

    if application.status != "pending":

        flash("This application has already been reviewed.", "error")

        return redirect(url_for("admin_dashboard.candidate_applications"))

    election = db.session.get(Election, application.election_id)

    student = db.session.get(Student, application.student_id)

    if election is None or student is None:

        flash("The linked student or election could not be found.", "error")

        return redirect(url_for("admin_dashboard.candidate_applications"))

    if election.status != "draft":

        flash(
            "Applications can only be approved while the election is in draft.", "error"
        )

        return redirect(url_for("admin_dashboard.candidate_applications"))

    try:

        existing_candidate = Candidate.query.filter_by(
            election_id=election.id,
            name=student.name,
            position=application.position,
        ).first()

        if existing_candidate is None:

            db.session.add(
                Candidate(
                    election_id=election.id,
                    name=student.name,
                    position=application.position,
                    manifesto=application.manifesto,
                )
            )

        application.status = "approved"
        application.reviewed_at = datetime.now()
        application.reviewed_by = session.get("admin_id")

        db.session.commit()

        flash("Candidate application approved successfully.", "success")

    except SQLAlchemyError:

        db.session.rollback()

        flash("Could not approve this application. Please try again.", "error")

    return redirect(url_for("admin_dashboard.candidate_applications"))


# =====================================================
# REJECT CANDIDATE APPLICATION
# =====================================================


@admin_dashboard_bp.route(
    "/candidate-application/<int:application_id>/reject", methods=["POST"]
)
@admin_required
def reject_candidate_application(application_id):

    application = db.session.get(CandidateApplication, application_id)

    if application is None:

        flash("Candidate application not found.", "error")

        return redirect(url_for("admin_dashboard.candidate_applications"))

    if application.status != "pending":

        flash("This application has already been reviewed.", "error")

        return redirect(url_for("admin_dashboard.candidate_applications"))

    try:

        application.status = "rejected"
        application.reviewed_at = datetime.now()
        application.reviewed_by = session.get("admin_id")

        db.session.commit()

        flash("Candidate application rejected.", "success")

    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not reject this application. Please try again.", "error")
        return redirect(url_for("admin_dashboard.candidate_applications"))

    return redirect(url_for("admin_dashboard.candidates_page"))
