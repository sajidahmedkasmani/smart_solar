import io
import math
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, send_file
from app import db
from app.models import Requirement, Quotation, Survey
from app.auth.decorators import role_required

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
                property_type=request.form.get('property_type', 'Residential'),
                city=request.form.get('city', 'Karachi'),
                monthly_units=units,
                monthly_bill=bill,
                roof_area=roof,
                system_type=request.form.get('system_type', 'Hybrid'),
                backup_hours=float(request.form.get('backup_hours', 0) or 0),
                budget=request.form.get('budget', 'Not specified'),
                installation_date=request.form.get('installation_date', ''),
                recommended_kw=kw,
                panel_count=panels,
                estimated_cost=cost,
            )
            db.session.add(req)
            db.session.commit()
            result = {'daily_units': round(daily, 2), 'kw': kw, 'panels': panels, 'cost': cost}
        except (ValueError, KeyError):
            flash('Please enter valid numeric values.', 'danger')
    return render_template('requirement_form.html', result=result)


@quotations_bp.route('/')
@role_required('customer')
def list_quotations():
    uid = session.get('user_id')
    quotations = (Quotation.query
                  .outerjoin(Survey, Quotation.survey_id == Survey.id)
                  .outerjoin(Requirement, Quotation.requirement_id == Requirement.id)
                  .filter(db.or_(Survey.user_id == uid, Requirement.user_id == uid))
                  .order_by(Quotation.id.desc()).all())
    return render_template('admin/quotation.html',quotations=quotations)


@quotations_bp.route('/generate/<int:survey_id>', methods=['GET', 'POST'])
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
        quotation_number=f'QTN-2026-{Quotation.query.count() + 1:05d}',
        system_capacity_kw=kw,
        system_type='Hybrid',
        equipment_cost=equipment,
        installation_cost=install,
        transport_cost=transport,
        tax=tax,
        discount=0,
        final_amount=total,
        status='Pending',
    )
    survey.status = 3
    db.session.add(q)
    db.session.commit()
    flash('Quotation generated successfully.', 'success')
    return redirect(url_for('sales.dashboard'))


def _customer_owns_quotation(q):
    uid = session.get('user_id')
    survey_user = q.survey.user_id if q.survey else None
    req_user = q.requirement.user_id if q.requirement else None
    return uid in (survey_user, req_user)


@quotations_bp.route('/approve/<int:quotation_id>', methods=['POST'])
@role_required('customer')
def approve(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)
    if not _customer_owns_quotation(q):
        flash('You can only approve your own quotation.', 'danger')
        return redirect(url_for('quotations.list_quotations'))
    if q.status != 'Pending':
        flash('This quotation is not awaiting approval.', 'warning')
        return redirect(url_for('quotations.list_quotations'))
    q.status = 'Approved'
    db.session.commit()
    flash('Quotation approved. Proceed to payment.', 'success')
    return redirect(url_for('payments.history'))


@quotations_bp.route('/reject/<int:quotation_id>', methods=['POST'])
@role_required('customer')
def reject(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)
    if not _customer_owns_quotation(q):
        flash('You can only reject your own quotation.', 'danger')
        return redirect(url_for('quotations.list_quotations'))
    q.status = 'Rejected'
    db.session.commit()
    flash('Quotation rejected.', 'warning')
    return redirect(url_for('quotations.list_quotations'))


@quotations_bp.route('/pdf/<int:quotation_id>')
@role_required('customer')
def pdf(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)
    if not _customer_owns_quotation(q):
        flash('You can only download your own quotation.', 'danger')
        return redirect(url_for('quotations.list_quotations'))
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        y = 800
        c.setFont('Helvetica-Bold', 20)
        c.drawString(50, y, 'SolarEase')
        y -= 35
        c.setFont('Helvetica-Bold', 14)
        c.drawString(50, y, f'Quotation {q.quotation_number}')
        y -= 30
        c.setFont('Helvetica', 11)
        rows = [
            ('System', f'{q.system_capacity_kw} kW {q.system_type}'),
            ('Equipment Cost', f'PKR {q.equipment_cost:,.0f}'),
            ('Installation', f'PKR {q.installation_cost:,.0f}'),
            ('Transport', f'PKR {q.transport_cost:,.0f}'),
            ('Tax', f'PKR {q.tax:,.0f}'),
            ('Discount', f'PKR {q.discount:,.0f}'),
            ('Final Amount', f'PKR {q.final_amount:,.0f}'),
            ('Payment Terms', q.payment_terms),
            ('Warranty', q.warranty_terms),
        ]
        for label, value in rows:
            c.drawString(60, y, label + ':')
            c.drawString(190, y, str(value))
            y -= 24
        c.save()
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f'{q.quotation_number}.pdf', mimetype='application/pdf')
    except ImportError:
        html = render_template('quotation_print.html', q=q)
        response = make_response(html)
        response.headers['Content-Disposition'] = f'attachment; filename={q.quotation_number}.html'
        return response
