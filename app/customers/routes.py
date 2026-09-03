from flask import Blueprint, render_template, session
from flask_login import current_user,login_required
from app import db
from app.models import Requirement, Survey, Quotation, Installation
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

