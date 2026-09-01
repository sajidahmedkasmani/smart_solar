from functools import wraps
from flask import session, redirect, url_for, flash, request
from app.roles import dashboard_for


def session_roles():
    roles = session.get('roles') or []
    if isinstance(roles, str):
        roles = [roles]
    legacy = session.get('role')
    if legacy and legacy not in roles:
        roles = list(roles) + [legacy]
    return roles


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Require one of the user's explicitly assigned roles; admin is not granted automatically to others."""
    allowed = set(roles)
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get('user_id'):
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login', next=request.path))
            current = set(session_roles())
            if 'admin' not in current and not current.intersection(allowed):
                primary = session.get('role') or 'customer'
                flash('You do not have permission to view that page.', 'danger')
                return redirect(url_for(dashboard_for(primary)))
            return f(*args, **kwargs)
        return wrapper
    return decorator
