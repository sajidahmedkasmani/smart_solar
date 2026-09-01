from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import MaintenanceRequest
from app.auth.decorators import role_required, session_roles

maintenance_bp = Blueprint('maintenance', __name__)


@maintenance_bp.route('/', methods=['GET', 'POST'])
@role_required('customer')
def maintenance():
    if request.method == 'POST':
        r = MaintenanceRequest(
            user_id=session.get('user_id'),
            customer_name=session.get('user_name', 'Customer'),
            service_type=request.form['issue_type'],
            issue_description=request.form['description'],
        )
        db.session.add(r)
        db.session.commit()
        flash('Maintenance request submitted.', 'success')
        return redirect(url_for('maintenance.maintenance'))
    requests = MaintenanceRequest.query.filter_by(user_id=session.get('user_id')).order_by(MaintenanceRequest.id.desc()).all()
    return render_template('maintenance.html', maintenance_requests=requests)


@maintenance_bp.route('/list')
@role_required('customer')
def list_requests():
    return maintenance()


@maintenance_bp.route('/update/<int:request_id>', methods=['POST'])
@role_required('admin', 'technician', 'engineer')
def update_status(request_id):
    r = MaintenanceRequest.query.get_or_404(request_id)
    r.status = request.form.get('status', r.status)
    db.session.commit()
    flash('Maintenance request status updated.', 'success')
    roles = session_roles()
    role = 'admin' if 'admin' in roles else ('technician' if 'technician' in roles else ('engineer' if 'engineer' in roles else 'customer'))
    if role == 'technician':
        return redirect(url_for('installations.technician_dashboard'))
    if role == 'engineer':
        return redirect(url_for('surveys.engineer_dashboard'))
    return redirect(url_for('admin.dashboard'))
