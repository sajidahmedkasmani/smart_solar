import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
from app import db
from app.models import Requirement, Survey, Quotation, Installation, Project, Payment
from app.auth.decorators import role_required


customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/dashboard')
@role_required('customer')
def dashboard():
    uid = session.get('user_id')
    latest_req = Requirement.query.filter_by(user_id=uid).order_by(Requirement.id.desc()).first()
    latest_survey = Survey.query.filter_by(user_id=uid).order_by(Survey.id.desc()).first()
    quotations = (Quotation.query
                  .outerjoin(Survey, Quotation.survey_id == Survey.id)
                  .outerjoin(Requirement, Quotation.requirement_id == Requirement.id)
                  .filter(db.or_(Survey.user_id == uid, Requirement.user_id == uid))
                  .order_by(Quotation.id.desc()).all())
    quotation_ids = [q.id for q in quotations]
    projects = (Installation.query.filter(Installation.quotation_id.in_(quotation_ids)).order_by(Installation.id.desc()).all()
                if quotation_ids else [])
    return render_template('landing_page/customer/user_dashboard.html', latest_req=latest_req, latest_survey=latest_survey,
                           quotations=quotations, projects=projects)



# @customers_bp.route('/surveys')
# @role_required('customer')
# def cust_surveys():
#     # uid = session.get('user_id')
#     # latest_req = Requirement.query.filter_by(user_id=uid).order_by(Requirement.id.desc()).first()
#     # latest_survey = Survey.query.filter_by(user_id=uid).order_by(Survey.id.desc()).first()
#     # quotations = (Quotation.query
#     #               .outerjoin(Survey, Quotation.survey_id == Survey.id)
#     #               .outerjoin(Requirement, Quotation.requirement_id == Requirement.id)
#     #               .filter(db.or_(Survey.user_id == uid, Requirement.user_id == uid))
#     #               .order_by(Quotation.id.desc()).all())
#     # quotation_ids = [q.id for q in quotations]
#     # projects = (Installation.query.filter(Installation.quotation_id.in_(quotation_ids)).order_by(Installation.id.desc()).all()
#     #             if quotation_ids else [])
#     # return render_template('landing_page/customer/user_dashboard.html', latest_req=latest_req, latest_survey=latest_survey,
#     #                        quotations=quotations, projects=projects)

#     return render_template('landing_page/customer/cust_surveys.html')


# @customers_bp.route('/surveys')
# @login_required
# @role_required('customer')
# def cust_surveys():
#     # Sirf current logged-in customer ke surveys fetch karein
#     user_surveys = Survey.query.filter_by(user_id=current_user.id)\
#                                .order_by(Survey.created_at.desc())\
#                                .all()
    
#     return render_template('landing_page/customer/cust_surveys.html', surveys=user_surveys)

@customers_bp.route('/surveys')
@role_required('customer')
def cust_surveys():

    uid = session.get('user_id')

    user_surveys = (
        Survey.query
        .filter_by(user_id=uid)
        .order_by(Survey.created_at.desc())
        .all()
    )

    return render_template(
        'landing_page/customer/cust_surveys.html',
        surveys=user_surveys
    )





# @customers_bp.route('/payment/<int:payment_id>', methods=['GET'])
# @role_required('customer')
# def make_payment(payment_id):
#     payment = Payment.query.get_or_404(payment_id)
#     return render_template('customer/make_payment.html', payment=payment)


# 1. Customer Projects Page Route
@customers_bp.route('/projects')
@role_required('customer')
def view_projects():
    # Customer ke sare active projects fetch karein (payments aur quotation ke sath)
    uid = session.get('user_id')

    projects = Project.query.filter_by(customer_id=uid).order_by(Project.created_at.desc()).all()
    return render_template('landing_page/customer/projects.html', projects=projects)


@customers_bp.route('/payment/<int:payment_id>', methods=['GET', 'POST'])
@role_required('customer')
def make_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    
    if request.method == 'POST':
        file = request.files.get('receipt')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'receipts')
            os.makedirs(upload_path, exist_ok=True)
            
            saved_filename = f"receipt_{payment.id}_{filename}"
            file.save(os.path.join(upload_path, saved_filename))
            
            payment.receipt_file = f"uploads/receipts/{saved_filename}"
            payment.payment_method = request.form.get('payment_method', 'Bank Transfer')
            payment.status = 'Verification Required'
            db.session.commit()
            
            flash('Payment receipt uploaded successfully!', 'success')
            return redirect(url_for('customers.view_projects'))
            
    return render_template('landing_page/customer/make_payment.html', payment=payment)
    payment = Payment.query.get_or_404(payment_id)
    
    # Ownership Check
    if payment.project.customer_id != current_user.id:
        flash('Unauthorized access to payment record.', 'danger')
        return redirect(url_for('customers.view_projects'))

    if 'receipt' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('customers.view_projects'))

    file = request.files['receipt']
    
    if file.filename == '':
        flash('Please select a payment receipt file to upload.', 'warning')
        return redirect(url_for('customers.view_projects'))

    if file:
        # File extension verification & secure save
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if ext not in ['jpg', 'jpeg', 'png', 'pdf']:
            flash('Only JPG, PNG, and PDF files are allowed.', 'danger')
            return redirect(url_for('customers.view_projects'))

        # Unique filename generation
        unique_filename = f"payment_{payment.id}_{int(datetime.utcnow().timestamp())}.{ext}"
        
        # Save to uploads folder
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'receipts')
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, unique_filename))

        # Update Payment Record
        payment.receipt_file = f"uploads/receipts/{unique_filename}"
        payment.payment_method = request.form.get('payment_method', 'Bank Transfer')
        payment.status = 'Verification Required'
        
        db.session.commit()

        flash('Payment receipt uploaded successfully! Finance team is verifying it.', 'success')

    return redirect(url_for('customers.view_projects'))