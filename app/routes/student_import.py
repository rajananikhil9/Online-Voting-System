import os
import tempfile

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    abort,
)

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from models import db, Student

from app.services.student_import import (
    import_students_from_excel,
    generate_temporary_password,
    validate_college_email,
)

from app.services.email_service import send_student_credentials


# ==========================================
# STUDENT IMPORT BLUEPRINT
# ==========================================

student_import_bp = Blueprint(
    "student_import",
    __name__,
    url_prefix="/admin/students",
)


# ==========================================
# ADD STUDENT MANUALLY
# ==========================================

@student_import_bp.route("/add", methods=["GET", "POST"])
def add_student():
    """Register one student manually and email credentials."""

    if request.method == "GET":
        return render_template("admin/add_student.html")

    reg_no = request.form.get("reg_no", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    department = request.form.get("department", "").strip()

    # Validate required fields
    if not all([reg_no, name, email, department]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("student_import.add_student"))

    # Validate college email
    if not validate_college_email(email):
        flash(
            "Only official college email addresses are allowed. "
            "Required format: 230101120xxx@centurionuniv.edu.in",
            "error",
        )
        return redirect(url_for("student_import.add_student"))

    try:

        # Check duplicate registration number or email
        existing_student = Student.query.filter(
            db.or_(
                Student.reg_no == reg_no,
                db.func.lower(Student.email) == email,
            )
        ).first()

        if existing_student:
            flash(
                "Registration number or email already exists.",
                "error",
            )
            return redirect(url_for("student_import.add_student"))

        # Generate default password
        temporary_password = generate_temporary_password()

        # Create student
        student = Student(
            reg_no=reg_no,
            name=name,
            email=email,
            department=department,
            password_hash=generate_password_hash(temporary_password),

            # Students are not forced to change their password
            must_change_password=False,

            email_status="pending",
        )

        db.session.add(student)
        db.session.commit()

        current_app.logger.info(
            "Student saved successfully: id=%s, reg_no=%s, database=%s",
            student.id,
            student.reg_no,
            db.engine.url.database,
        )

    except IntegrityError:

        db.session.rollback()

        current_app.logger.exception(
            "Database constraint error registering %s",
            reg_no,
        )

        flash(
            "Registration failed because of a duplicate or database constraint.",
            "error",
        )

        return redirect(url_for("student_import.add_student"))

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Student registration failed for %s",
            reg_no,
        )

        flash(
            "Student could not be saved. Check the VS Code terminal.",
            "error",
        )

        return redirect(url_for("student_import.add_student"))

    # ==========================================
    # SEND STUDENT CREDENTIALS
    # ==========================================

    try:

        send_student_credentials(
            recipient_email=email,
            reg_no=reg_no,
            temporary_password=temporary_password,
        )

        student.email_status = "sent"
        db.session.commit()

        flash(
            "Student registered successfully. "
            "The email server accepted the credentials email.",
            "success",
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Email delivery failed for student %s",
            reg_no,
        )

        try:

            saved_student = Student.query.filter_by(
                reg_no=reg_no
            ).first()

            if saved_student:
                saved_student.email_status = "failed"
                db.session.commit()

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "Failed to update email status for %s",
                reg_no,
            )

        flash(
            "Student was saved, but the email could not be sent. "
            "Check the VS Code terminal.",
            "error",
        )

    return redirect(url_for("student_import.add_student"))


# ==========================================
# IMPORT STUDENTS FROM EXCEL
# ==========================================

@student_import_bp.route("/import", methods=["GET", "POST"])
def import_students():

    # Display Import Students page
    if request.method == "GET":
        return render_template("admin/import_students.html")

    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({
            "error": "Please select an Excel file."
        }), 400

    if not uploaded_file.filename.lower().endswith(".xlsx"):
        return jsonify({
            "error": "Only .xlsx files are supported."
        }), 400

    temp_path = None

    try:

        # Create temporary Excel file
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            delete=False,
        ) as temp_file:

            temp_path = temp_file.name

        uploaded_file.save(temp_path)

        # Import students
        result = import_students_from_excel(temp_path)

        email_results = []

        # Send credentials to imported students
        for item in result.get("students", []):

            try:

                send_student_credentials(
                    recipient_email=item["email"],
                    reg_no=item["reg_no"],
                    temporary_password=item["temporary_password"],
                )

                student = db.session.get(
                    Student,
                    item["student_id"],
                )

                if student:
                    student.email_status = "sent"

                email_results.append({
                    "reg_no": item["reg_no"],
                    "status": "sent",
                })

            except Exception:

                current_app.logger.exception(
                    "Email delivery failed for student %s",
                    item["reg_no"],
                )

                student = db.session.get(
                    Student,
                    item["student_id"],
                )

                if student:
                    student.email_status = "failed"

                email_results.append({
                    "reg_no": item["reg_no"],
                    "status": "failed",
                })

        db.session.commit()

        return jsonify({
            "imported_count": result["imported_count"],
            "error_count": result["error_count"],
            "errors": result["errors"],
            "email_results": email_results,
        }), 200

    except ValueError as error:

        db.session.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Student Excel import failed."
        )

        return jsonify({
            "error": "Import failed. Check the VS Code terminal."
        }), 500

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# ==========================================
# DELETE STUDENT
# ==========================================

@student_import_bp.route(
    "/delete/<int:student_id>",
    methods=["POST"]
)
def delete_student(student_id):
    """Delete a student only if they have not voted."""

    # Verify administrator login
    if not session.get("admin_id"):
        abort(403)

    student = db.session.get(Student, student_id)

    if student is None:
        flash("Student not found.", "error")
        return redirect(
            url_for("admin_dashboard.student_list")
        )

    reg_no = student.reg_no

    try:
        # --------------------------------------
        # 1. CHECK WHETHER STUDENT HAS VOTED
        # --------------------------------------

        voted_record = db.session.execute(
            text("""
                SELECT 1
                FROM voter_eligibility
                WHERE student_id = :student_id
                AND (has_voted <> 0 OR has_voted IS NULL)
                LIMIT 1
            """),
            {"student_id": student_id}
        ).first()

        if voted_record:
            flash(
                "This student has already voted. "
                "Deletion is not allowed.",
                "error"
            )

            return redirect(
                url_for("admin_dashboard.student_list")
            )

        # --------------------------------------
        # 2. CHECK BALLOT RECORDS
        # --------------------------------------

        ballot_record = db.session.execute(
            text("""
                SELECT 1
                FROM ballots
                WHERE voter_id = :student_id
                LIMIT 1
            """),
            {"student_id": student_id}
        ).first()

        if ballot_record:
            flash(
                "This student has ballot records. "
                "Deletion is not allowed.",
                "error"
            )

            return redirect(
                url_for("admin_dashboard.student_list")
            )

        # --------------------------------------
        # 3. DELETE ELIGIBILITY RECORDS
        # --------------------------------------

        db.session.execute(
            text("""
                DELETE FROM voter_eligibility
                WHERE student_id = :student_id
                AND has_voted = 0
            """),
            {"student_id": student_id}
        )

        # --------------------------------------
        # 4. DELETE STUDENT
        # --------------------------------------

        db.session.delete(student)

        db.session.commit()

        current_app.logger.info(
            "Student deleted successfully: ID=%s, Reg No=%s",
            student_id,
            reg_no
        )

        flash(
            "Student and their unused election eligibility "
            "records deleted successfully.",
            "success"
        )

    except IntegrityError:

        db.session.rollback()

        current_app.logger.exception(
            "Foreign key constraint prevented deletion of student ID %s",
            student_id
        )

        flash(
            "Student cannot be deleted because other related records exist.",
            "error"
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete student ID %s",
            student_id
        )

        flash(
            "Unable to delete student. Check the VS Code terminal.",
            "error"
        )

    return redirect(
        url_for("admin_dashboard.student_list")
    )