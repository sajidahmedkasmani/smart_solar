from flask_mail import Message
from app import mail # Ensure Flask-Mail initialized in app/__init__.py

def send_survey_email(to_email, subject, body_html):
    try:
        msg = Message(
            subject=subject,
            recipients=[to_email],
            html=body_html
        )
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")