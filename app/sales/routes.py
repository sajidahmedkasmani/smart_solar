from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import SolarPackage, Requirement, Survey, Quotation
from app.auth.decorators import role_required

sales_bp = Blueprint('sales', __name__)


@sales_bp.route('/packages')
@role_required('customer', 'sales')
def packages():
    return render_template('packages.html', packages=SolarPackage.query.all())


@sales_bp.route('/system-types')
@role_required('customer', 'sales')
def system_types():
    systems = [
        {'name': 'On-Grid', 'description': 'Connected to the electricity grid, normally without batteries. Suitable for bill reduction and net-metering documentation.', 'battery': 'No', 'grid': 'Yes', 'backup': 'No'},
        {'name': 'Off-Grid', 'description': 'Independent from the electricity grid and designed around battery storage for remote locations.', 'battery': 'Yes', 'grid': 'No', 'backup': 'Yes'},
        {'name': 'Hybrid', 'description': 'Grid-connected system with batteries that provides backup during outages.', 'battery': 'Yes', 'grid': 'Yes', 'backup': 'Yes'},
    ]
    return render_template('system_types.html', systems=systems)


@sales_bp.route('/dashboard')
@role_required('sales')
def dashboard():
    quoted_survey_ids = {q.survey_id for q in Quotation.query.filter(Quotation.survey_id.isnot(None)).all()}
    leads_surveys = [s for s in Survey.query.order_by(Survey.id.desc()).all() if s.id not in quoted_survey_ids and s.status in ('Survey Completed', 'Report Submitted')]
    leads_requirements = Requirement.query.order_by(Requirement.id.desc()).limit(15).all()
    quotations = Quotation.query.order_by(Quotation.id.desc()).all()
    pending_quotations = [q for q in quotations if q.status == 'Pending']
    approved_quotations = [q for q in quotations if q.status == 'Approved']
    rejected_quotations = [q for q in quotations if q.status == 'Rejected']
    total_leads = len(leads_surveys) + len(leads_requirements)
    conversion_rate = round((len(approved_quotations) / len(quotations) * 100), 1) if quotations else 0
    return render_template('sales_dashboard.html', leads_surveys=leads_surveys, leads_requirements=leads_requirements,
                           quotations=quotations, pending_quotations=pending_quotations,
                           approved_quotations=approved_quotations, rejected_quotations=rejected_quotations,
                           total_leads=total_leads, conversion_rate=conversion_rate)


@sales_bp.route('/discount/<int:quotation_id>', methods=['POST'])
@role_required('sales')
def apply_discount(quotation_id):
    q = Quotation.query.get_or_404(quotation_id)
    try:
        discount = max(float(request.form.get('discount', 0) or 0), 0)
    except ValueError:
        discount = 0
    subtotal = q.equipment_cost + q.installation_cost + q.transport_cost + q.tax
    q.discount = min(discount, subtotal)
    q.final_amount = subtotal - q.discount
    db.session.commit()
    flash(f'Discount of PKR {q.discount:,.0f} applied to {q.quotation_number}.', 'success')
    return redirect(url_for('sales.dashboard'))
