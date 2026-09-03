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
    SurveyImage
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
def complete_survey(survey_id):

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

    if survey.status != STATUS_IN_PROGRESS:
        flash(
            'Start the survey before completing it.',
            'warning'
        )

        return redirect(
            url_for('surveys.engineer_dashboard')
        )

    try:
        survey.roof_area = float(
            request.form.get(
                'roof_area',
                0
            ) or 0
        )
    except ValueError:
        survey.roof_area = 0

    try:
        survey.recommended_kw = float(
            request.form.get(
                'recommended_kw',
                0
            ) or 0
        )
    except ValueError:
        survey.recommended_kw = 0

    survey.roof_direction = request.form.get(
        'roof_direction',
        'Not recorded'
    )

    survey.shading = request.form.get(
        'shading',
        'Not recorded'
    )

    survey.report_notes = request.form.get(
        'report_notes',
        ''
    )

    survey.status = STATUS_COMPLETED
    survey.completed_at = datetime.now()

    # Upload images
    upload_folder = os.path.join(
        current_app.static_folder,
        'uploads',
        'surveys'
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    files = request.files.getlist(
        'survey_images'
    )

    for file in files:

        if not file or not file.filename:
            continue

        filename = secure_filename(
            file.filename
        )

        unique_name = (
            f'{survey.id}_'
            f'{int(datetime.now().timestamp())}_'
            f'{filename}'
        )

        file.save(
            os.path.join(
                upload_folder,
                unique_name
            )
        )

        image = SurveyImage(
            survey_id=survey.id,
            filename=unique_name,
            image_type=request.form.get(
                'image_type',
                'site'
            )
        )

        db.session.add(image)

    notify_user(
        survey.user_id,
        'Survey Completed',
        f'Site survey SUR-{survey.id} has been completed.'
    )

    notify_admins(
        'Survey Completed',
        f'SUR-{survey.id} is ready for review and quotation.'
    )

    db.session.commit()

    flash(
        'Survey completed and technical report submitted.',
        'success'
    )

    return redirect(
        url_for(
            'surveys.engineer_dashboard'
        )
    )


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
            'landing_page/customer/survey_response.html',
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