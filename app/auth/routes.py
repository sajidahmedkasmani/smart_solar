from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from app import db
from app.models import User, Customer, UserRole
from app.roles import dashboard_for, label_for, get_user_roles, sync_user_roles, CUSTOMER, STAFF_ROLES
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.helpers import unique_username
from app.utils.email import send_verification_email
from google.oauth2 import id_token
from google.auth.transport import requests
import secrets


auth_bp = Blueprint('auth', __name__)
ADMIN_EMAIL = 'admin@solarease.pk'

VERIFICATION_TOKEN_TTL_HOURS = 24


def _issue_verification_token(customer):
    """Generate a fresh verification token/expiry for a customer and persist it."""
    token = secrets.token_hex(16)
    customer.verification_token = token
    customer.verification_token_expires_at = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_TTL_HOURS)
    db.session.commit()
    return token


def _send_verification_email(customer):
    token = _issue_verification_token(customer)
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    return send_verification_email(customer.email, customer.full_name, verify_url)

# GOOGLE_CLIENT_ID = "864558198474-tbbe731r46thscmifrc8kt0gl9bpkq1f.apps.googleusercontent.com"
# GOOGLE_CLIENT_ID = current_app.config['GOOGLE_CLIENT_ID']


def _is_password_hash(value):
    return value.startswith(('scrypt:', 'pbkdf2:', 'argon2:'))


def _start_session(user):
    roles = get_user_roles(user)
    session['user_id'] = user.id
    session['user_name'] = user.full_name
    session['roles'] = roles
    session['role'] = next((r for r in roles if r == 'admin'), roles[0] if roles else CUSTOMER)
    return roles


def _login_user(user, staff=False):
    roles = get_user_roles(user)
    if staff:
        staff_roles = [r for r in roles if r in STAFF_ROLES]
        if not staff_roles:
            return False
    else:
        if roles and not any(r == CUSTOMER for r in roles):
            return False
    if not user.assigned_roles:
        sync_user_roles(user, roles or [CUSTOMER])
        db.session.commit()
        roles = get_user_roles(user)
    _start_session(user)
    return True


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # User ki jagah Customer table se record fetch karein
        customer = Customer.query.filter_by(email=email).first()

        valid = customer and (
            check_password_hash(customer.password, password) 
            if customer.password.startswith(('scrypt:', 'pbkdf2:', 'argon2:')) 
            else customer.password == password
        )

        if not valid:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))

        if not customer.is_email_verified:
            flash('Please verify your email address before logging in. We\'ve sent you a verification link.', 'warning')
            return redirect(url_for('auth.verify_notice', email=customer.email))

        # Session me customer ki details store karein
        session['user_id'] = customer.id
        session['user_name'] = customer.full_name
        session['role'] = 'customer'  # Customer table ke liye role fixed/default

        return redirect(url_for('customers.dashboard'))

    return render_template('landing_page/auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if Customer.query.filter_by(email=email).first(): 
            flash('Email already registered.', 'warning')
            return redirect(url_for('auth.register'))

        customer = Customer(
            full_name=full_name,
            email=email,
            password=generate_password_hash(password),
            is_email_verified=False,
        )
        db.session.add(customer)
        db.session.commit()

        _send_verification_email(customer)

        flash('Registration successful! Please check your email to verify your account.', 'success')
        return redirect(url_for('auth.verify_notice', email=customer.email))

    return render_template('landing_page/auth/register.html')


@auth_bp.route('/verify-notice')
def verify_notice():
    """Shown right after registration: 'check your email' screen."""
    email = request.args.get('email', '')
    return render_template('landing_page/auth/verify_notice.html', email=email)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    customer = Customer.query.filter_by(verification_token=token).first()

    if not customer:
        flash('This verification link is invalid or has already been used.', 'danger')
        return redirect(url_for('auth.login'))

    if customer.verification_token_expires_at and customer.verification_token_expires_at < datetime.utcnow():
        flash('This verification link has expired. Please request a new one.', 'warning')
        return redirect(url_for('auth.verify_notice', email=customer.email))

    customer.is_email_verified = True
    customer.verification_token = None
    customer.verification_token_expires_at = None
    db.session.commit()

    # Auto-login the customer now that their email is confirmed
    session['user_id'] = customer.id
    session['user_name'] = customer.full_name
    session['role'] = 'customer'

    flash('Your account is successfully verified!', 'success')
    return redirect(url_for('customers.dashboard'))


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email', '').strip().lower()
    customer = Customer.query.filter_by(email=email).first()

    # Always show the same generic message so we don't leak whether an email exists.
    if customer and not customer.is_email_verified:
        _send_verification_email(customer)

    flash('If that email is registered and unverified, a new verification link has been sent.', 'info')
    return redirect(url_for('auth.verify_notice', email=email))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/google-login', methods=['POST'])
def google_callback():
    from app import db
    from app.models import Customer

    data = request.get_json()
    token = data.get('token')

    GOOGLE_CLIENT_ID = current_app.config['GOOGLE_CLIENT_ID']

    try:
        id_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        email = id_info.get('email').lower()
        full_name = id_info.get('name')

        # Check agar customer already DB me hai
        customer = Customer.query.filter_by(email=email).first()

        # Agar nahi hai tou AUTO-REGISTER karein
        if not customer:
            customer = Customer(
                full_name=full_name,
                email=email,
                password=generate_password_hash(secrets.token_hex(16)),
                is_email_verified=True,  # Google already verified this email address
            )
            db.session.add(customer)
            db.session.commit()
        elif not customer.is_email_verified:
            # Existing form-registered account signing in with the same, Google-verified email
            customer.is_email_verified = True
            customer.verification_token = None
            customer.verification_token_expires_at = None
            db.session.commit()

        # Session me LOGIN karwayein
        session['user_id'] = customer.id
        session['user_name'] = customer.full_name
        session['role'] = 'customer'

        return jsonify({'success': True, 'redirect': url_for('customers.dashboard')})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400