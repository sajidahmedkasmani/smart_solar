from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Payment, Quotation, Installation, Warranty, Survey, Requirement
from app.auth.decorators import role_required

payments_bp = Blueprint('payments', __name__)


def _customer_quotations():
    uid = session.get('user_id')
    return (Quotation.query
            .outerjoin(Survey, Quotation.survey_id == Survey.id)
            .outerjoin(Requirement, Quotation.requirement_id == Requirement.id)
            .filter(db.or_(Survey.user_id == uid, Requirement.user_id == uid))
            .filter(Quotation.status.in_(['Approved', 'Payment Verification Required', 'Partially Paid', 'Fully Paid']))
            .order_by(Quotation.id.desc()).all())


@payments_bp.route('/', methods=['GET', 'POST'])
@payments_bp.route('/history', methods=['GET', 'POST'])
@role_required('customer')
def history():
    if request.method == 'POST':
        qid = int(request.form.get('quotation_id', 0))
        q = Quotation.query.get_or_404(qid)
        if q not in _customer_quotations():
            flash('You can only pay your own approved quotation.', 'danger')
            return redirect(url_for('payments.history'))
        payment_type = request.form.get('payment_type', 'Advance 30%')
        amount = q.final_amount * 0.30 if '30%' in payment_type else max(q.final_amount - sum(p.amount_paid for p in q.payments if p.status != 'Failed'), 0)
        p = Payment(
            quotation_id=q.id,
            payment_method=request.form.get('payment_method', 'Bank Transfer'),
            payment_type=payment_type,
            trx_ref=request.form.get('trx_ref', '').strip() or 'N/A',
            amount_paid=amount,
        )
        db.session.add(p)
        q.status = 'Payment Verification Required'
        db.session.commit()
        flash('Payment record submitted for Finance verification. Installation will be created after verification.', 'success')
    payments = (Payment.query.join(Quotation)
                .outerjoin(Survey, Quotation.survey_id == Survey.id)
                .outerjoin(Requirement, Quotation.requirement_id == Requirement.id)
                .filter(db.or_(Survey.user_id == session.get('user_id'), Requirement.user_id == session.get('user_id')))
                .order_by(Payment.id.desc()).all())
    approved = _customer_quotations()
    project = approved[0] if approved else None
    return render_template('payment.html', payments=payments, project=project, quotations=approved)


@payments_bp.route('/process/<int:project_id>', methods=['POST'])
@role_required('customer')
def process_payment(project_id):
    # Kept as the payment form endpoint for compatibility with the existing UI.
    return history()


@payments_bp.route('/finance')
@role_required('finance')
def finance_dashboard():
    payments = Payment.query.order_by(Payment.id.desc()).all()
    pending_verification = [p for p in payments if p.status == 'Payment Verification Required']
    verified = [p for p in payments if p.status != 'Payment Verification Required']
    total_revenue = sum(p.amount_paid for p in payments if p.status not in ('Failed', 'Payment Verification Required'))
    outstanding = sum(q.final_amount - sum(pp.amount_paid for pp in q.payments if pp.status != 'Failed') for q in Quotation.query.filter(Quotation.status.in_(['Approved', 'Partially Paid'])).all())
    return render_template('finance_dashboard.html', pending_verification=pending_verification, verified=verified,
                           total_revenue=total_revenue, outstanding=outstanding, payments=payments)


@payments_bp.route('/verify/<int:payment_id>', methods=['POST'])
@role_required('finance')
def verify_payment(payment_id):
    p = Payment.query.get_or_404(payment_id)
    action = request.form.get('action', 'verify')
    q = p.quotation
    if action == 'reject':
        p.status = 'Failed'
        q.status = 'Approved'
        flash('Payment marked as failed.', 'warning')
    else:
        p.status = 'Verified'
        paid_so_far = sum(pp.amount_paid for pp in q.payments if pp.status != 'Failed')
        q.status = 'Fully Paid' if paid_so_far >= q.final_amount else 'Partially Paid'
        if not q.installation:
            db.session.add(Installation(quotation_id=q.id, capacity_kw=q.system_capacity_kw, status='Project Created'))
        flash(f'Payment verified for {q.quotation_number}.', 'success')
    db.session.commit()
    return redirect(url_for('payments.finance_dashboard'))
