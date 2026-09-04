from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Inventory, Supplier, PurchaseOrder, ProjectAssignment, DamagedItem
from app.auth.decorators import role_required

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/')
@role_required('inventory_manager')
def stock():
    items = Inventory.query.all()
    low_stock = [i for i in items if i.quantity <= i.minimum_stock]
    suppliers = Supplier.query.all()
    purchases = PurchaseOrder.query.order_by(PurchaseOrder.purchase_date.desc()).all()
    assignments = ProjectAssignment.query.order_by(ProjectAssignment.assigned_date.desc()).all()
    damaged = DamagedItem.query.order_by(DamagedItem.reported_date.desc()).all()

    return render_template(
        'admin/inventory/inventory_list.html', 
        items=items, 
        low_stock=low_stock,
        suppliers=suppliers,
        purchases=purchases,
        assignments=assignments,
        damaged=damaged
    )

@inventory_bp.route('/add', methods=['GET','POST'])
@role_required('inventory_manager')
def add_item():
    if request.method == 'POST':
        item = Inventory(
            item_name=request.form['item_name'],
            category=request.form['category'],
            brand=request.form.get('brand','Generic'),
            model=request.form.get('model',''),
            quantity=int(request.form.get('quantity', 0)),
            selling_price=float(request.form.get('selling_price',0) or 0),
            purchase_price=float(request.form.get('purchase_price',0) or 0),
            supplier=request.form.get('supplier','Local Supplier'),
            warranty_years=int(request.form.get('warranty_years', 1) or 1),
            minimum_stock=int(request.form.get('minimum_stock',2) or 2)
        )
        db.session.add(item)
        db.session.commit()
        flash('Equipment added to catalog.', 'success')
        return redirect(url_for('inventory.stock'))
    return render_template('inventory_add.html')

# 1. Record Purchase (Stock Increases Automatically)
@inventory_bp.route('/record-purchase', methods=['POST'])
@role_required('inventory_manager')
def record_purchase():
    inventory_id = int(request.form['inventory_id'])
    quantity = int(request.form['quantity'])
    unit_cost = float(request.form['unit_cost'])
    supplier_id = request.form.get('supplier_id')
    invoice = request.form.get('invoice_number', '')

    item = Inventory.query.get_or_404(inventory_id)
    item.quantity += quantity # Stock increase

    purchase = PurchaseOrder(
        inventory_id=inventory_id,
        supplier_id=supplier_id if supplier_id else None,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=quantity * unit_cost,
        invoice_number=invoice
    )
    db.session.add(purchase)
    db.session.commit()
    flash(f'Purchase recorded! Added {quantity} units to {item.item_name}.', 'success')
    return redirect(url_for('inventory.stock'))

# 2. Assign Equipment to Projects (Stock Deducts Automatically)
@inventory_bp.route('/assign-project', methods=['POST'])
@role_required('inventory_manager')
def assign_project():
    inventory_id = int(request.form['inventory_id'])
    quantity = int(request.form['quantity'])
    project_name = request.form['project_name']

    item = Inventory.query.get_or_404(inventory_id)
    if item.quantity < quantity:
        flash(f'Insufficient stock! Available: {item.quantity}', 'danger')
        return redirect(url_for('inventory.stock'))

    item.quantity -= quantity # Stock deduct

    assignment = ProjectAssignment(
        inventory_id=inventory_id,
        project_name=project_name,
        quantity_assigned=quantity,
        notes=request.form.get('notes', '')
    )
    db.session.add(assignment)
    db.session.commit()
    flash(f'Assigned {quantity} units of {item.item_name} to {project_name}.', 'success')
    return redirect(url_for('inventory.stock'))

# 3. Manage Damaged Equipment (Deducts stock & logs reason)
@inventory_bp.route('/report-damaged', methods=['POST'])
@role_required('inventory_manager')
def report_damaged():
    inventory_id = int(request.form['inventory_id'])
    quantity = int(request.form['quantity'])
    reason = request.form['reason']

    item = Inventory.query.get_or_404(inventory_id)
    if item.quantity < quantity:
        flash(f'Cannot report more than available stock ({item.quantity}).', 'danger')
        return redirect(url_for('inventory.stock'))

    item.quantity -= quantity # Deduct damaged stock

    damaged = DamagedItem(
        inventory_id=inventory_id,
        quantity_damaged=quantity,
        reason=reason
    )
    db.session.add(damaged)
    db.session.commit()
    flash(f'Recorded {quantity} damaged units for {item.item_name}.', 'warning')
    return redirect(url_for('inventory.stock'))

# 4. Add Supplier
@inventory_bp.route('/add-supplier', methods=['POST'])
@role_required('inventory_manager')
def add_supplier():
    supplier = Supplier(
        name=request.form['name'],
        contact_person=request.form.get('contact_person'),
        phone=request.form.get('phone'),
        email=request.form.get('email'),
        address=request.form.get('address')
    )
    db.session.add(supplier)
    db.session.commit()
    flash('Supplier added successfully.', 'success')
    return redirect(url_for('inventory.stock'))

@inventory_bp.route('/adjust/<int:item_id>', methods=['POST'])
@role_required('inventory_manager')
def adjust_quantity(item_id):
    item = Inventory.query.get_or_404(item_id)
    try:
        item.quantity = int(request.form.get('quantity', item.quantity))
    except ValueError:
        pass
    db.session.commit()
    flash(f'Stock for {item.item_name} updated.', 'success')
    return redirect(url_for('inventory.stock'))