from functools import wraps
from flask import session, redirect, url_for, flash, request
from app.roles import dashboard_for
# app/auth/decorators.py mein
from flask_login import current_user
from flask import redirect, url_for, flash
from functools import wraps


def session_roles():
    roles = session.get('roles') or []
    if isinstance(roles, str):
        roles = [roles]
    legacy = session.get('role')
    if legacy and legacy not in roles:
        roles = list(roles) + [legacy]
    return roles


# def login_required(f):
#     @wraps(f)
#     def wrapper(*args, **kwargs):
#         if not session.get('user_id'):
#             flash('Please log in to continue.', 'warning')
#             return redirect(url_for('auth.login', next=request.path))
#         return f(*args, **kwargs)
#     return wrapper


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 1. Check karein ke user logged in hai ya nahi
        if not current_user.is_authenticated:
            flash("Pehle login karein.", "warning")
            return redirect(url_for('auth.login'))
            
        # 2. Check karein ke role customer hai ya nahi
        if current_user.role != 'customer':
            flash("Aapko is page ka access nahi hai.", "danger")
            return redirect(url_for('main.index'))
            
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
