from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Customer, SolarPackage, SystemType, UserRole, StaffRoleRequest, Survey, Quotation, Installation, Inventory, MaintenanceRequest
from app.auth.decorators import role_required
from app.roles import ROLES, STAFF_ROLES, label_for, get_user_roles, sync_user_roles, dashboard_for
from werkzeug.security import generate_password_hash, check_password_hash

admin_bp = Blueprint('admin', __name__)
ADMIN_EMAIL = 'admin@solarease.pk'


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Private staff/admin login. There is intentionally no registration here."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        valid = user and (check_password_hash(user.password, password) if user.password.startswith(('scrypt:', 'pbkdf2:', 'argon2:')) else user.password == password)
        roles = get_user_roles(user) if valid else []
        staff_roles = [r for r in roles if r in STAFF_ROLES]
        if not valid or not staff_roles:
            flash('Invalid staff email/password or this account has no Administrator-assigned staff role.', 'danger')
            return redirect(url_for('admin.login'))
        session['user_id'] = user.id
        session['user_name'] = user.full_name
        session['roles'] = roles
        session['role'] = 'admin' if 'admin' in roles else roles[0]
        flash(f'Welcome back, {user.full_name}.', 'success')
        return redirect(url_for(dashboard_for(session['role'])))
    return render_template('admin/auth/staff_login.html')


@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    return render_template(
        'admin/admin_dashboard.html',
        total_users=User.query.filter(User.role != 'customer').count(),
        total_customers=Customer.query.count(),
        total_surveys=Survey.query.count(),
        total_quotations=Quotation.query.count(),
        total_projects=Installation.query.count(),
        surveys=Survey.query.order_by(Survey.id.desc()).all(),
        inventory=Inventory.query.all(),
        complaints_open=MaintenanceRequest.query.filter(MaintenanceRequest.status != 'Resolved').count(),
    )


@admin_bp.route('/users')
@role_required('admin')
def users():
    # Admin's Users table is a staff-access table. Customer profiles live separately.
    staff_users = [u for u in User.query.order_by(User.id.desc()).all() if set(get_user_roles(u)).intersection(STAFF_ROLES)]
    return render_template(
        'admin_users.html',
        users=staff_users,
        roles=STAFF_ROLES,
        staff_roles=STAFF_ROLES,
        label_for=label_for,
        user_roles={u.id: get_user_roles(u) for u in staff_users},
    )


@admin_bp.route('/users/create', methods=['POST'])
@role_required('admin')
def create_staff():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    selected = [r for r in request.form.getlist('roles') if r in STAFF_ROLES]
    if not full_name or not email or not password or not selected:
        flash('Name, email, password and at least one staff role are required.', 'warning')
        return redirect(url_for('admin.users'))
    if User.query.filter_by(email=email).first():
        flash('That email already has an account. Use the Access dropdown to change its roles.', 'warning')
        return redirect(url_for('admin.users'))
    user = User(full_name=full_name, username=email.split('@')[0][:70], email=email,
                password=generate_password_hash(password), role=selected[0])
    db.session.add(user)
    db.session.flush()
    sync_user_roles(user, selected)
    db.session.commit()
    flash(f'Staff account created for {email} with {len(selected)} role(s).', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/assign', methods=['POST'])
@role_required('admin')
def request_role():
    # Direct Admin-controlled multi-role assignment; legacy endpoint retained for existing links.
    email = request.form.get('email', '').strip().lower()
    selected = [r for r in request.form.getlist('roles') if r in STAFF_ROLES]
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No account exists for that email. Create the staff account from this Admin screen.', 'warning')
        return redirect(url_for('admin.users'))
    if user.email == ADMIN_EMAIL:
        flash('The Administrator account cannot be changed.', 'danger')
        return redirect(url_for('admin.users'))
    sync_user_roles(user, selected or ['customer'])
    db.session.commit()
    flash(f'Access updated for {email}: {", ".join(label_for(r) for r in get_user_roles(user))}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/role/<int:user_id>', methods=['POST'])
@role_required('admin')
def update_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.email == ADMIN_EMAIL:
        flash('The Administrator account cannot be changed.', 'danger')
        return redirect(url_for('admin.users'))
    selected = [r for r in request.form.getlist('roles') if r in STAFF_ROLES]
    if not selected:
        flash('Select at least one staff role.', 'warning')
        return redirect(url_for('admin.users'))
    sync_user_roles(user, selected)
    db.session.commit()
    flash(f'Access updated for {user.email}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/packages')
@role_required('admin')
def packages():
    # Admin's Users table is a staff-access table. Customer profiles live separately.
    packages = [pkg for pkg in SolarPackage.query.all()]
    return render_template(
        'admin/admin_packages.html',
        packages=packages
    )



# 1. Admin Page: List & Add System Types
@admin_bp.route('/system-types', methods=['GET', 'POST'])
@role_required('admin')
def system_types():
    if request.method == 'POST':
        name = request.form.get('name')
        tagline = request.form.get('tagline')
        description = request.form.get('description')
        has_grid = 'has_grid' in request.form
        requires_battery = 'requires_battery' in request.form
        provides_backup = 'provides_backup' in request.form
        supports_net_metering = 'supports_net_metering' in request.form

        new_type = SystemType(
            name=name,
            tagline=tagline,
            description=description,
            has_grid=has_grid,
            requires_battery=requires_battery,
            provides_backup=provides_backup,
            supports_net_metering=supports_net_metering
        )
        db.session.add(new_type)
        db.session.commit()
        flash('System Type successfully added!', 'success')
        return redirect(url_for('admin.system_types'))

    types = SystemType.query.all()
    return render_template('admin/admin_system-types.html', types=types)


# 2. Customer Comparison View Page
# @system_types_bp.route('/system-types')
# def compare_systems():
#     types = SystemType.query.all()
#     return render_template('system_types_compare.html', types=types)