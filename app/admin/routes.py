from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Customer, SolarPackage, SystemType, UserRole, StaffRoleRequest, Survey, Quotation, Installation, Inventory, MaintenanceRequest
from app.auth.decorators import role_required
from app.roles import ROLES, STAFF_ROLES, label_for, get_user_roles, sync_user_roles, dashboard_for
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.email import send_survey_email

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
        'admin/admin_users.html',
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



# @admin_bp.route('/surveys')
# @role_required('admin')
# def surveys():
#     unassigned = Survey.query.filter(Survey.engineer == 'Unassigned').order_by(Survey.id.desc()).all()
#     my_name = session.get('user_name')
#     my_surveys = Survey.query.filter_by(engineer=my_name).order_by(Survey.id.desc()).all()
#     completed = [s for s in my_surveys if s.status in ('Survey Completed', 'Report Submitted')]
#     return render_template('admin/admin_surveys.html', unassigned=unassigned, my_surveys=my_surveys, completed=completed,
#                            engineers=User.query.join(UserRole, UserRole.user_id == User.id).filter(UserRole.role == 'engineer').all())



@admin_bp.route('/surveys')
@role_required('admin')
def surveys():
    unassigned = Survey.query.filter_by(engineer_id=None).all()
    # my_surveys = Survey.query.filter_by(engineer_id=current_user.id).all()
    completed = Survey.query.filter_by(status='Completed').all()
    
    # Active Engineers load karein dropdown ke liye
    engineers = User.query.filter_by(role='engineer', status=1).all()

    return render_template(
        'admin/admin_surveys.html',
        unassigned=unassigned,
        # my_surveys=my_surveys,
        completed=completed,
        engineers=engineers
    )


# @admin_bp.route('/surveys/<int:survey_id>/assign', methods=['POST'])
# @role_required('admin')
# def assign_survey(survey_id):
#     survey = Survey.query.get_or_404(survey_id)
    
#     engineer_id = request.form.get('engineer_id', type=int)
#     new_date = request.form.get('preferred_date')
#     new_time = request.form.get('preferred_time')
    
#     engineer = User.query.get(engineer_id)
#     if not engineer:
#         flash('Invalid Engineer selected.', 'danger')
#         return redirect(url_for('admin.surveys'))

#     # Check if Admin modified date or time
#     date_changed = (survey.preferred_date != new_date)
#     time_changed = (survey.preferred_time != new_time)
    
#     survey.engineer_id = engineer_id
    
#     if date_changed or time_changed:
#         # CASE A: Date/Time Changed -> Needs Customer Approval
#         survey.preferred_date = new_date
#         survey.preferred_time = new_time
#         survey.status = 0  # Pending Approval
#         survey.rescheduled_by_admin = True
        
#         db.session.commit()
        
#         # Email ONLY to Customer
#         approval_link = url_for('surveys.approve_reschedule', survey_id=survey.id, _external=True)
#         customer_email_body = f"""
#         <h3>Hello {survey.customer_name},</h3>
#         <p>Your survey request date/time has been modified by the admin.</p>
#         <p><strong>New Schedule:</strong> {new_date} at {new_time}</p>
#         <p>Please review and confirm if this schedule works for you:</p>
#         <a href="{approval_link}" style="padding:10px 15px; background:purple; color:white; text-decoration:none; border-radius:5px;">Approve New Schedule</a>
#         """
#         send_survey_email(survey.customer.email, "Action Required: Survey Schedule Change", customer_email_body)
        
#         flash('Survey rescheduled! Sent approval request email to customer. Engineer will be notified upon acceptance.', 'warning')
        
#     else:
#         # CASE B: No Schedule Change -> Immediate Assignment
#         survey.status = 1  # Assigned
#         survey.rescheduled_by_admin = False
        
#         db.session.commit()
        
#         # Email to Customer
#         send_survey_email(
#             survey.customer.email,
#             "Survey Confirmed & Engineer Assigned",
#             f"<h3>Survey Confirmed</h3><p>Engineer <strong>{engineer.name}</strong> has been assigned to your survey on {survey.preferred_date} ({survey.preferred_time}).</p>"
#         )
        
#         # Email to Engineer
#         send_survey_email(
#             engineer.email,
#             "New Survey Task Assigned",
#             f"<h3>New Assignment</h3><p>You have been assigned to survey <strong>SUR-{survey.id}</strong> at {survey.address} on {survey.preferred_date} ({survey.preferred_time}).</p>"
#         )
        
#         flash('Survey assigned successfully and notifications sent.', 'success')

#     return redirect(url_for('admin.surveys'))

@admin_bp.route('/surveys/<int:survey_id>/assign', methods=['POST'])
@role_required('admin')
def assign_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    
    engineer_id = request.form.get('engineer_id', type=int)
    new_date = request.form.get('preferred_date')
    new_time = request.form.get('preferred_time')
    
    engineer = User.query.get(engineer_id)
    if not engineer:
        flash('Invalid Engineer selected.', 'danger')
        return redirect(url_for('admin.surveys'))

    # Check if Admin modified date or time
    date_changed = (survey.preferred_date != new_date)
    time_changed = (survey.preferred_time != new_time)
    
    survey.engineer_id = engineer_id
    
    if date_changed or time_changed:
        # CASE A: Schedule Modified -> Requires Customer Confirmation
        survey.preferred_date = new_date
        survey.preferred_time = new_time
        survey.status = 0  # Pending Approval
        survey.rescheduled_by_admin = True
        
        db.session.commit()
        flash('Survey schedule updated. Pending customer approval.', 'warning')
        
    else:
        # CASE B: Schedule Unchanged -> Direct Active Assignment
        survey.status = 1  # Assigned / Approved
        survey.rescheduled_by_admin = False
        
        db.session.commit()
        flash('Engineer assigned successfully!', 'success')

    return redirect(url_for('admin.surveys'))