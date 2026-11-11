from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)

from sqlalchemy.exc import IntegrityError

from models import (
    db,
    Student,
    Election,
    Candidate,
    VoterEligibility,
    Ballot,
)


voting_bp = Blueprint(
    "voting",
    __name__,
    url_prefix="/voting",
)


# =========================================================
# GET LOGGED-IN STUDENT
# =========================================================

def get_logged_in_student():

    student_id = session.get("student_id")

    if not student_id:
        return None

    return db.session.get(Student, student_id)


# =========================================================
# UPDATE VOTING COMPLETION
# =========================================================

def update_voting_completion(election_id, student_id):

    eligibility = VoterEligibility.query.filter_by(
        election_id=election_id,
        student_id=student_id,
    ).first()

    if eligibility is None:
        return

    # Get all unique positions in this election.
    positions = {
        row[0]
        for row in (
            db.session.query(Candidate.position)
            .filter_by(election_id=election_id)
            .distinct()
            .all()
        )
    }

    # Get positions for which this student has voted.
    voted_positions = {
        row[0]
        for row in (
            db.session.query(Ballot.position)
            .filter_by(
                election_id=election_id,
                voter_id=student_id,
            )
            .distinct()
            .all()
        )
    }

    # Mark voting as completed only when all positions are voted.
    eligibility.has_voted = (
        bool(positions)
        and positions.issubset(voted_positions)
    )


# =========================================================
# DISPLAY AVAILABLE ELECTIONS
# =========================================================

@voting_bp.route("/", methods=["GET"])
def elections():

    student = get_logged_in_student()

    if student is None:
        flash(
            "Please log in to view elections.",
            "error",
        )
        return redirect(url_for("auth.login"))

    now = datetime.now()

    # Get elections assigned to this student only.
    eligibility_records = VoterEligibility.query.filter_by(
        student_id=student.id
    ).all()

    election_data = []

    for eligibility in eligibility_records:

        election = db.session.get(
            Election,
            eligibility.election_id,
        )

        if election is None:
            continue

        # Hide elections that are not active.
        if election.status != "active":
            continue

        # Determine election status.
        if now < election.start_at:

            election_state = "Upcoming"
            is_voting_open = False
            is_completed = False

        elif election.start_at <= now < election.end_at:

            election_state = "Ongoing"
            is_voting_open = True
            is_completed = False

        else:

            election_state = "Completed"
            is_voting_open = False
            is_completed = True

        # Get candidates for this election.
        candidates = Candidate.query.filter_by(
            election_id=election.id
        ).order_by(
            Candidate.position.asc(),
            Candidate.name.asc(),
        ).all()

        # Get positions for which this student has already voted.
        voted_positions = {
            row[0]
            for row in (
                db.session.query(Ballot.position)
                .filter_by(
                    election_id=election.id,
                    voter_id=student.id,
                )
                .distinct()
                .all()
            )
        }

        election_data.append({

            "election": election,
            "eligibility": eligibility,
            "candidates": candidates,
            "voted_positions": voted_positions,
            "election_state": election_state,
            "is_completed": is_completed,
            "is_voting_open": is_voting_open,

        })

    # Upcoming and ongoing elections appear before completed ones.
    election_data.sort(
        key=lambda item: (
            item["is_completed"],
            item["election"].start_at,
        )
    )

    return render_template(
        "student/voting.html",
        election_data=election_data,
    )


# =========================================================
# CAST ONE VOTE FOR A POSITION
# =========================================================

@voting_bp.route(
    "/<int:election_id>/cast",
    methods=["POST"],
)
def cast_vote(election_id):

    student = get_logged_in_student()

    if student is None:
        flash(
            "Please log in first.",
            "error",
        )
        return redirect(url_for("auth.login"))

    election = db.session.get(
        Election,
        election_id,
    )

    if election is None or election.status != "active":

        flash(
            "This election is not available for voting.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    now = datetime.now()

    # Check voting period.
    if not (election.start_at <= now < election.end_at):

        flash(
            "Voting is not open for this election yet.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    # Check student eligibility.
    eligibility = VoterEligibility.query.filter_by(
        election_id=election.id,
        student_id=student.id,
    ).first()

    if eligibility is None:

        flash(
            "You are not eligible to vote in this election.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    # Get selected position and candidate.
    position = request.form.get(
        "position",
        "",
    ).strip()

    candidate_id = request.form.get(
        "candidate_id",
        type=int,
    )

    if not position or candidate_id is None:

        flash(
            "Please select a position and candidate.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    # Validate candidate.
    candidate = Candidate.query.filter_by(
        id=candidate_id,
        election_id=election.id,
        position=position,
    ).first()

    if candidate is None:

        flash(
            "Invalid candidate selection.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    # Prevent duplicate voting for the same position.
    existing_vote = Ballot.query.filter_by(
        election_id=election.id,
        position=position,
        voter_id=student.id,
    ).first()

    if existing_vote is not None:

        flash(
            f"You have already voted for {position}.",
            "error",
        )
        return redirect(url_for("voting.elections"))

    try:

        ballot = Ballot(
            election_id=election.id,
            candidate_id=candidate.id,
            position=position,
            voter_id=student.id,
        )

        db.session.add(ballot)

        db.session.flush()

        # Update voting completion.
        update_voting_completion(
            election_id=election.id,
            student_id=student.id,
        )

        db.session.commit()

        flash(
            f"Your vote for {position} has been recorded successfully.",
            "success",
        )

    except IntegrityError:

        db.session.rollback()

        flash(
            "A vote for this position may already exist. "
            "Please refresh and check your voting status.",
            "error",
        )

    except Exception:

        db.session.rollback()

        flash(
            "An unexpected error occurred while recording your vote.",
            "error",
        )

        raise

    return redirect(url_for("voting.elections"))