import uuid

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy


# =========================================================
# INITIALIZE SQLALCHEMY
# =========================================================

db = SQLAlchemy()


# =========================================================
# ADMIN MODEL
# =========================================================

class Admin(db.Model):

    __tablename__ = "admins"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# STUDENT MODEL
# =========================================================

class Student(db.Model):

    __tablename__ = "students"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    reg_no = db.Column(
        db.String(40),
        unique=True,
        nullable=False
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=True
    )

    mobile = db.Column(
        db.String(20),
        nullable=True
    )

    department = db.Column(
        db.String(100),
        nullable=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    must_change_password = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    email_status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


# =========================================================
# ELECTION MODEL
# =========================================================

class Election(db.Model):
    __tablename__ = "elections"

    id = db.Column(db.Integer, primary_key=True)

    public_id = db.Column(
        db.String(11),
        unique=True,
        nullable=False,
        default=lambda: "EL-" + uuid.uuid4().hex[:8].upper()
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="draft")

# =========================================================
# CANDIDATE MODEL
# =========================================================

class Candidate(db.Model):

    __tablename__ = "candidates"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("elections.id"),
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    position = db.Column(
        db.String(100),
        nullable=False,
        default="President"
    )

    manifesto = db.Column(
        db.Text,
        nullable=True
    )


# =========================================================
# VOTER ELIGIBILITY MODEL
# =========================================================

class VoterEligibility(db.Model):

    __tablename__ = "voter_eligibility"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("elections.id"),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    has_voted = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    __table_args__ = (

        db.UniqueConstraint(
            "election_id",
            "student_id",
            name="uq_election_student"
        ),

    )


# =========================================================
# BALLOT MODEL
# =========================================================

class Ballot(db.Model):

    __tablename__ = "ballots"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("elections.id"),
        nullable=False
    )

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    position = db.Column(
        db.String(100),
        nullable=False
    )

    voter_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    __table_args__ = (

        db.UniqueConstraint(
            "election_id",
            "position",
            "voter_id",
            name="uq_ballot_voter_position"
        ),

    )


# =========================================================
# CANDIDATE APPLICATION MODEL
# =========================================================

class CandidateApplication(db.Model):

    __tablename__ = "candidate_applications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("elections.id"),
        nullable=False
    )

    position = db.Column(
        db.String(100),
        nullable=False
    )

    manifesto = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    applied_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey("admins.id"),
        nullable=True
    )

    __table_args__ = (

        db.UniqueConstraint(
            "election_id",
            "student_id",
            "position",
            name="uq_candidate_application"
        ),

    )


# =========================================================
# PREDEFINED ELECTION POSITIONS
# =========================================================

PREDEFINED_POSITIONS = [

    "President",
    "Vice President",
    "General Secretary",
    "Secretary",
    "Joint Secretary",
    "Treasurer",
    "Sports Secretary"

]


# =========================================================
# ELECTION POSITIONS MODEL
# =========================================================

class ElectionPosition(db.Model):

    __tablename__ = "election_positions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    election_id = db.Column(
        db.Integer,
        db.ForeignKey("elections.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    __table_args__ = (

        db.UniqueConstraint(
            "election_id",
            "name",
            name="uq_election_position"
        ),

    )

    election = db.relationship(
        "Election",
        backref=db.backref(
            "available_positions",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )