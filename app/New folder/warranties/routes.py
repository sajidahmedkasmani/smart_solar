from flask import Blueprint, render_template, session
from app.models import Warranty
from app.auth.decorators import role_required

warranties_bp = Blueprint('warranties', __name__)


@warranties_bp.route('/')
@role_required('customer')
def list_warranties():
    # The current project model does not yet have a customer_id on warranties.
    # Keep the page restricted to customers/admins rather than exposing it to
    # arbitrary staff accounts.
    return render_template('warranty.html', warranties=Warranty.query.all())
