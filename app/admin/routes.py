from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Customer, SolarPackage, SystemType, UserRole, StaffRoleRequest, Survey, Quotation, Installation, Inventory, MaintenanceRequest, Project, Notification
from app.auth.decorators import role_required
from app.roles import ROLES, STAFF_ROLES, label_for, get_user_roles, sync_user_roles, dashboard_for
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.email import send_survey_email

admin_bp = Blueprint('admin', __name__)
ADMIN_EMAIL = 'admin@solarease.pk'


def notify_user(user_id, title, message):
    if user_id:
        db.session.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message
            )
        )




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


# USERS (VIEW, CREATE)

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


# PACKAGES & SYSTEM-TYPES
@admin_bp.route('/packages')
@role_required('admin')
def packages():
    # Admin's Users table is a staff-access table. Customer profiles live separately.
    packages = [pkg for pkg in SolarPackage.query.all()]
    return render_template(
        'admin/admin_packages.html',
        packages=packages
    )

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






# SURVEYS (VIEW, ASSIGN ENGINER & VIEW REPORT):-

@admin_bp.route('/surveys')
@role_required('admin')
def surveys():

    unassigned = Survey.query.filter(
        Survey.engineer_id.is_(None),
        Survey.status.in_([5])
    ).order_by(
        Survey.id.desc()
    ).all()

    pending_approval = Survey.query.filter_by(
        status=0
    ).order_by(
        Survey.id.desc()
    ).all()

    completed = Survey.query.filter_by(
        status=3
    ).order_by(
        Survey.id.desc()
    ).all()

    engineers = User.query.filter_by(
        role='engineer',
        status=1
    ).all()

    return render_template(
        'admin/admin_surveys.html',
        unassigned=unassigned,
        pending_approval=pending_approval,
        completed=completed,
        engineers=engineers
    )


@admin_bp.route(
    '/surveys/<int:survey_id>/assign',
    methods=['POST']
)
@role_required('admin')
def assign_survey(survey_id):

    survey = Survey.query.get_or_404(
        survey_id
    )

    engineer_id = request.form.get(
        'engineer_id',
        type=int
    )

    new_date = request.form.get(
        'preferred_date'
    )

    new_time = request.form.get(
        'preferred_time'
    )

    engineer = User.query.get(
        engineer_id
    )

    if not engineer:
        flash(
            'Invalid engineer selected.',
            'danger'
        )

        return redirect(
            url_for('admin.surveys')
        )

    if not new_date or not new_time:
        flash(
            'Date and time are required.',
            'danger'
        )

        return redirect(
            url_for('admin.surveys')
        )

    # Check engineer schedule conflict
    conflict = Survey.query.filter(
        Survey.engineer_id == engineer_id,
        Survey.id != survey.id,
        Survey.preferred_date == new_date,
        Survey.preferred_time == new_time,
        Survey.status.in_([0, 1, 2])
    ).first()

    if conflict:

        flash(
            f'{engineer.full_name} is already assigned to '
            f'SUR-{conflict.id} at this date/time.',
            'danger'
        )

        return redirect(
            url_for('admin.surveys')
        )

    date_changed = (
        survey.preferred_date != new_date
    )

    time_changed = (
        survey.preferred_time != new_time
    )

    survey.engineer_id = engineer_id
    survey.preferred_date = new_date
    survey.preferred_time = new_time

    if date_changed or time_changed:

        survey.status = 0
        survey.rescheduled_by_admin = True

        notify_user(
            survey.user_id,
            'Survey Schedule Changed',
            f'Admin proposed a new schedule for SUR-{survey.id}: '
            f'{new_date} ({new_time}). Please approve or suggest another time.'
        )

        if survey.user_id:

            customer = User.query.get(
                survey.user_id
            )

            if customer and customer.email:

                send_survey_email(
                    customer.email,
                    'SolarEase - Survey Schedule Changed',
                    f'''
                    <h3>Survey Schedule Updated</h3>
                    <p>Your site survey <strong>SUR-{survey.id}</strong>
                    has been scheduled for:</p>
                    <p><strong>{new_date}</strong></p>
                    <p><strong>{new_time}</strong></p>
                    <p>Please login to SolarEase to approve the schedule
                    or suggest another time.</p>
                    '''
                )

        if engineer.email:

            send_survey_email(
                engineer.email,
                'SolarEase - Survey Assignment',
                f'''
                <h3>Survey Assignment</h3>
                <p>You have been assigned SUR-{survey.id}.</p>
                <p><strong>Customer:</strong> {survey.customer_name}</p>
                <p><strong>Address:</strong> {survey.address}</p>
                <p><strong>Date:</strong> {new_date}</p>
                <p><strong>Time:</strong> {new_time}</p>
                <p>The assignment becomes active after customer approval.</p>
                '''
            )

        flash(
            'Schedule changed. Customer approval is required.',
            'warning'
        )

    else:

        survey.status = 1
        survey.rescheduled_by_admin = False

        notify_user(
            survey.user_id,
            'Survey Confirmed',
            f'SUR-{survey.id} has been confirmed for '
            f'{new_date} ({new_time}).'
        )

        notify_user(
            engineer.id,
            'New Survey Assigned',
            f'SUR-{survey.id} has been assigned to you for '
            f'{new_date} ({new_time}).'
        )

        customer = User.query.get(
            survey.user_id
        )

        if customer and customer.email:

            send_survey_email(
                customer.email,
                'SolarEase - Survey Confirmed',
                f'''
                <h3>Survey Confirmed</h3>
                <p>Your site survey <strong>SUR-{survey.id}</strong>
                has been confirmed.</p>
                <p><strong>Date:</strong> {new_date}</p>
                <p><strong>Time:</strong> {new_time}</p>
                <p><strong>Engineer:</strong> {engineer.full_name}</p>
                '''
            )

        if engineer.email:

            send_survey_email(
                engineer.email,
                'SolarEase - New Survey Assignment',
                f'''
                <h3>New Survey Assignment</h3>
                <p>SUR-{survey.id} has been assigned to you.</p>
                <p><strong>Customer:</strong> {survey.customer_name}</p>
                <p><strong>Address:</strong> {survey.address}</p>
                <p><strong>Date:</strong> {new_date}</p>
                <p><strong>Time:</strong> {new_time}</p>
                '''
            )

        flash(
            'Engineer assigned successfully.',
            'success'
        )

    db.session.commit()

    return redirect(
        url_for('admin.surveys')
    )


@admin_bp.route(
    '/surveys/<int:survey_id>/report'
)
@role_required('admin')
def survey_report(survey_id):

    survey = Survey.query.get_or_404(
        survey_id
    )

    return render_template(
        'admin/survey_report.html',
        survey=survey
    )


# PROJECTS 
@admin_bp.route('/projects')
@role_required('admin')
def projects_list():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    # Sirf un users ko lao jinka role 'technician' hai
    technicians = User.query.filter_by(role='technician').all() 
    return render_template('admin/admin/projects.html', projects=projects, technicians=technicians)

# @admin_bp.route('/projects/<int:id>/assign', methods=['POST'])
# @role_required('admin')
# def assign_project_technician(id):
#     project = Project.query.get_or_404(id)
#     technician_id = request.form.get('technician_id')

#     if technician_id:
#         project.technician_id = technician_id
#         project.status = 'In Progress'
#         db.session.commit()
#         flash('Technician successfully assigned to the project!', 'success')

#     return redirect(url_for('admin.projects_list'))


# @admin_bp.route('/projects/<int:id>/assign', methods=['POST'])
# @role_required('admin')
# def assign_project_technician(id):
#     project = Project.query.get_or_404(id)
#     technician_id = request.form.get('technician_id')

#     if technician_id:
#         # 1. Project Table Update
#         project.technician_id = technician_id
#         project.status = 'In Progress'

#         # 2. Check & Auto-Create Installation Record
#         installation = Installation.query.filter_by(project_id=project.id).first()

#         if not installation:
#             installation = Installation(
#                 project_id=project.id,
#                 quotation_id=project.quotation_id,
#                 technician_id=technician_id,
#                 status='Project Created',
#                 notes='Installation task auto-generated on technician assignment.'
#             )
#             db.session.add(installation)
#         else:
#             # Agar pehle se record majood hai toh sirf technician_id update kardein
#             installation.technician_id = technician_id

#         # 3. Commit Changes to Database
#         db.session.commit()
#         flash('Technician assigned and Installation process initiated successfully!', 'success')
#     else:
#         flash('Please select a valid technician.', 'danger')

#     return redirect(url_for('admin.projects_list'))


@admin_bp.route('/projects/<int:id>/assign', methods=['POST'])
@role_required('admin')
def assign_project_technician(id):
    project = Project.query.get_or_404(id)
    technician_id = request.form.get('technician_id')

    if technician_id:
        # 1. Project Table Update
        project.technician_id = technician_id
        project.status = 'In Progress'

        # 2. Check & Auto-Create Installation Record using quotation_id
        installation = Installation.query.filter_by(quotation_id=project.quotation_id).first()

        if not installation:
            installation = Installation(
                quotation_id=project.quotation_id,
                technician=technician_id,
                status='Project Created',
                notes='Installation task auto-generated on technician assignment.'
            )
            db.session.add(installation)
        else:
            # Agar pehle se Installation Record mojood hai toh technician_id update karein
            installation.technician = technician_id

        # 3. Commit Changes to Database
        db.session.commit()
        flash('Technician assigned and Installation process initiated successfully!', 'success')
    else:
        flash('Please select a valid technician.', 'danger')

    return redirect(url_for('admin.projects_list'))