from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)

from werkzeug.security import check_password_hash

from models import Admin


admin_auth_bp = Blueprint(
    "admin_auth",
    __name__,
    url_prefix="/admin",
)


# ==========================================
# ADMIN LOGIN
# ==========================================
@admin_auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if session.get("admin_id"):
        return redirect(
            url_for("admin_dashboard.dashboard")
        )

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(
            username=username
        ).first()

        if admin and check_password_hash(
            admin.password_hash,
            password,
        ):

            # Remove only previous admin session data.
            # Preserve student session data.
            session.pop("admin_id", None)
            session.pop("admin_username", None)

            session["admin_id"] = admin.id
            session["admin_username"] = admin.username

            flash(
                "Admin login successful.",
                "success",
            )

            return redirect(
                url_for("admin_dashboard.dashboard")
            )

        flash(
            "Invalid username or password.",
            "error",
        )

    return render_template("admin/login.html")


# ==========================================
# ADMIN LOGOUT
# ==========================================
@admin_auth_bp.route("/logout", methods=["POST"])
def logout():

    if not session.get("admin_id"):
        return redirect(
            url_for("admin_auth.login")
        )

    # Remove only admin session data.
    # Preserve student session data.
    session.pop("admin_id", None)
    session.pop("admin_username", None)

    flash(
        "Admin logged out successfully.",
        "success",
    )

    return redirect(
        url_for("admin_auth.login")
    )