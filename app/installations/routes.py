from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Installation, Quotation, Warranty, Project
from app.auth.decorators import role_required, session_roles
from app.notifications.service import create_customer_notification

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
    return render_template('landing_page/customer/installation_tracking.html', projects=projects)


@installations_bp.route('/schedule/<int:quote_id>', methods=['GET', 'POST'])
@role_required('admin')
def schedule(quote_id):
    q = Quotation.query.get_or_404(quote_id)
    if request.method == 'POST':
        inst = Installation(quotation_id=q.id, team_lead=request.form.get('team_lead', 'Not Assigned'),
                            technician=request.form.get('technician', 'Not Assigned'), capacity_kw=q.system_capacity_kw,
                            address=request.form.get('address', ''), status='Scheduled')
        db.session.add(inst)
        db.session.flush()
        customer_id = q.survey.user_id if q.survey else (q.requirement.user_id if q.requirement else None)
        if customer_id:
            create_customer_notification(
                customer_id,
                'Installation date confirmed',
                f'Your solar installation for {q.quotation_number} has been scheduled.',
                event_type='Installation Scheduled',
                category='installation',
                link=url_for('installations.list_installations'),
            )
        db.session.commit()
        flash('Installation scheduled!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('installation_tracking.html', projects=[q.installation] if q.installation else [])


@installations_bp.route('/updates/<int:installation_id>', methods=['POST'])
@role_required('admin', 'technician')
def update(installation_id):
    i = Installation.query.get_or_404(installation_id)
    if 'technician' in session_roles() and 'admin' not in session_roles() and i.technician != session.get('user_name'):
        flash('You can only update installations assigned to you.', 'danger')
        return redirect(url_for('installations.technician_dashboard'))
    old_status = i.status
    i.status = request.form.get('status', i.status)
    if 'admin' in session_roles():
        i.technician = request.form.get('technician', i.technician)
    if request.form.get('notes'):
        i.notes = request.form.get('notes')
    if i.status == 'Completed & Handover' and not Warranty.query.filter_by(serial_number=f'SE-PRJ-{i.id:05d}').first():
        db.session.add(Warranty(component_name='Solar Installation System', serial_number=f'SE-PRJ-{i.id:05d}',
                                warranty_years=10, start_date=date.today().isoformat()))
    q = i.quotation
    customer_id = q.survey.user_id if q and q.survey else (q.requirement.user_id if q and q.requirement else None)
    if customer_id and i.status != old_status:
        create_customer_notification(
            customer_id,
            'Installation stage updated',
            f'Your installation progress has moved to: {i.status}.',
            event_type='Installation Stage Changed',
            category='installation',
            link=url_for('installations.list_installations'),
        )
    db.session.commit()
    flash('Installation progress updated.', 'success')
    return redirect(url_for('installations.technician_dashboard') if 'technician' in session_roles() and 'admin' not in session_roles() else url_for('admin.dashboard'))


@installations_bp.route('/technician')
@role_required('technician')
def technician_dashboard():
    # User ID get karein (Name ki jagah ID se filter karna safe aur standard hai)
    uid = session.get('user_id') 
    
    # 1. Foreign Key (technician_id) se query karein
    # my_projects = Installation.query.filter_by(technician_id=uid).order_by(Installation.id.desc()).all()
    
    # Installation ki jagah Project query karein
    my_projects = Project.query.filter_by(technician_id=uid).order_by(Project.id.desc()).all()

    # 2. Status check Logic
    in_progress = [p for p in my_projects if p.status != 'Completed & Handover']
    completed = [p for p in my_projects if p.status == 'Completed & Handover']
    
    return render_template(
        'admin/technician_dashboard.html', 
        my_projects=my_projects, 
        unassigned=[],
        in_progress=in_progress, 
        completed=completed
    )



# @installations_bp.route('/update/<int:installation_id>', methods=['POST'])
# @role_required('technician')
# def tupdate(installation_id):
#     # Foreign key ya ID se installation get karein
#     installation = Installation.query.get_or_404(installation_id)
    
#     # Form data
#     new_status = request.form.get('status')
#     new_notes = request.form.get('notes')
    
#     if new_status:
#         installation.status = new_status
#     if new_notes is not None:
#         installation.notes = new_notes
        
#     db.session.commit()
#     flash('Installation status updated successfully!', 'success')
    
#     return redirect(url_for('installations.technician_dashboard'))


@installations_bp.route('/update/<int:installation_id>', methods=['POST'])
@role_required('technician')
def tupdate(installation_id):
    installation = Installation.query.get_or_404(installation_id)
    
    new_status = request.form.get('status')
    new_notes = request.form.get('notes')
    
    if new_status:
        installation.status = new_status
        
        # 1. Linked Project Status Sync
        # Agar Installation Quotation/Project se linked hai toh Project status bhi sync karein
        if hasattr(installation, 'quotation') and installation.quotation and hasattr(installation.quotation, 'project'):
            if installation.quotation.project:
                installation.quotation.project.status = new_status
                
    if new_notes is not None:
        installation.notes = new_notes
        
    db.session.commit()
    flash('Installation status updated successfully!', 'success')
    
    return redirect(url_for('installations.technician_dashboard'))
