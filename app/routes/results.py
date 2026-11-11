from datetime import datetime
from collections import defaultdict
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    request
)

from sqlalchemy import func

from models import (
    db,
    Student,
    Election,
    Candidate,
    Ballot,
    VoterEligibility
)


results_bp = Blueprint(
    "results",
    __name__,
    url_prefix="/results"
)


# =====================================================
# ADMIN AUTHENTICATION DECORATOR
# =====================================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "admin_id" not in session:
            return redirect(url_for("admin_auth.login"))

        return f(*args, **kwargs)

    return decorated_function


# =====================================================
# ADMIN RESULTS
# =====================================================

@results_bp.route("/admin")
@admin_required
def admin_results():

    # Get all elections
    elections = Election.query.order_by(
        Election.id.desc()
    ).all()

    election_id = request.args.get(
        "election_id",
        type=int
    )

    selected_election = None

    results = {}

    total_voters = 0
    total_votes = 0
    voters_participated = 0
    participation = 0

    # Get selected election
    if election_id:

        selected_election = db.session.get(
            Election,
            election_id
        )

    if selected_election:

        # =============================================
        # TOTAL ELIGIBLE VOTERS
        # =============================================

        total_voters = VoterEligibility.query.filter_by(
            election_id=selected_election.id
        ).count()

        # =============================================
        # CANDIDATE-WISE VOTE COUNT
        # =============================================

        rows = (
            db.session.query(
                Candidate.id,
                Candidate.name,
                Candidate.position,
                func.count(Ballot.id).label("votes")
            )
            .outerjoin(
                Ballot,
                (Ballot.candidate_id == Candidate.id)
                & (Ballot.election_id == selected_election.id)
                & (Ballot.position == Candidate.position)
            )
            .filter(
                Candidate.election_id == selected_election.id
            )
            .group_by(
                Candidate.id,
                Candidate.name,
                Candidate.position
            )
            .order_by(
                Candidate.position.asc(),
                func.count(Ballot.id).desc(),
                Candidate.name.asc()
            )
            .all()
        )

        # =============================================
        # GROUP CANDIDATES BY POSITION
        # =============================================

        grouped_results = defaultdict(list)

        for row in rows:

            grouped_results[row.position].append({

                "name": row.name,

                "votes": row.votes,

                "percentage": 0,

                "is_winner": False

            })

        # =============================================
        # CALCULATE RESULTS AND WINNERS
        # =============================================

        for position, candidates in grouped_results.items():

            position_total = sum(
                candidate["votes"]
                for candidate in candidates
            )

            total_votes += position_total

            # Calculate candidate vote percentages
            for candidate in candidates:

                candidate["percentage"] = (

                    round(
                        candidate["votes"] * 100 / position_total,
                        2
                    )

                    if position_total > 0 else 0

                )

            # Find highest votes
            highest_votes = max(
                candidate["votes"]
                for candidate in candidates
            )

            leaders = [

                candidate

                for candidate in candidates

                if candidate["votes"] == highest_votes

            ]

            # Declare winner only if there is a unique leader
            if highest_votes > 0 and len(leaders) == 1:

                leaders[0]["is_winner"] = True

            results[position] = candidates

        # =============================================
        # VOTER PARTICIPATION
        # =============================================

        voters_participated = (

            db.session.query(
                func.count(func.distinct(Ballot.voter_id))
            )
            .filter(
                Ballot.election_id == selected_election.id
            )
            .scalar()

        ) or 0

        participation = (

            round(
                voters_participated * 100 / total_voters,
                2
            )

            if total_voters > 0 else 0

        )

    return render_template(

        "admin/results.html",

        elections=elections,

        selected_election=selected_election,

        results=results,

        total_voters=total_voters,

        total_votes=total_votes,

        voters_participated=voters_participated,

        participation=participation

    )


# =====================================================
# STUDENT ELECTION RESULTS
# =====================================================

@results_bp.route("/<int:election_id>")
def election_results(election_id):

    # Student login check
    if "student_id" not in session:

        return redirect(
            url_for("auth.login")
        )

    student = db.session.get(
        Student,
        session["student_id"]
    )

    if student is None:
        
       session.pop("student_id", None)
       session.pop("reg_no", None)

       return redirect(
          url_for("auth.login")
        )

    # Password change check
    if student.must_change_password:

        return redirect(
            url_for("auth.change_password")
        )

    # Get election
    election = db.session.get(
        Election,
        election_id
    )

    if election is None:

        flash(
            "Election not found.",
            "error"
        )

        return redirect(
            url_for("voting.elections")
        )

    # Results available only after election ends
    if datetime.now() < election.end_at:

        flash(
            "Results will be available after the election ends.",
            "error"
        )

        return redirect(
            url_for("voting.elections")
        )

    # =============================================
    # GET CANDIDATE VOTES
    # =============================================

    rows = (

        db.session.query(

            Candidate.id.label("candidate_id"),

            Candidate.name.label("candidate_name"),

            Candidate.position.label("position"),

            func.count(Ballot.id).label("vote_count")

        )

        .outerjoin(

            Ballot,

            (Ballot.candidate_id == Candidate.id)
            & (Ballot.election_id == election.id)
            & (Ballot.position == Candidate.position)

        )

        .filter(
            Candidate.election_id == election.id
        )

        .group_by(
            Candidate.id,
            Candidate.name,
            Candidate.position
        )

        .order_by(
            Candidate.position.asc(),
            func.count(Ballot.id).desc(),
            Candidate.name.asc()
        )

        .all()

    )

    # =============================================
    # GROUP BY POSITION
    # =============================================

    positions = defaultdict(list)

    for row in rows:

        positions[row.position].append({

            "candidate_id": row.candidate_id,

            "candidate_name": row.candidate_name,

            "vote_count": row.vote_count,

            "percentage": 0

        })

    position_results = []

    total_votes = 0

    # =============================================
    # CALCULATE WINNERS AND TIES
    # =============================================

    for position_name, candidates in positions.items():

        position_total = sum(

            candidate["vote_count"]

            for candidate in candidates

        )

        total_votes += position_total

        # Calculate percentages
        for candidate in candidates:

            candidate["percentage"] = (

                round(
                    candidate["vote_count"] * 100 / position_total,
                    2
                )

                if position_total > 0 else 0

            )

        highest_votes = max(

            candidate["vote_count"]

            for candidate in candidates

        )

        leaders = [

            candidate

            for candidate in candidates

            if candidate["vote_count"] == highest_votes

        ]

        winner = (

            leaders[0]

            if highest_votes > 0 and len(leaders) == 1

            else None

        )

        tied_candidates = (

            leaders

            if highest_votes > 0 and len(leaders) > 1

            else []

        )

        position_results.append({

            "position": position_name,

            "candidates": candidates,

            "total_votes": position_total,

            "winner": winner,

            "tied_candidates": tied_candidates

        })

    # =============================================
    # DISPLAY STUDENT RESULTS
    # =============================================

    return render_template(

        "elections/election_results.html",

        election=election,

        position_results=position_results,

        total_votes=total_votes

    )