import re

from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from models import db, Student


# ==========================================
# COLLEGE EMAIL VALIDATION
# ==========================================

COLLEGE_EMAIL_PATTERN = (
    r"230101120\d{3}@centurionuniv\.edu\.in"
)


def validate_college_email(email):
    """Validate the official college email format."""

    email = (email or "").strip().lower()

    return bool(re.fullmatch(COLLEGE_EMAIL_PATTERN, email))


# ==========================================
# DEFAULT PASSWORD
# ==========================================

DEFAULT_TEMPORARY_PASSWORD = "stud@1234567"


def generate_temporary_password(length=12):
    """Return the default student password."""

    return DEFAULT_TEMPORARY_PASSWORD


# ==========================================
# EXCEL STUDENT IMPORT
# ==========================================

def import_students_from_excel(file_path):
    """Import students from an Excel workbook."""

    workbook = load_workbook(
        filename=file_path,
        read_only=True,
        data_only=True
    )

    imported = []
    errors = []

    seen_reg_numbers = set()
    seen_emails = set()

    try:
        worksheet = workbook.active
        rows = worksheet.iter_rows(values_only=True)

        headers = next(rows, None)

        if not headers:
            raise ValueError("The Excel file is empty.")

        headers = [
            str(value).strip().lower() if value is not None else ""
            for value in headers
        ]

        required = {
            "reg_no",
            "name",
            "email",
            "department"
        }

        if not required.issubset(set(headers)):
            raise ValueError(
                "Excel must contain: reg_no, name, email, department."
            )

        indexes = {
            column: headers.index(column)
            for column in required
        }

        for row_number, row in enumerate(rows, start=2):

            try:

                def get_value(column):
                    index = indexes[column]
                    return row[index] if index < len(row) else None

                reg_no = str(get_value("reg_no") or "").strip()
                name = str(get_value("name") or "").strip()
                email = str(get_value("email") or "").strip().lower()
                department = str(get_value("department") or "").strip()

                # Validate required fields
                if not all([reg_no, name, email, department]):
                    raise ValueError(
                        "Registration number, name, email, "
                        "and department are required."
                    )

                # Validate college email
                if not validate_college_email(email):
                    raise ValueError(
                        "Invalid college email. Required format: "
                        "230101120xxx@centurionuniv.edu.in"
                    )

                # Check duplicate registration numbers in Excel
                if reg_no in seen_reg_numbers:
                    raise ValueError(
                        "Duplicate registration number in Excel."
                    )

                # Check duplicate emails in Excel
                if email in seen_emails:
                    raise ValueError(
                        "Duplicate college email address in Excel."
                    )

                # Check existing registration number
                if Student.query.filter_by(reg_no=reg_no).first():
                    raise ValueError(
                        "Registration number already exists."
                    )

                # Check existing email
                if Student.query.filter_by(email=email).first():
                    raise ValueError(
                        "College email address already exists."
                    )

                seen_reg_numbers.add(reg_no)
                seen_emails.add(email)

                # Set default password
                password = generate_temporary_password()

                # Create student
                student = Student(
                    reg_no=reg_no,
                    name=name,
                    email=email,
                    department=department,

                    password_hash=generate_password_hash(password),

                    must_change_password=False,
                    email_status="pending"
                )

                db.session.add(student)
                db.session.flush()

                imported.append({
                    "student_id": student.id,
                    "reg_no": reg_no,
                    "email": email,
                    "temporary_password": password
                })

            except (ValueError, TypeError, IndexError) as error:

                errors.append({
                    "row": row_number,
                    "error": str(error)
                })

        db.session.commit()

        return {
            "imported_count": len(imported),
            "error_count": len(errors),
            "students": imported,
            "errors": errors
        }

    except Exception:
        db.session.rollback()
        raise

    finally:
        workbook.close()