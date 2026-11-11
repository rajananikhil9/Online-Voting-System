import os
import smtplib

from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def get_email_config():
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    sender = os.getenv("MAIL_DEFAULT_SENDER") or username

    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"

    if not all([username, password, sender]):
        raise RuntimeError(
            "Email configuration is incomplete. "
            "Check MAIL_USERNAME, MAIL_PASSWORD and MAIL_DEFAULT_SENDER."
        )

    # Debug information (never print passwords)
    print("\n========== EMAIL CONFIG DEBUG ==========")
    print("SMTP Server:", repr(mail_server))
    print("SMTP Port:", mail_port)
    print("TLS Enabled:", use_tls)
    print("Username Configured:", bool(username))
    print("Password Configured:", bool(password))
    print("========================================\n")

    return username, password, sender, mail_server, mail_port, use_tls


def send_email(message):

    username, password, sender, mail_server, mail_port, use_tls = (
        get_email_config()
    )

    message["From"] = sender

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            server.ehlo()

            if use_tls:
                server.starttls()
                server.ehlo()

            server.login(username, password)
            server.send_message(message)

        print("Email sent successfully to:", message["To"])
        return True

    except (smtplib.SMTPException, OSError) as error:
        print("Email delivery failed:", str(error))

        raise RuntimeError(
            f"Could not send email to {message['To']}: {error}"
        ) from error


# =====================================================
# SEND STUDENT LOGIN CREDENTIALS
# =====================================================

def send_student_credentials(recipient_email, reg_no, temporary_password):

    message = EmailMessage()
    message["Subject"] = "Your College Voting System Login"
    message["To"] = recipient_email

    message.set_content(f"""Hello,

Your College Student Voting System account has been created.

Registration Number: {reg_no}
Temporary Password: {temporary_password}

Login page: http://127.0.0.1:5000/auth/login

Please log in and change your temporary password immediately.

If you did not expect this email, contact your college administrator.
""")

    return send_email(message)


# =====================================================
# SEND STUDENT OTP
# =====================================================

def send_student_otp(recipient_email, otp):

    message = EmailMessage()
    message["Subject"] = "College Voting System - Email Verification"
    message["To"] = recipient_email

    message.set_content(f"""Hello,

Your OTP for College Student Voting System verification is:

{otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.

If you did not request this verification, please ignore this email.

Regards,
College Election Administration
""")

    return send_email(message)