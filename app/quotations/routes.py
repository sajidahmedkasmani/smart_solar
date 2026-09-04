import io
import math
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
    send_file,
)

from app import db
from app.models import Requirement, Quotation, Survey
from app.auth.decorators import role_required

from app.models import Payment, Project, Quotation  # Project aur Payment models import kar lein

quotations_bp = Blueprint('quotations', __name__)


@quotations_bp.route('/calculator', methods=['GET', 'POST'])
@role_required('customer')
def calculator():
    result = None

    if request.method == 'POST':
        try:
            units = float(request.form['monthly_units'])
            bill = float(request.form['bill'])
            roof = float(request.form['roof_area'])

            if units <= 0 or bill < 0 or roof <= 0:
                raise ValueError

            daily = units / 30
            base_kw = daily / 5
            kw = round(max(base_kw * 1.20, 3.0), 1)

            panels = math.ceil(kw * 1000 / 550)
            cost = kw * 220000

            req = Requirement(
                user_id=session.get('user_id'),
                property_type=request.form.get(
                    'property_type',
                    'Residential'
                ),
                city=request.form.get(
                    'city',
                    'Karachi'
                ),
                monthly_units=units,
                monthly_bill=bill,
                roof_area=roof,
                system_type=request.form.get(
                    'system_type',
                    'Hybrid'
                ),
                backup_hours=float(
                    request.form.get('backup_hours', 0) or 0
                ),
                budget=request.form.get(
                    'budget',
                    'Not specified'
                ),
                installation_date=request.form.get(
                    'installation_date',
                    ''
                ),
                recommended_kw=kw,
                panel_count=panels,
                estimated_cost=cost,
            )

            db.session.add(req)
            db.session.commit()

            result = {
                'daily_units': round(daily, 2),
                'kw': kw,
                'panels': panels,
                'cost': cost,
            }

        except (ValueError, KeyError):
            flash(
                'Please enter valid numeric values.',
                'danger'
            )

    return render_template(
        'requirement_form.html',
        result=result
    )


@quotations_bp.route('/')
@role_required('customer')
def list_quotations():
    uid = session.get('user_id')

    quotations = (
        Quotation.query
        .outerjoin(
            Survey,
            Quotation.survey_id == Survey.id
        )
        .outerjoin(
            Requirement,
            Quotation.requirement_id == Requirement.id
        )
        .filter(
            db.or_(
                Survey.user_id == uid,
                Requirement.user_id == uid
            )
        )
        .order_by(Quotation.id.desc())
        .all()
    )

    return render_template(
        'admin/quotation.html',
        quotations=quotations
    )


@quotations_bp.route(
    '/generate/<int:survey_id>',
    methods=['GET', 'POST']
)
@role_required('sales')
def generate_quotation(survey_id):
    survey = Survey.query.get_or_404(survey_id)

    kw = survey.recommended_kw or 5

    equipment = kw * 170000
    install = kw * 25000
    transport = 20000
    tax = (equipment + install) * 0.05
    total = equipment + install + transport + tax

    q = Quotation(
        survey_id=survey.id,
        quotation_number=(
            f'QTN-2026-{Quotation.query.count() + 1:05d}'
        ),
        system_capacity_kw=kw,
        system_type='Hybrid',
        equipment_cost=equipment,
        installation_cost=install,
        transport_cost=transport,
        tax=tax,
        discount=0,
        final_amount=total,

        # Customer ko quotation bhejne ke baad
        # customer approval workflow start hota hai.
        status='Sent to Customer',
    )

    survey.status = 3

    db.session.add(q)
    db.session.commit()

    flash(
        'Quotation generated and sent to customer successfully.',
        'success'
    )

    return redirect(
        url_for('sales.dashboard')
    )


def _customer_owns_quotation(q):
    uid = session.get('user_id')

    survey_user = (
        q.survey.user_id
        if q.survey
        else None
    )

    req_user = (
        q.requirement.user_id
        if q.requirement
        else None
    )

    return uid in (survey_user, req_user)


def _quotation_awaiting_customer_decision(q):
    """
    Customer decision sirf in dono statuses par allowed hai.
    Existing quotations ke liye Pending bhi support rahega.
    """
    return q.status in (
        'Pending',
        'Sent to Customer'
    )


# =========================================================
# Customer - Approve Quotation
# =========================================================

@quotations_bp.route(
    '/approve/<int:quotation_id>',
    methods=['POST']
)
@role_required('customer')
def approve(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only approve your own quotation.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    if not _quotation_awaiting_customer_decision(q):
        flash(
            'This quotation is not awaiting approval.',
            'warning'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    q.status = 'Approved'
    q.decision_reason = 'Quotation approved by customer.'
    q.decision_at = datetime.utcnow()

    # Contract is generated after quotation approval.
    q.contract_generated = True
    q.contract_accepted = False
    q.contract_accepted_at = None

    db.session.commit()

    flash(
        'Quotation approved. Your installation agreement is now available.',
        'success'
    )

    return redirect(
        url_for(
            'quotations.view_quotation',
            quotation_id=q.id
        )
    )


# =========================================================
# Customer - Hold Quotation
# =========================================================

@quotations_bp.route(
    '/hold/<int:quotation_id>',
    methods=['POST']
)
@role_required('customer')
def hold(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only hold your own quotation.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    if not _quotation_awaiting_customer_decision(q):
        flash(
            'This quotation is not awaiting approval.',
            'warning'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    reason = request.form.get(
        'hold_reason',
        ''
    ).strip()

    q.status = 'On Hold'
    q.decision_reason = (
        reason
        or 'Quotation placed on hold by customer.'
    )
    q.decision_at = datetime.utcnow()

    db.session.commit()

    flash(
        'Quotation has been placed on hold.',
        'warning'
    )

    return redirect(
        url_for('quotations.list_quotations')
    )


# =========================================================
# Customer - Reject / Request Quotation Changes
# =========================================================

@quotations_bp.route(
    '/reject/<int:quotation_id>',
    methods=['POST']
)
@role_required('customer')
def reject(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only reject your own quotation.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    if not _quotation_awaiting_customer_decision(q):
        flash(
            'This quotation is not awaiting approval.',
            'warning'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    reason = request.form.get(
        'reject_reason',
        ''
    ).strip()

    if not reason:
        flash(
            'A rejection reason is required.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    changes_requested = request.form.get(
        'changes_requested',
        ''
    ).strip()

    # Only the limited quotation fields below can be requested
    # for change by the customer.
    requested_capacity = request.form.get(
        'requested_system_capacity_kw',
        ''
    ).strip()

    requested_system_type = request.form.get(
        'requested_system_type',
        ''
    ).strip()

    requested_equipment_cost = request.form.get(
        'requested_equipment_cost',
        ''
    ).strip()

    requested_installation_cost = request.form.get(
        'requested_installation_cost',
        ''
    ).strip()

    # Existing quotation values remain untouched.
    # Requested values are stored separately for sales review.

    if requested_capacity:
        try:
            requested_capacity_value = float(
                requested_capacity
            )

            if requested_capacity_value <= 0:
                raise ValueError

            q.requested_system_capacity_kw = (
                requested_capacity_value
            )

        except ValueError:
            flash(
                'Invalid requested system capacity.',
                'danger'
            )
            return redirect(
                url_for('quotations.list_quotations')
            )

    if requested_equipment_cost:
        try:
            requested_equipment_cost_value = float(
                requested_equipment_cost
            )

            if requested_equipment_cost_value < 0:
                raise ValueError

            q.requested_equipment_cost = (
                requested_equipment_cost_value
            )

        except ValueError:
            flash(
                'Invalid requested equipment cost.',
                'danger'
            )
            return redirect(
                url_for('quotations.list_quotations')
            )

    if requested_installation_cost:
        try:
            requested_installation_cost_value = float(
                requested_installation_cost
            )

            if requested_installation_cost_value < 0:
                raise ValueError

            q.requested_installation_cost = (
                requested_installation_cost_value
            )

        except ValueError:
            flash(
                'Invalid requested installation cost.',
                'danger'
            )
            return redirect(
                url_for('quotations.list_quotations')
            )

    if requested_system_type:
        allowed_system_types = {
            'On-Grid',
            'Off-Grid',
            'Hybrid'
        }

        if requested_system_type not in allowed_system_types:
            flash(
                'Invalid system type requested.',
                'danger'
            )
            return redirect(
                url_for('quotations.list_quotations')
            )

        q.requested_system_type = requested_system_type

    q.status = 'Rejected'
    q.decision_reason = reason
    q.decision_at = datetime.utcnow()

    q.revision_requested = bool(
        changes_requested
        or requested_capacity
        or requested_system_type
        or requested_equipment_cost
        or requested_installation_cost
    )

    if q.revision_requested:
        q.revision_status = 'Pending'

        # Customer ka actual reason + requested changes
        # sales review ke liye save kar rahe hain.
        if changes_requested:
            q.revision_reason = (
                f'{reason}\n\n'
                f'Requested Changes:\n'
                f'{changes_requested}'
            )
        else:
            q.revision_reason = reason

    else:
        q.revision_status = ''
        q.revision_reason = ''

    db.session.commit()

    if q.revision_requested:
        flash(
            'Quotation rejected and your requested changes have been sent to the sales team.',
            'warning'
        )
    else:
        flash(
            'Quotation rejected.',
            'warning'
        )

    return redirect(
        url_for('quotations.list_quotations')
    )


# =========================================================
# Customer - View Complete Quotation
# =========================================================

# =========================================================
# Customer - View Complete Quotation
# =========================================================

@quotations_bp.route(
    '/view/<int:quotation_id>'
)
@role_required('customer')
def view_quotation(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only view your own quotation.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    return render_template(
    'admin/quotation_detail.html',
    quotation=q
)


# =========================================================
# Customer - Installation Agreement
# =========================================================

@quotations_bp.route(
    '/contract/<int:quotation_id>'
)
@role_required('customer')
def contract(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only view your own agreement.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    if q.status != 'Approved':
        flash(
            'The installation agreement is only available after quotation approval.',
            'warning'
        )
        return redirect(
            url_for(
                'quotations.view_quotation',
                quotation_id=q.id
            )
        )

    return render_template(
    'admin/installation_agreement.html',
    q=q
)


# @quotations_bp.route(
#     '/contract/accept/<int:quotation_id>',
#     methods=['POST']
# )
# @role_required('customer')
# def accept_contract(quotation_id):
#     q = Quotation.query.get_or_404(quotation_id)

#     if not _customer_owns_quotation(q):
#         flash(
#             'You can only accept your own agreement.',
#             'danger'
#         )
#         return redirect(
#             url_for('quotations.list_quotations')
#         )

#     if q.status != 'Approved':
#         flash(
#             'Quotation must be approved before accepting the agreement.',
#             'warning'
#         )
#         return redirect(
#             url_for(
#                 'quotations.view_quotation',
#                 quotation_id=q.id
#             )
#         )

#     q.contract_generated = True
#     q.contract_accepted = True
#     q.contract_accepted_at = datetime.utcnow()

#     db.session.commit()

#     flash(
#         'Installation agreement accepted successfully.',
#         'success'
#     )

#     return redirect(
#         url_for('quotations.list_quotations')
#     )





@quotations_bp.route('/contract/accept/<int:quotation_id>', methods=['POST'])
@role_required('customer')
def accept_contract(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash('You can only accept your own agreement.', 'danger')
        return redirect(url_for('quotations.list_quotations'))

    if q.status != 'Approved':
        flash('Quotation must be approved before accepting the agreement.', 'warning')
        return redirect(url_for('quotations.view_quotation', quotation_id=q.id))

    # 1. Update Quotation Status
    q.contract_generated = True
    q.contract_accepted = True
    q.contract_accepted_at = datetime.utcnow()
    q.status = 'Contract Signed'

    # 2. Check if Project already exists, agar nahi toh create karein
    project = Project.query.filter_by(quotation_id=q.id).first()
    if not project:
        project = Project(
            quotation_id=q.id,
            customer_id=q.survey.user_id if q.survey else current_user.id,
            project_name=f"Solar System - {q.quotation_number}",
            status='Pending Advance'
        )
        db.session.add(project)
        db.session.flush()  # Project ID generate karne ke liye

    # 3. Automatic 30% Advance Payment Milestone
    advance_payment = Payment.query.filter_by(project_id=project.id, milestone_name='30% Advance Payment').first()
    if not advance_payment:
        advance_amount = q.final_amount * 0.30
        advance_payment = Payment(
            project_id=project.id,
            milestone_name='30% Advance Payment',
            amount=advance_amount,
            status='Pending'
        )
        db.session.add(advance_payment)

    db.session.commit()

    flash('Installation agreement accepted! Project initialized. Please submit your 30% advance payment to proceed.', 'success')
    
    # Redirect customer directly to Payment Upload Page
    return redirect(url_for('customer.make_payment', payment_id=advance_payment.id))


# =========================================================
# Sales - View Revision Requests
# =========================================================

@quotations_bp.route(
    '/sales/review'
)
@role_required('sales')
def sales_review():
    quotations = (
        Quotation.query
        .filter(
            Quotation.revision_requested.is_(True),
            Quotation.revision_status == 'Pending'
        )
        .order_by(Quotation.id.desc())
        .all()
    )

    return render_template(
        'sales/quotation_review.html',
        quotations=quotations
    )


# =========================================================
# Sales - Accept Requested Changes
# =========================================================

@quotations_bp.route(
    '/sales/review/<int:quotation_id>/accept',
    methods=['POST']
)
@role_required('sales')
def sales_accept_revision(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not q.revision_requested:
        flash(
            'No revision request exists for this quotation.',
            'warning'
        )
        return redirect(
            url_for('quotations.sales_review')
        )

    # Apply ONLY the customer-editable fields.
    if q.requested_system_capacity_kw is not None:
        q.system_capacity_kw = (
            q.requested_system_capacity_kw
        )

    if q.requested_system_type:
        q.system_type = q.requested_system_type

    if q.requested_equipment_cost is not None:
        q.equipment_cost = (
            q.requested_equipment_cost
        )

    if q.requested_installation_cost is not None:
        q.installation_cost = (
            q.requested_installation_cost
        )

    # Recalculate quotation after approved changes.
    equipment = q.equipment_cost or 0
    installation = q.installation_cost or 0
    transport = q.transport_cost or 0
    discount = q.discount or 0

    # Tax is recalculated according to the
    # updated equipment + installation cost.
    q.tax = (
        equipment + installation
    ) * 0.05

    q.final_amount = (
        equipment
        + installation
        + transport
        + q.tax
        - discount
    )

    q.revision_status = 'Accepted'

    q.sales_review_reason = (
        request.form.get(
            'sales_review_reason',
            'Requested quotation changes accepted by sales.'
        ).strip()
    )

    q.sales_review_at = datetime.utcnow()

    # Send quotation back to customer for approval.
    q.status = 'Sent to Customer'

    # Reset customer decision state.
    q.decision_reason = ''
    q.decision_at = None

    # New quotation is again waiting for customer decision.
    q.contract_generated = False
    q.contract_accepted = False
    q.contract_accepted_at = None

    db.session.commit()

    flash(
        'Requested quotation changes have been accepted and the quotation has been sent back to the customer.',
        'success'
    )

    return redirect(
        url_for('quotations.sales_review')
    )


# =========================================================
# Sales - Reject Requested Changes
# =========================================================

@quotations_bp.route(
    '/sales/review/<int:quotation_id>/reject',
    methods=['POST']
)
@role_required('sales')
def sales_reject_revision(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not q.revision_requested:
        flash(
            'No revision request exists for this quotation.',
            'warning'
        )
        return redirect(
            url_for('quotations.sales_review')
        )

    reason = request.form.get(
        'sales_review_reason',
        ''
    ).strip()

    if not reason:
        flash(
            'A reason is required when rejecting the requested changes.',
            'danger'
        )
        return redirect(
            url_for('quotations.sales_review')
        )

    q.revision_status = 'Rejected'

    q.sales_review_reason = reason

    q.sales_review_at = datetime.utcnow()

    # The original quotation remains unchanged.
    q.status = 'Rejected'

    db.session.commit()

    flash(
        'The requested quotation changes were rejected.',
        'warning'
    )

    return redirect(
        url_for('quotations.sales_review')
    )


# =========================================================
# PDF
# =========================================================

@quotations_bp.route(
    '/pdf/<int:quotation_id>'
)
@role_required('customer')
def pdf(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)

    if not _customer_owns_quotation(q):
        flash(
            'You can only download your own quotation.',
            'danger'
        )
        return redirect(
            url_for('quotations.list_quotations')
        )

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()

        c = canvas.Canvas(
            buf,
            pagesize=A4
        )

        y = 800

        c.setFont(
            'Helvetica-Bold',
            20
        )

        c.drawString(
            50,
            y,
            'SolarEase'
        )

        y -= 35

        c.setFont(
            'Helvetica-Bold',
            14
        )

        c.drawString(
            50,
            y,
            f'Quotation {q.quotation_number}'
        )

        y -= 30

        c.setFont(
            'Helvetica',
            11
        )

        rows = [
            (
                'System',
                f'{q.system_capacity_kw} kW {q.system_type}'
            ),
            (
                'Equipment Cost',
                f'PKR {q.equipment_cost:,.0f}'
            ),
            (
                'Installation',
                f'PKR {q.installation_cost:,.0f}'
            ),
            (
                'Transport',
                f'PKR {q.transport_cost:,.0f}'
            ),
            (
                'Tax',
                f'PKR {q.tax:,.0f}'
            ),
            (
                'Discount',
                f'PKR {q.discount:,.0f}'
            ),
            (
                'Final Amount',
                f'PKR {q.final_amount:,.0f}'
            ),
            (
                'Payment Terms',
                q.payment_terms
            ),
            (
                'Warranty',
                q.warranty_terms
            ),
        ]

        for label, value in rows:

            c.drawString(
                60,
                y,
                label + ':'
            )

            c.drawString(
                190,
                y,
                str(value)
            )

            y -= 24

        c.save()

        buf.seek(0)

        return send_file(
            buf,
            as_attachment=True,
            download_name=(
                f'{q.quotation_number}.pdf'
            ),
            mimetype='application/pdf'
        )

    except ImportError:

        html = render_template(
            'quotation_print.html',
            q=q
        )

        response = make_response(html)

        response.headers[
            'Content-Disposition'
        ] = (
            f'attachment; '
            f'filename={q.quotation_number}.html'
        )

        return response