from datetime import datetime
import uuid

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app import db
from app.auth.decorators import role_required
from app.models import Complaint, Customer
from app.notifications.service import create_customer_notification, create_staff_notification

complaints_bp = Blueprint('complaints', __name__)

COMPLAINT_CATEGORIES = [
    'Delayed installation',
    'Incorrect equipment',
    'Payment issue',
    'Staff behavior',
    'Poor installation quality',
    'Warranty claim',
    'System performance',
    'Documentation delay',
]

COMPLAINT_STATUSES = [
    'Submitted',
    'Under Review',
    'Assigned',
    'In Progress',
    'Resolved',
    'Closed',
]


def _complaint_number():
    return f"CMP-{datetime.utcnow().year}-{uuid.uuid4().hex[:7].upper()}"


def _customer_id():
    return session.get('user_id')


@complaints_bp.route('/')
@role_required('customer')
def index():
    complaints = (
        Complaint.query
        .filter_by(customer_id=_customer_id())
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .all()
    )
    return render_template(
        'complaints.html',
        complaints=complaints,
        categories=COMPLAINT_CATEGORIES,
    )


@complaints_bp.route('/submit', methods=['POST'])
@role_required('customer')
def submit():
    category = request.form.get('category', '').strip()
    subject = request.form.get('subject', '').strip()
    description = request.form.get('description', '').strip()

    if category not in COMPLAINT_CATEGORIES:
        flash('Please select a valid complaint category.', 'warning')
        return redirect(url_for('complaints.index'))

    if not subject or len(subject) > 150:
        flash('Please enter a complaint subject (maximum 150 characters).', 'warning')
        return redirect(url_for('complaints.index'))

    if not description or len(description) < 10:
        flash('Please provide at least 10 characters describing the complaint.', 'warning')
        return redirect(url_for('complaints.index'))

    customer = Customer.query.get(_customer_id())
    if not customer:
        session.clear()
        flash('Customer account could not be found. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    complaint = Complaint(
        customer_id=customer.id,
        complaint_number=_complaint_number(),
        category=category,
        subject=subject,
        description=description,
        status='Submitted',
    )
    db.session.add(complaint)
    db.session.flush()
    create_customer_notification(
        customer.id,
        'Complaint submitted',
        f'Your complaint {complaint.complaint_number} has been received and is now under support review.',
        event_type='Complaint Submitted',
        category='complaint',
        link=url_for('complaints.view', complaint_id=complaint.id),
    )
    db.session.commit()

    flash(
        f'Complaint {complaint.complaint_number} submitted successfully.',
        'success',
    )
    return redirect(url_for('complaints.index'))


@complaints_bp.route('/view/<int:complaint_id>')
@role_required('customer')
def view(complaint_id):
    complaint = Complaint.query.filter_by(
        id=complaint_id,
        customer_id=_customer_id(),
    ).first_or_404()
    return render_template('complaint_detail.html', complaint=complaint)


# --------------------------- Admin Complaint Management ---------------------------

@complaints_bp.route('/admin')
@role_required('admin')
def admin_index():
    status_filter = request.args.get('status', '').strip()
    query = Complaint.query

    if status_filter in COMPLAINT_STATUSES:
        query = query.filter_by(status=status_filter)

    complaints = query.order_by(
        Complaint.created_at.desc(), Complaint.id.desc()
    ).all()

    counts = {
        status: Complaint.query.filter_by(status=status).count()
        for status in COMPLAINT_STATUSES
    }

    return render_template(
        'admin/complaints.html',
        complaints=complaints,
        statuses=COMPLAINT_STATUSES,
        counts=counts,
        active_status=status_filter,
    )


@complaints_bp.route('/admin/<int:complaint_id>/update', methods=['POST'])
@role_required('admin')
def update(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    status = request.form.get('status', '').strip()
    response = request.form.get('admin_response', '').strip()

    if status not in COMPLAINT_STATUSES:
        flash('Invalid complaint status.', 'danger')
        return redirect(url_for('complaints.admin_index'))

    if len(response) > 2000:
        flash('Admin response is too long (maximum 2000 characters).', 'warning')
        return redirect(url_for('complaints.admin_index'))

    complaint.status = status
    complaint.admin_response = response or None
    create_customer_notification(
        complaint.customer_id,
        f'Complaint {status}',
        f'Your complaint {complaint.complaint_number} is now marked as {status}.',
        event_type='Complaint Status Changed',
        category='complaint',
        link=url_for('complaints.view', complaint_id=complaint.id),
    )
    db.session.commit()

    flash(
        f'{complaint.complaint_number} updated successfully.',
        'success',
    )
    return redirect(
        url_for('complaints.admin_index', status=request.form.get('return_status', ''))
    )
