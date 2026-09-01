from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Inventory
from app.auth.decorators import role_required

inventory_bp=Blueprint('inventory',__name__)

@inventory_bp.route('/')
@role_required('inventory_manager')
def stock():
    items = Inventory.query.all()
    low_stock = [i for i in items if i.quantity <= i.minimum_stock]
    return render_template('inventory_list.html', items=items, low_stock=low_stock)

@inventory_bp.route('/add', methods=['GET','POST'])
@role_required('inventory_manager')
def add_item():
    if request.method=='POST':
        item=Inventory(item_name=request.form['item_name'],category=request.form['category'],brand=request.form.get('brand','Generic'),model=request.form.get('model',''),quantity=int(request.form['quantity']),selling_price=float(request.form.get('selling_price',0) or 0),purchase_price=float(request.form.get('purchase_price',0) or 0),supplier=request.form.get('supplier','Local Supplier'),minimum_stock=int(request.form.get('minimum_stock',2) or 2))
        db.session.add(item); db.session.commit(); flash('Inventory item added.','success'); return redirect(url_for('inventory.stock'))
    return render_template('inventory_add.html')

@inventory_bp.route('/stock')
@role_required('inventory_manager')
def stock_alias(): return stock()

@inventory_bp.route('/adjust/<int:item_id>', methods=['POST'])
@role_required('inventory_manager')
def adjust_quantity(item_id):
    item = Inventory.query.get_or_404(item_id)
    try:
        item.quantity = int(request.form.get('quantity', item.quantity))
    except ValueError:
        pass
    db.session.commit(); flash(f'Stock for {item.item_name} updated.', 'success')
    return redirect(url_for('inventory.stock'))
