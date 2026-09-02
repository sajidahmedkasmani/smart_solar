from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Survey, User, UserRole
from app.auth.decorators import role_required

surveys_bp = Blueprint('surveys', __name__)


@surveys_bp.route('/', methods=['GET', 'POST'])
@role_required('customer')
def index():
    if request.method == 'POST':
        s = Survey(
            user_id=session.get('user_id'), customer_name=session.get('user_name', 'Customer'),
            phone=request.form.get('phone', ''), city=request.form.get('city', 'Karachi'),
            address=request.form['address'], preferred_date=request.form['preferred_date'],
            preferred_time=request.form['preferred_time'], property_type=request.form.get('property_type', 'Residential'),
            contact_person=request.form.get('contact_person', ''), notes=request.form.get('notes', ''), status='Requested'
        )
        db.session.add(s)
        db.session.commit()
        flash('Site survey request submitted successfully!', 'success')
        return redirect(url_for('surveys.index'))
    return render_template('landing_page/survey_booking.html')


@surveys_bp.route('/list')
@role_required('customer')
def list_surveys():
    return index()


@surveys_bp.route('/new', methods=['GET', 'POST'])
@role_required('customer')
def new_survey():
    return index()


@surveys_bp.route('/engineer')
@role_required('engineer')
def engineer_dashboard():
    unassigned = Survey.query.filter(Survey.engineer == 'Unassigned').order_by(Survey.id.desc()).all()
    my_name = session.get('user_name')
    my_surveys = Survey.query.filter_by(engineer=my_name).order_by(Survey.id.desc()).all()
    completed = [s for s in my_surveys if s.status in ('Survey Completed', 'Report Submitted')]
    return render_template('admin/engineer_dashboard.html', unassigned=unassigned, my_surveys=my_surveys, completed=completed,
                           engineers=User.query.join(UserRole, UserRole.user_id == User.id).filter(UserRole.role == 'engineer').all())


@surveys_bp.route('/engineer/claim/<int:survey_id>', methods=['POST'])
@role_required('engineer')
def claim_survey(survey_id):
    s = Survey.query.get_or_404(survey_id)
    s.engineer = session.get('user_name')
    s.status = 'Engineer Assigned'
    db.session.commit()
    flash('Survey assigned to you.', 'success')
    return redirect(url_for('surveys.engineer_dashboard'))


@surveys_bp.route('/admin/update/<int:survey_id>', methods=['POST'])
@role_required('admin', 'engineer')
def update_survey(survey_id):
    s = Survey.query.get_or_404(survey_id)
    s.engineer = request.form.get('engineer', s.engineer)
    s.status = request.form.get('status', s.status)
    s.report_notes = request.form.get('report_notes', s.report_notes)
    s.roof_area = float(request.form.get('roof_area', s.roof_area) or 0)
    s.recommended_kw = float(request.form.get('recommended_kw', s.recommended_kw) or 0)
    if request.form.get('roof_direction'):
        s.roof_direction = request.form.get('roof_direction')
    if request.form.get('shading'):
        s.shading = request.form.get('shading')
    db.session.commit()
    flash('Survey report updated.', 'success')
    from app.auth.decorators import session_roles
    return redirect(url_for('surveys.engineer_dashboard') if 'engineer' in session_roles() and 'admin' not in session_roles() else url_for('admin.dashboard'))
