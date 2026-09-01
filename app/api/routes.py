from flask import Blueprint, jsonify
from app.models import SolarPackage, Quotation, Inventory
from app.auth.decorators import role_required

api_bp = Blueprint('api', __name__)


@api_bp.route('/v1/status')
def status():
    return jsonify(status='SolarEase API Online')


@api_bp.route('/v1/packages')
def packages():
    return jsonify([{'id': p.id, 'name': p.name, 'capacity_kw': p.capacity_kw,
                     'system_type': p.system_type, 'price': p.price} for p in SolarPackage.query.all()])


@api_bp.route('/v1/quotations')
@role_required('admin')
def quotations():
    return jsonify([{'id': q.id, 'number': q.quotation_number,
                     'status': q.status, 'amount': q.final_amount} for q in Quotation.query.all()])


@api_bp.route('/v1/inventory')
@role_required('admin', 'inventory_manager')
def inventory():
    return jsonify([{'id': i.id, 'name': i.item_name, 'quantity': i.quantity,
                     'low_stock': i.quantity <= i.minimum_stock} for i in Inventory.query.all()])
