from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Installation, Quotation, Warranty
from app.auth.decorators import role_required, session_roles

installations_bp = Blueprint('installations', __name__)


@installations_bp.route('/')
@role_required('customer')
def list_installations():
    uid = session.get('user_id')
    projects = (Installation.query.join(Quotation, Installation.quotation_id == Quotation.id)
                .outerjoin(Quotation.survey)
                .outerjoin(Quotation.requirement)
                .filter(db.or_(Quotation.survey.has(user_id=uid), Quotation.requirement.has(user_id=uid)))
                .order_by(Installation.id.desc()).all())
    return render_template('installation_tracking.html', projects=projects)


@installations_bp.route('/schedule/<int:quote_id>', methods=['GET', 'POST'])
@role_required('admin')
def schedule(quote_id):
    q = Quotation.query.get_or_404(quote_id)
    if request.method == 'POST':
        inst = Installation(quotation_id=q.id, team_lead=request.form.get('team_lead', 'Not Assigned'),
                            technician=request.form.get('technician', 'Not Assigned'), capacity_kw=q.system_capacity_kw,
                            address=request.form.get('address', ''), status='Scheduled')
        db.session.add(inst)
        db.session.commit()
        flash('Installation scheduled!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('installation_tracking.html', projects=[q.installation] if q.installation else [])


@installations_bp.route('/update/<int:installation_id>', methods=['POST'])
@role_required('admin', 'technician')
def update(installation_id):
    i = Installation.query.get_or_404(installation_id)
    if 'technician' in session_roles() and 'admin' not in session_roles() and i.technician != session.get('user_name'):
        flash('You can only update installations assigned to you.', 'danger')
        return redirect(url_for('installations.technician_dashboard'))
    i.status = request.form.get('status', i.status)
    if 'admin' in session_roles():
        i.technician = request.form.get('technician', i.technician)
    if request.form.get('notes'):
        i.notes = request.form.get('notes')
    if i.status == 'Completed & Handover' and not Warranty.query.filter_by(serial_number=f'SE-PRJ-{i.id:05d}').first():
        db.session.add(Warranty(component_name='Solar Installation System', serial_number=f'SE-PRJ-{i.id:05d}',
                                warranty_years=10, start_date=date.today().isoformat()))
    db.session.commit()
    flash('Installation progress updated.', 'success')
    return redirect(url_for('installations.technician_dashboard') if 'technician' in session_roles() and 'admin' not in session_roles() else url_for('admin.dashboard'))


@installations_bp.route('/technician')
@role_required('technician')
def technician_dashboard():
    my_name = session.get('user_name')
    my_projects = Installation.query.filter_by(technician=my_name).order_by(Installation.id.desc()).all()
    in_progress = [p for p in my_projects if p.status != 'Completed & Handover']
    completed = [p for p in my_projects if p.status == 'Completed & Handover']
    return render_template('technician_dashboard.html', my_projects=my_projects, unassigned=[],
                           in_progress=in_progress, completed=completed)
