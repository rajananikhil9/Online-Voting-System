from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, Election, Candidate

elections_bp = Blueprint(
    "elections",
    __name__,
    url_prefix="/admin/elections"
)


@elections_bp.route("/", methods=["GET"])
def get_elections():
    elections = Election.query.order_by(Election.id.desc()).all()

    return jsonify([
        {
            "id": election.id,
            "title": election.title,
            "description": election.description,
            "start_at": (
                election.start_at.isoformat()
                if election.start_at else None
            ),
            "end_at": (
                election.end_at.isoformat()
                if election.end_at else None
            ),
            "status": election.status
        }
        for election in elections
    ])


@elections_bp.route("/", methods=["POST"])
def create_election():
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()

    if not title:
        return jsonify({"error": "Election title is required"}), 400

    try:
        start_at = datetime.fromisoformat(data["start_at"])
        end_at = datetime.fromisoformat(data["end_at"])
    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Provide valid start_at and end_at dates"
        }), 400

    if end_at <= start_at:
        return jsonify({
            "error": "End time must be after start time"
        }), 400

    election = Election(
        title=title,
        description=description,
        start_at=start_at,
        end_at=end_at,
        status="draft"
    )

    db.session.add(election)
    db.session.commit()

    return jsonify({
        "message": "Election created successfully",
        "election_id": election.id,
        "title": election.title,
        "status": election.status
    }), 201


@elections_bp.route("/<int:election_id>/candidates", methods=["POST"])
def add_candidate(election_id):
    election = db.session.get(Election, election_id)

    if election is None:
        return jsonify({"error": "Election not found"}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    manifesto = data.get("manifesto", "").strip()

    if not name:
        return jsonify({"error": "Candidate name is required"}), 400

    candidate = Candidate(
        election_id=election.id,
        name=name,
        manifesto=manifesto
    )

    db.session.add(candidate)
    db.session.commit()

    return jsonify({
        "message": "Candidate added successfully",
        "candidate_id": candidate.id,
        "election_id": election.id,
        "name": candidate.name
    }), 201


@elections_bp.route("/<int:election_id>/candidates", methods=["GET"])
def get_candidates(election_id):
    election = db.session.get(Election, election_id)

    if election is None:
        return jsonify({"error": "Election not found"}), 404

    candidates = Candidate.query.filter_by(
        election_id=election.id
    ).all()

    return jsonify([
        {
            "id": candidate.id,
            "name": candidate.name,
            "manifesto": candidate.manifesto
        }
        for candidate in candidates
    ])
