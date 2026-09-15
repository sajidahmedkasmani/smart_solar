from flask import current_app
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


def send_verification_email(to_email, full_name, verify_url):
    """Send the 'verify your account' email with a one-click verify button.

    Returns True if the send call completed without raising, False otherwise.
    The caller decides how to react to a False result (e.g. still show the
    'check your email' screen, but log/flash that sending may have failed).
    """
    app_name = current_app.config.get('APP_NAME', 'SolarEase')
    subject = f"Verify your {app_name} account"
    body_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; color:#142033;">
      <div style="text-align:center; padding: 24px 0 8px;">
        <span style="font-weight:700; font-size:20px; color:#142033;">{app_name}</span>
      </div>
      <div style="background:#ffffff; border:1px solid #E4E0D3; border-radius:16px; padding:28px;">
        <h2 style="margin-top:0; font-size:20px;">Hi {full_name or 'there'},</h2>
        <p style="font-size:14px; line-height:1.6; color:#4A5670;">
          Thanks for signing up for {app_name}. Please confirm this is your email address
          by clicking the button below.
        </p>
        <div style="text-align:center; margin: 28px 0;">
          <a href="{verify_url}"
             style="background:#F0A93B; color:#142033; text-decoration:none; font-weight:700;
                    padding:12px 28px; border-radius:10px; display:inline-block; font-size:14px;">
            Verify My Account
          </a>
        </div>
        <p style="font-size:12px; color:#4A5670; line-height:1.6;">
          This link expires in 24 hours. If the button doesn't work, copy and paste this URL
          into your browser:<br>
          <a href="{verify_url}" style="color:#1D6E8C; word-break:break-all;">{verify_url}</a>
        </p>
        <p style="font-size:12px; color:#94a3b8; margin-top:20px;">
          If you didn't create this account, you can safely ignore this email.
        </p>
      </div>
    </div>
    """
    try:
        msg = Message(subject=subject, recipients=[to_email], html=body_html)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False