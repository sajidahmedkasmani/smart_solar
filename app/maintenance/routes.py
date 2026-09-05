from datetime import date, timedelta
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from app import db
from app.models import (
    MaintenanceRequest,
    MaintenancePlan,
    CustomerSubscription,
    User,
    Customer,
)
from app.auth.decorators import role_required, session_roles
from app.notifications.service import create_customer_notification

maintenance_bp = Blueprint('maintenance', __name__)

MAINTENANCE_STATUSES = [
    'Request Submitted',
    'Support Review',
    'Technician Assigned',
    'Visit Scheduled',
    'Inspection Completed',
    'Repair In Progress',
    'Resolved',
    'Customer Confirmation',
]

MAINTENANCE_CATEGORIES = [
    'Solar-panel cleaning',
    'Low power production',
    'Inverter error',
    'Battery problem',
    'Wiring problem',
    'Monitoring-system issue',
    'Breaker problem',
    'General inspection',
    'Warranty claim',
]


def _contract_number():
    return f"AMC-{date.today().year}-{uuid.uuid4().hex[:7].upper()}"


def _customer_id():
    return session.get('user_id')


def _customer_subscriptions():
    return (
        CustomerSubscription.query
        .filter_by(customer_id=_customer_id())
        .order_by(CustomerSubscription.id.desc())
        .all()
    )


@maintenance_bp.route('/', methods=['GET', 'POST'])
@role_required('customer')
def maintenance():
    if request.method == 'POST':
        issue_type = request.form.get('issue_type', '').strip()
        description = request.form.get('description', '').strip()
        if issue_type not in MAINTENANCE_CATEGORIES or not description:
            flash('Please select a valid service category and describe the issue.', 'warning')
            return redirect(url_for('maintenance.maintenance'))

        customer = Customer.query.get_or_404(_customer_id())
        r = MaintenanceRequest(
            customer_id=customer.id,
            customer_name=customer.full_name,
            service_type=issue_type,
            issue_description=description,
            status='Request Submitted',
        )
        db.session.add(r)
        db.session.flush()

        create_customer_notification(
            customer.id,
            'Maintenance request submitted',
            f'Your maintenance request #MNT-{r.id} has been submitted and is awaiting support review.',
            event_type='Maintenance Request Submitted',
            category='maintenance',
            link=url_for('maintenance.maintenance'),
        )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Maintenance request submission failed')
            flash('Unable to submit your maintenance request right now. Please try again.', 'danger')
            return redirect(url_for('maintenance.maintenance'))

        flash('Maintenance request submitted successfully.', 'success')
        return redirect(url_for('maintenance.maintenance'))

    requests = (
        MaintenanceRequest.query
        .filter_by(customer_id=_customer_id())
        .order_by(MaintenanceRequest.id.desc())
        .all()
    )
    return render_template(
        'maintenance.html',
        maintenance_requests=requests,
        maintenance_categories=MAINTENANCE_CATEGORIES,
    )


@maintenance_bp.route('/list', methods=['GET', 'POST'])
@role_required('customer')
def list_requests():
    return maintenance()


@maintenance_bp.route('/confirm/<int:request_id>', methods=['POST'])
@role_required('customer')
def customer_confirm(request_id):
    r = MaintenanceRequest.query.filter_by(
        id=request_id,
        customer_id=_customer_id(),
    ).first_or_404()
    if r.status != 'Resolved':
        flash('This request can be confirmed after it is marked Resolved.', 'warning')
        return redirect(url_for('maintenance.maintenance'))

    r.status = 'Customer Confirmation'
    create_customer_notification(
        _customer_id(),
        'Maintenance request confirmed',
        f'You confirmed maintenance request #MNT-{r.id}. Thank you for confirming the service.',
        event_type='Maintenance Customer Confirmation',
        category='maintenance',
        link=url_for('maintenance.maintenance'),
    )
    db.session.commit()
    flash('Service completion confirmed.', 'success')
    return redirect(url_for('maintenance.maintenance'))


@maintenance_bp.route('/update/<int:request_id>', methods=['POST'])
@role_required('admin', 'technician', 'engineer')
def update_status(request_id):
    r = MaintenanceRequest.query.get_or_404(request_id)
    new_status = request.form.get('status', r.status)
    if new_status not in MAINTENANCE_STATUSES:
        flash('Invalid maintenance status.', 'danger')
        return redirect(url_for('maintenance.admin_requests'))

    r.status = new_status
    r.assigned_to = request.form.get('assigned_to', r.assigned_to or '').strip() or None
    visit_date = request.form.get('scheduled_visit', '').strip()
    if visit_date:
        try:
            from datetime import datetime
            r.scheduled_visit = datetime.fromisoformat(visit_date)
        except ValueError:
            flash('Invalid visit date/time.', 'warning')
            return redirect(url_for('maintenance.admin_requests'))
    notes = request.form.get('resolution_notes', '').strip()
    if notes:
        r.resolution_notes = notes

    recipient_id = r.customer_id
    if recipient_id:
        event_type = 'Maintenance Visit Scheduled' if new_status == 'Visit Scheduled' else 'Maintenance Status Changed'
        create_customer_notification(
            recipient_id,
            'Maintenance request updated',
            f'Your maintenance request #MNT-{r.id} status is now {new_status}.',
            event_type=event_type,
            category='maintenance',
            link=url_for('maintenance.maintenance'),
        )
    db.session.commit()
    flash('Maintenance request updated successfully.', 'success')

    roles = session_roles()
    if 'technician' in roles:
        return redirect(url_for('installations.technician_dashboard'))
    if 'engineer' in roles:
        return redirect(url_for('surveys.engineer_dashboard'))
    return redirect(url_for('maintenance.admin_requests'))


@maintenance_bp.route('/admin/requests')
@role_required('admin', 'technician', 'engineer')
def admin_requests():
    requests = MaintenanceRequest.query.order_by(MaintenanceRequest.id.desc()).all()
    return render_template(
        'admin/maintenance_requests.html',
        maintenance_requests=requests,
        maintenance_statuses=MAINTENANCE_STATUSES,
    )


@maintenance_bp.route('/plans')
@role_required('customer')
def plans():
    active_plans = (
        MaintenancePlan.query
        .filter_by(active=True)
        .order_by(MaintenancePlan.price.asc())
        .all()
    )
    subscriptions = _customer_subscriptions()
    active_contract = next(
        (s for s in subscriptions
         if s.status == 'Active' and s.end_date and s.end_date >= date.today()),
        None
    )
    return render_template(
        'maintenance_plans.html',
        plans=active_plans,
        subscriptions=subscriptions,
        active_contract=active_contract,
    )


@maintenance_bp.route('/checkout/<int:plan_id>', methods=['GET', 'POST'])
@role_required('customer')
def checkout(plan_id):
    plan = MaintenancePlan.query.filter_by(id=plan_id, active=True).first_or_404()

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', '').strip()
        if payment_method not in {'Card / Online Gateway', 'Bank Transfer'}:
            flash('Please select a valid payment method.', 'warning')
            return redirect(url_for('maintenance.checkout', plan_id=plan.id))

        # A new contract starts only after payment verification.
        subscription = CustomerSubscription(
            customer_id=session.get('user_id'),
            plan_id=plan.id,
            contract_number=_contract_number(),
            status='Pending Payment',
            payment_status='Payment Verification Required',
            payment_method=payment_method,
            transaction_reference=request.form.get('transaction_reference', '').strip() or None,
            amount=plan.price,
        )
        db.session.add(subscription)
        create_customer_notification(
            subscription.customer_id,
            'AMC order received',
            f'{plan.name} order {subscription.contract_number} is awaiting Finance payment verification.',
            event_type='AMC Purchase',
            category='maintenance',
            link=url_for('maintenance.my_contracts'),
        )
        db.session.commit()

        flash(
            'AMC order created. Payment is pending Finance verification; '
            'your contract will activate after approval.',
            'success',
        )
        return redirect(url_for('maintenance.my_contracts'))

    return render_template('maintenance_checkout.html', plan=plan)


@maintenance_bp.route('/renew/<int:subscription_id>', methods=['GET', 'POST'])
@role_required('customer')
def renew(subscription_id):
    old = CustomerSubscription.query.filter_by(
        id=subscription_id,
        customer_id=session.get('user_id')
    ).first_or_404()

    if old.status not in {'Active', 'Expired'}:
        flash('This contract is not eligible for renewal yet.', 'warning')
        return redirect(url_for('maintenance.my_contracts'))

    plan = old.plan
    if not plan.active:
        flash('The plan is no longer available for renewal.', 'warning')
        return redirect(url_for('maintenance.my_contracts'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', '').strip()
        if payment_method not in {'Card / Online Gateway', 'Bank Transfer'}:
            flash('Please select a valid payment method.', 'warning')
            return redirect(url_for('maintenance.renew', subscription_id=old.id))

        subscription = CustomerSubscription(
            customer_id=session.get('user_id'),
            plan_id=plan.id,
            contract_number=_contract_number(),
            status='Pending Payment',
            payment_status='Payment Verification Required',
            payment_method=payment_method,
            transaction_reference=request.form.get('transaction_reference', '').strip() or None,
            amount=plan.price,
            renewed_from_id=old.id,
        )
        db.session.add(subscription)
        create_customer_notification(
            subscription.customer_id,
            'AMC renewal received',
            f'Your {plan.name} renewal {subscription.contract_number} is awaiting Finance payment verification.',
            event_type='AMC Renewal',
            category='maintenance',
            link=url_for('maintenance.my_contracts'),
        )
        db.session.commit()
        flash('Renewal order submitted for Finance verification.', 'success')
        return redirect(url_for('maintenance.my_contracts'))

    return render_template('maintenance_renew.html', subscription=old, plan=plan)


@maintenance_bp.route('/contracts')
@role_required('customer')
def my_contracts():
    subscriptions = _customer_subscriptions()
    today = date.today()
    for subscription in subscriptions:
        if subscription.status == 'Active' and subscription.end_date and subscription.end_date < today:
            subscription.status = 'Expired'
    if any(s.status == 'Expired' for s in subscriptions):
        db.session.commit()

    return render_template(
        'maintenance_contracts.html',
        subscriptions=subscriptions,
        today=today,
    )


# --------------------------- Admin AMC Management ---------------------------

@maintenance_bp.route('/admin/plans')
@role_required('admin')
def admin_plans():
    plans = MaintenancePlan.query.order_by(MaintenancePlan.id.desc()).all()
    subscriptions = CustomerSubscription.query.order_by(CustomerSubscription.id.desc()).all()
    return render_template(
        'admin/maintenance_plans.html',
        plans=plans,
        subscriptions=subscriptions,
    )


@maintenance_bp.route('/admin/plans/create', methods=['POST'])
@role_required('admin')
def create_plan():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name or not description:
        flash('Plan name and description are required.', 'warning')
        return redirect(url_for('maintenance.admin_plans'))

    if MaintenancePlan.query.filter_by(name=name).first():
        flash('A plan with this name already exists.', 'warning')
        return redirect(url_for('maintenance.admin_plans'))

    plan = MaintenancePlan(
        name=name,
        description=description,
        visits_per_year=max(int(request.form.get('visits_per_year', 2)), 1),
        includes_cleaning='includes_cleaning' in request.form,
        includes_performance_check='includes_performance_check' in request.form,
        includes_emergency_support='includes_emergency_support' in request.form,
        includes_minor_repairs='includes_minor_repairs' in request.form,
        priority_visits='priority_visits' in request.form,
        price=max(float(request.form.get('price', 0)), 0),
        duration_months=12,
        active=True,
    )
    db.session.add(plan)
    db.session.commit()
    flash(f'{plan.name} created successfully.', 'success')
    return redirect(url_for('maintenance.admin_plans'))


@maintenance_bp.route('/admin/plans/<int:plan_id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_plan(plan_id):
    plan = MaintenancePlan.query.get_or_404(plan_id)
    plan.active = not plan.active
    db.session.commit()
    flash(f'{plan.name} is now {"active" if plan.active else "inactive"}.', 'success')
    return redirect(url_for('maintenance.admin_plans'))


@maintenance_bp.route('/admin/subscriptions/<int:subscription_id>/verify', methods=['POST'])
@role_required('admin', 'finance')
def verify_subscription(subscription_id):
    subscription = CustomerSubscription.query.get_or_404(subscription_id)
    action = request.form.get('action', 'approve')

    if action == 'reject':
        subscription.payment_status = 'Failed'
        subscription.status = 'Payment Failed'
        create_customer_notification(
            subscription.customer_id,
            'AMC payment not verified',
            f'Payment verification for AMC order {subscription.contract_number} was not approved.',
            event_type='Payment Verification',
            category='payment',
            link=url_for('maintenance.my_contracts'),
        )
        db.session.commit()
        flash('AMC payment was rejected.', 'warning')
        return redirect(url_for('maintenance.admin_plans'))

    today = date.today()
    # Renewal extends from the previous contract when possible; otherwise starts today.
    start = today
    if subscription.renewed_from and subscription.renewed_from.end_date:
        previous_end = subscription.renewed_from.end_date
        if previous_end >= today:
            start = previous_end + timedelta(days=1)

    subscription.start_date = start
    subscription.end_date = start + timedelta(days=365) - timedelta(days=1)
    subscription.payment_status = 'Paid'
    subscription.status = 'Active'
    create_customer_notification(
        subscription.customer_id,
        'AMC contract activated',
        f'Your {subscription.plan.name} AMC contract {subscription.contract_number} is now active.',
        event_type='AMC Activated',
        category='maintenance',
        link=url_for('maintenance.my_contracts'),
    )
    db.session.commit()
    flash(f'{subscription.contract_number} has been activated.', 'success')
    if 'finance' in session_roles() and 'admin' not in session_roles():
        return redirect(url_for('payments.finance_dashboard'))
    return redirect(url_for('maintenance.admin_plans'))
