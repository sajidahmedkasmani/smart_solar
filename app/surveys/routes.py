import os
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app
)

from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Survey,
    User,
    UserRole,
    Notification,
    SurveyImage,
    Quotation
)
from app.auth.decorators import role_required
from app.utils.email import send_survey_email


surveys_bp = Blueprint('surveys', __name__)


STATUS_PENDING_ADMIN = 5
STATUS_RESCHEDULE_APPROVAL = 0
STATUS_ASSIGNED = 1
STATUS_IN_PROGRESS = 2
STATUS_COMPLETED = 3
STATUS_CANCELLED = 4


def notify_user(user_id, title, message):
    if not user_id:
        return

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message
    )

    db.session.add(notification)


def notify_admins(title, message):
    admins = User.query.filter_by(
        role='admin',
        status=1
    ).all()

    for admin in admins:
        notify_user(
            admin.id,
            title,
            message
        )


def parse_appointment_start(survey):
    """
    Converts survey date/time slot into appointment datetime.
    """

    try:
        appointment_date = datetime.strptime(
            survey.preferred_date,
            '%Y-%m-%d'
        ).date()
    except (ValueError, TypeError):
        return None

    time_text = (
        survey.preferred_time or ''
    ).lower()

    if '09:00' in time_text or 'morning' in time_text:
        hour = 9
    elif '12:00' in time_text or 'afternoon' in time_text:
        hour = 12
    elif '03:00' in time_text or '15:00' in time_text or 'evening' in time_text:
        hour = 15
    else:
        return None

    return datetime.combine(
        appointment_date,
        datetime.min.time()
    ).replace(hour=hour)


def survey_can_start(survey):
    appointment = parse_appointment_start(survey)

    if not appointment:
        return False

    return datetime.now() >= (
        appointment - timedelta(minutes=10)
    )


@surveys_bp.route('/', methods=['GET', 'POST'])
@role_required('customer')
def index():

    if request.method == 'POST':

        s = Survey(
            user_id=session.get('user_id'),

            customer_name=session.get(
                'user_name',
                'Customer'
            ),

            phone=request.form.get(
                'phone',
                ''
            ),

            city=request.form.get(
                'city',
                'Karachi'
            ),

            address=request.form.get(
                'address',
                ''
            ),

            preferred_date=request.form.get(
                'preferred_date',
                ''
            ),

            preferred_time=request.form.get(
                'preferred_time',
                ''
            ),

            property_type=request.form.get(
                'property_type',
                'Residential'
            ),

            contact_person=request.form.get(
                'contact_person',
                ''
            ),

            notes=request.form.get(
                'notes',
                ''
            ),

            status=STATUS_PENDING_ADMIN
        )

        db.session.add(s)

        db.session.flush()

        notify_admins(
            'New Survey Request',
            f'SUR-{s.id} has been submitted by {s.customer_name}.'
        )

        db.session.commit()

        flash(
            'Site survey request submitted successfully!',
            'success'
        )

        return redirect(
            url_for('customers.cust_surveys')
        )

    return render_template(
        'landing_page/survey_booking.html'
    )


@surveys_bp.route('/list')
@role_required('customer')
def list_surveys():
    return redirect(
        url_for('customers.cust_surveys')
    )


@surveys_bp.route('/new', methods=['GET', 'POST'])
@role_required('customer')
def new_survey():
    return index()


@surveys_bp.route('/engineer')
@role_required('engineer')
def engineer_dashboard():

    user_id = session.get('user_id')

    unassigned = Survey.query.filter(
        Survey.engineer_id.is_(None),
        Survey.status.in_([
            STATUS_PENDING_ADMIN
        ])
    ).order_by(
        Survey.id.desc()
    ).all()

    my_surveys = Survey.query.filter_by(
        engineer_id=user_id
    ).order_by(
        Survey.preferred_date.asc(),
        Survey.id.desc()
    ).all()

    completed = [
        s for s in my_surveys
        if s.status == STATUS_COMPLETED
    ]

    return render_template(
        'admin/engineer_dashboard.html',
        unassigned=unassigned,
        my_surveys=my_surveys,
        completed=completed
    )


@surveys_bp.route(
    '/engineer/claim/<int:survey_id>',
    methods=['POST']
)
@role_required('engineer')
def claim_survey(survey_id):

    survey = Survey.query.get_or_404(
        survey_id
    )

    if survey.engineer_id:
        flash(
            'This survey is already assigned.',
            'warning'
        )

        return redirect(
            url_for('surveys.engineer_dashboard')
        )

    survey.engineer_id = session.get(
        'user_id'
    )

    survey.status = STATUS_ASSIGNED

    notify_user(
        survey.user_id,
        'Engineer Assigned',
        f'Engineer has been assigned to SUR-{survey.id}.'
    )

    db.session.commit()

    flash(
        'Survey assigned to you.',
        'success'
    )

    return redirect(
        url_for('surveys.engineer_dashboard')
    )


@surveys_bp.route(
    '/engineer/start/<int:survey_id>',
    methods=['POST']
)
@role_required('engineer')
def start_survey(survey_id):

    survey = Survey.query.get_or_404(
        survey_id
    )

    if survey.engineer_id != session.get('user_id'):
        flash(
            'You are not assigned to this survey.',
            'danger'
        )

        return redirect(
            url_for('surveys.engineer_dashboard')
        )

    if survey.status != STATUS_ASSIGNED:
        flash(
            'This survey cannot be started.',
            'warning'
        )

        return redirect(
            url_for('surveys.engineer_dashboard')
        )

    if not survey_can_start(survey):
        flash(
            'Survey can only be started 10 minutes before the appointment.',
            'warning'
        )

        return redirect(
            url_for('surveys.engineer_dashboard')
        )

    survey.status = STATUS_IN_PROGRESS
    survey.started_at = datetime.now()

    notify_user(
        survey.user_id,
        'Survey Started',
        f'Engineer has started SUR-{survey.id}.'
    )

    db.session.commit()

    flash(
        'Survey started. You can now complete the technical inspection.',
        'success'
    )

    return redirect(
        url_for(
            'surveys.engineer_dashboard'
        )
    )


@surveys_bp.route(
    '/engineer/complete/<int:survey_id>',
    methods=['POST']
)
@role_required('engineer')
# def complete_survey(survey_id):

#     survey = Survey.query.get_or_404(
#         survey_id
#     )

#     if survey.engineer_id != session.get('user_id'):
#         flash(
#             'You are not assigned to this survey.',
#             'danger'
#         )

#         return redirect(
#             url_for('surveys.engineer_dashboard')
#         )

#     if survey.status != STATUS_IN_PROGRESS:
#         flash(
#             'Start the survey before completing it.',
#             'warning'
#         )

#         return redirect(
#             url_for('surveys.engineer_dashboard')
#         )

#     try:
#         survey.roof_area = float(
#             request.form.get(
#                 'roof_area',
#                 0
#             ) or 0
#         )
#     except ValueError:
#         survey.roof_area = 0

#     try:
#         survey.recommended_kw = float(
#             request.form.get(
#                 'recommended_kw',
#                 0
#             ) or 0
#         )
#     except ValueError:
#         survey.recommended_kw = 0

#     survey.roof_direction = request.form.get(
#         'roof_direction',
#         'Not recorded'
#     )

#     survey.shading = request.form.get(
#         'shading',
#         'Not recorded'
#     )

#     survey.report_notes = request.form.get(
#         'report_notes',
#         ''
#     )

#     survey.status = STATUS_COMPLETED
#     survey.completed_at = datetime.now()

#     # Upload images
#     upload_folder = os.path.join(
#         current_app.static_folder,
#         'uploads',
#         'surveys'
#     )

#     os.makedirs(
#         upload_folder,
#         exist_ok=True
#     )

#     files = request.files.getlist(
#         'survey_images'
#     )

#     for file in files:

#         if not file or not file.filename:
#             continue

#         filename = secure_filename(
#             file.filename
#         )

#         unique_name = (
#             f'{survey.id}_'
#             f'{int(datetime.now().timestamp())}_'
#             f'{filename}'
#         )

#         file.save(
#             os.path.join(
#                 upload_folder,
#                 unique_name
#             )
#         )

#         image = SurveyImage(
#             survey_id=survey.id,
#             filename=unique_name,
#             image_type=request.form.get(
#                 'image_type',
#                 'site'
#             )
#         )

#         db.session.add(image)

#     notify_user(
#         survey.user_id,
#         'Survey Completed',
#         f'Site survey SUR-{survey.id} has been completed.'
#     )

#     notify_admins(
#         'Survey Completed',
#         f'SUR-{survey.id} is ready for review and quotation.'
#     )

#     db.session.commit()

#     flash(
#         'Survey completed and technical report submitted.',
#         'success'
#     )

#     return redirect(
#         url_for(
#             'surveys.engineer_dashboard'
#         )
#     )


# def complete_survey(survey_id):

#     survey = Survey.query.get_or_404(
#         survey_id
#     )

#     # Check assigned engineer
#     if survey.engineer_id != session.get('user_id'):
#         flash(
#             'You are not assigned to this survey.',
#             'danger'
#         )

#         return redirect(
#             url_for('surveys.engineer_dashboard')
#         )

#     # Survey must be in progress
#     if survey.status != STATUS_IN_PROGRESS:
#         flash(
#             'Start the survey before completing it.',
#             'warning'
#         )

#         return redirect(
#             url_for('surveys.engineer_dashboard')
#         )

#     try:

#         # -----------------------------------------
#         # SAVE SURVEY REPORT DATA
#         # -----------------------------------------

#         try:
#             survey.roof_area = float(
#                 request.form.get(
#                     'roof_area',
#                     0
#                 ) or 0
#             )
#         except ValueError:
#             survey.roof_area = 0

#         try:
#             survey.recommended_kw = float(
#                 request.form.get(
#                     'recommended_kw',
#                     0
#                 ) or 0
#             )
#         except ValueError:
#             survey.recommended_kw = 0

#         survey.roof_direction = request.form.get(
#             'roof_direction',
#             'Not recorded'
#         )

#         survey.shading = request.form.get(
#             'shading',
#             'Not recorded'
#         )

#         survey.report_notes = request.form.get(
#             'report_notes',
#             ''
#         )

#         # -----------------------------------------
#         # MARK SURVEY COMPLETED
#         # -----------------------------------------

#         survey.status = STATUS_COMPLETED

#         survey.completed_at = datetime.now()

#         # -----------------------------------------
#         # AUTOMATICALLY GENERATE QUOTATION
#         # -----------------------------------------

#         quotation = generate_quotation(
#             survey
#         )

#         # -----------------------------------------
#         # UPLOAD SURVEY IMAGES
#         # -----------------------------------------

#         upload_folder = os.path.join(
#             current_app.static_folder,
#             'uploads',
#             'surveys'
#         )

#         os.makedirs(
#             upload_folder,
#             exist_ok=True
#         )

#         files = request.files.getlist(
#             'survey_images'
#         )

#         for file in files:

#             if not file or not file.filename:
#                 continue

#             filename = secure_filename(
#                 file.filename
#             )

#             unique_name = (
#                 f'{survey.id}_'
#                 f'{int(datetime.now().timestamp())}_'
#                 f'{filename}'
#             )

#             file.save(
#                 os.path.join(
#                     upload_folder,
#                     unique_name
#                 )
#             )

#             image = SurveyImage(
#                 survey_id=survey.id,
#                 filename=unique_name,
#                 image_type=request.form.get(
#                     'image_type',
#                     'site'
#                 )
#             )

#             db.session.add(
#                 image
#             )

#         # -----------------------------------------
#         # CUSTOMER NOTIFICATION
#         # -----------------------------------------

#         notify_user(
#             survey.user_id,
#             'Survey Completed',
#             f'Site survey SUR-{survey.id} has been completed.'
#         )

#         # -----------------------------------------
#         # ADMIN / SALES NOTIFICATION
#         # -----------------------------------------

#         notify_admins(
#             'Quotation Ready for Review',
#             f'Quotation {quotation.quotation_number} '
#             f'for SUR-{survey.id} is ready for sales review.'
#         )

#         # -----------------------------------------
#         # SAVE EVERYTHING
#         # -----------------------------------------

#         db.session.commit()

#         flash(
#             'Survey completed and quotation generated successfully.',
#             'success'
#         )

#     except Exception as e:

#         db.session.rollback()

#         current_app.logger.exception(
#             'Error completing survey'
#         )

#         flash(
#             f'Error completing survey: {str(e)}',
#             'danger'
#         )

#     return redirect(
#         url_for(
#             'surveys.engineer_dashboard'
#         )
#     )


# def generate_quotation(survey):
#     """
#     Automatically generate a quotation after survey completion.
#     """

#     # Prevent duplicate quotation
#     existing_quotation = Quotation.query.filter_by(
#         survey_id=survey.id
#     ).first()

#     if existing_quotation:
#         return existing_quotation

#     # Get requirement
#     requirement = Requirement.query.get(
#         survey.requirement_id
#     )

#     if not requirement:
#         raise ValueError(
#             'Requirement not found for this survey.'
#         )

#     # System capacity
#     system_capacity = survey.recommended_kw or 0

#     if system_capacity <= 0:
#         raise ValueError(
#             'Recommended system capacity is required to generate quotation.'
#         )

#     # --------------------------------------------------
#     # QUOTATION CALCULATION
#     # --------------------------------------------------

#     # Example base rates
#     equipment_rate_per_kw = 180000
#     installation_rate_per_kw = 25000
#     transport_rate_per_kw = 5000

#     equipment_cost = (
#         system_capacity * equipment_rate_per_kw
#     )

#     installation_cost = (
#         system_capacity * installation_rate_per_kw
#     )

#     transport_cost = (
#         system_capacity * transport_rate_per_kw
#     )

#     # Tax
#     subtotal = (
#         equipment_cost
#         + installation_cost
#         + transport_cost
#     )

#     tax = subtotal * 0.18

#     discount = 0

#     final_amount = (
#         subtotal
#         + tax
#         - discount
#     )

#     # --------------------------------------------------
#     # QUOTATION NUMBER
#     # --------------------------------------------------

#     quotation_number = (
#         f'QUO-{datetime.now().strftime("%Y%m%d")}-'
#         f'{survey.id:04d}'
#     )

#     # --------------------------------------------------
#     # SYSTEM TYPE
#     # --------------------------------------------------

#     system_type = getattr(
#         requirement,
#         'system_type',
#         None
#     )

#     if not system_type:
#         system_type = 'Hybrid'

#     # --------------------------------------------------
#     # CREATE QUOTATION
#     # --------------------------------------------------

#     quotation = Quotation(
#         survey_id=survey.id,
#         requirement_id=survey.requirement_id,
#         quotation_number=quotation_number,
#         system_capacity_kw=system_capacity,
#         system_type=system_type,
#         equipment_cost=equipment_cost,
#         installation_cost=installation_cost,
#         transport_cost=transport_cost,
#         tax=tax,
#         discount=discount,
#         final_amount=final_amount,
#         payment_terms=(
#             '30% advance, 50% before installation, '
#             '20% after completion'
#         ),
#         warranty_terms=(
#             '10 years equipment warranty'
#         ),
#         status='Pending Sales Review',
#         customer_comment=''
#     )

#     db.session.add(quotation)

#     return quotation



def complete_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)

    # 1. Check assigned engineer (Session ya Current User Check)
    user_id = session.get('user_id') or getattr(current_user, 'id', None)
    if survey.engineer_id != user_id:
        flash('You are not assigned to this survey.', 'danger')
        return redirect(url_for('surveys.engineer_dashboard'))

    # 2. Survey status check
    if survey.status != STATUS_IN_PROGRESS:
        flash('Start the survey before completing it.', 'warning')
        return redirect(url_for('surveys.engineer_dashboard'))

    # 3. Input Validation (Form Submit check)
    recommended_kw = request.form.get('recommended_kw', 0)
    try:
        recommended_kw = float(recommended_kw)
    except ValueError:
        recommended_kw = 0.0

    if recommended_kw <= 0:
        flash('Please enter a valid Recommended System kW (greater than 0).', 'danger')
        return redirect(url_for('surveys.engineer_dashboard'))

    try:
        # Save Survey Data
        try:
            survey.roof_area = float(request.form.get('roof_area', 0) or 0)
        except ValueError:
            survey.roof_area = 0.0

        survey.recommended_kw = recommended_kw
        survey.roof_direction = request.form.get('roof_direction', 'Not recorded')
        survey.shading = request.form.get('shading', 'Not recorded')
        survey.report_notes = request.form.get('report_notes', '')

        # Mark Completed
        survey.status = STATUS_COMPLETED
        survey.completed_at = datetime.now()

        # Handle Image Uploads BEFORE generation/commit
        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'surveys')
        os.makedirs(upload_folder, exist_ok=True)

        files = request.files.getlist('survey_images')
        for file in files:
            if not file or not file.filename:
                continue

            filename = secure_filename(file.filename)
            unique_name = f"{survey.id}_{int(datetime.now().timestamp())}_{filename}"
            file.save(os.path.join(upload_folder, unique_name))

            image = SurveyImage(
                survey_id=survey.id,
                filename=unique_name,
                image_type=request.form.get('image_type', 'site')
            )
            db.session.add(image)

        # Generate Quotation
        quotation = generate_quotation(survey)

        # Notifications
        notify_user(
            survey.user_id,
            'Survey Completed',
            f'Site survey SUR-{survey.id} has been completed.'
        )

        notify_admins(
            'Quotation Ready for Review',
            f'Quotation {quotation.quotation_number} for SUR-{survey.id} is ready for sales review.'
        )

        # Commit All DB Changes Together
        db.session.commit()

        flash('Survey completed and quotation generated successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Error completing survey')
        flash(f'Error completing survey: {str(e)}', 'danger')

    return redirect(url_for('surveys.engineer_dashboard'))


def generate_quotation(survey):
    """ Automatically generate a quotation after survey completion. """

    existing_quotation = Quotation.query.filter_by(survey_id=survey.id).first()
    if existing_quotation:
        return existing_quotation

    # Get requirement
    requirement = None
    if getattr(survey, 'requirement_id', None):
        requirement = Requirement.query.get(survey.requirement_id)

    system_capacity = survey.recommended_kw or 0.0
    if system_capacity <= 0:
        raise ValueError('Recommended system capacity is required to generate quotation.')

    # Calculations
    equipment_rate_per_kw = 180000
    installation_rate_per_kw = 25000
    transport_rate_per_kw = 5000

    equipment_cost = system_capacity * equipment_rate_per_kw
    installation_cost = system_capacity * installation_rate_per_kw
    transport_cost = system_capacity * transport_rate_per_kw

    subtotal = equipment_cost + installation_cost + transport_cost
    tax = subtotal * 0.18
    discount = 0
    final_amount = subtotal + tax - discount

    quotation_number = f'QUO-{datetime.now().strftime("%Y%m%d")}-{survey.id:04d}'
    system_type = getattr(requirement, 'system_type', 'Hybrid') if requirement else 'Hybrid'

    quotation = Quotation(
        survey_id=survey.id,
        requirement_id=survey.requirement_id if hasattr(survey, 'requirement_id') else None,
        quotation_number=quotation_number,
        system_capacity_kw=system_capacity,
        system_type=system_type,
        equipment_cost=equipment_cost,
        installation_cost=installation_cost,
        transport_cost=transport_cost,
        tax=tax,
        discount=discount,
        final_amount=final_amount,
        payment_terms='30% advance, 50% before installation, 20% after completion',
        warranty_terms='10 years equipment warranty',
        status='Pending Sales Review',
        customer_comment=''
    )

    db.session.add(quotation)
    return quotation


@surveys_bp.route(
    '/reschedule/<int:survey_id>',
    methods=['GET', 'POST']
)
@role_required('customer')
def approve_reschedule(survey_id):

    survey = Survey.query.get_or_404(
        survey_id
    )

    if survey.user_id != session.get('user_id'):
        flash(
            'You cannot modify this survey.',
            'danger'
        )

        return redirect(
            url_for('customers.cust_surveys')
        )

    if survey.status != STATUS_RESCHEDULE_APPROVAL:
        flash(
            'This survey is not waiting for your approval.',
            'warning'
        )

        return redirect(
            url_for('customers.cust_surveys')
        )

    if request.method == 'GET':
      return render_template(
    'admin/survey_response.html',
    survey=survey

)

    action = request.form.get(
        'action'
    )

    if action == 'accept':

        survey.status = STATUS_ASSIGNED
        survey.rescheduled_by_admin = False

        if survey.engineer_id:
            notify_user(
                survey.engineer_id,
                'Survey Schedule Approved',
                f'Customer approved SUR-{survey.id} for '
                f'{survey.preferred_date} '
                f'({survey.preferred_time}).'
            )

        notify_admins(
            'Customer Approved Schedule',
            f'Customer approved SUR-{survey.id}.'
        )

        db.session.commit()

        flash(
            'Survey schedule approved.',
            'success'
        )

    elif action == 'reject':

        new_date = request.form.get(
            'new_date'
        )

        new_time = request.form.get(
            'new_time'
        )

        if not new_date or not new_time:
            flash(
                'Please provide your preferred new date and time.',
                'danger'
            )

            return redirect(
                url_for(
                    'surveys.approve_reschedule',
                    survey_id=survey.id
                )
            )

        survey.preferred_date = new_date
        survey.preferred_time = new_time

        # Old engineer is released
        survey.engineer_id = None

        survey.status = STATUS_PENDING_ADMIN
        survey.rescheduled_by_admin = False

        notify_admins(
            'Customer Requested New Survey Time',
            f'Customer rejected the proposed schedule for '
            f'SUR-{survey.id} and requested '
            f'{new_date} ({new_time}).'
        )

        db.session.commit()

        flash(
            'Your new preferred schedule has been sent to the admin.',
            'success'
        )

    return redirect(
        url_for('customers.cust_surveys')
    )