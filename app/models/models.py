from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(30), default='customer', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_roles = db.relationship('UserRole', backref='user', cascade='all, delete-orphan', lazy=True)




# class Customer(db.Model):
#     """Customer profile kept separate from staff/user access records."""
#     __tablename__ = 'customers'
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
#     full_name = db.Column(db.String(120), nullable=False)
#     email = db.Column(db.String(120), unique=True, nullable=False, index=True)
#     phone = db.Column(db.String(30), default='')
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    password = db.Column(db.String(200), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(80), default='Karachi')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __table_args__ = (db.UniqueConstraint('user_id', 'role', name='uq_user_role'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False, index=True)


class StaffRoleRequest(db.Model):
    """Administrator-controlled staff role assignment.

    A request is created against an email address first. The person may already
    have a customer account, or may register later. The role is not activated
    until the Administrator approves the request.
    """
    __tablename__ = 'staff_role_requests'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    requested_by_user = db.relationship('User', foreign_keys=[requested_by])
    assigned_user = db.relationship('User', foreign_keys=[user_id])


class Requirement(db.Model):
    __tablename__ = 'requirements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    property_type = db.Column(db.String(40), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    monthly_units = db.Column(db.Float, nullable=False)
    monthly_bill = db.Column(db.Float, nullable=False)
    roof_area = db.Column(db.Float, nullable=False)
    system_type = db.Column(db.String(30), nullable=False)
    backup_hours = db.Column(db.Float, default=0)
    budget = db.Column(db.String(80), default='Not specified')
    installation_date = db.Column(db.String(30), default='')
    recommended_kw = db.Column(db.Float, nullable=False)
    panel_count = db.Column(db.Integer, nullable=False)
    estimated_cost = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SolarPackage(db.Model):
    __tablename__ = 'solar_packages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    
    system_type_id = db.Column(db.Integer, db.ForeignKey('system_types.id'), nullable=True)
    capacity_kw = db.Column(db.Float, nullable=False)
    panels_info = db.Column(db.String(150), nullable=False)
    inverter_info = db.Column(db.String(150), nullable=False)
    battery_info = db.Column(db.String(150), default='Not included')
    description = db.Column(db.Text, default='')
    warranty_years = db.Column(db.Integer, default=10)
    price = db.Column(db.Float, nullable=False)


class Survey(db.Model):
    __tablename__ = 'surveys'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(80), default='Karachi')
    preferred_date = db.Column(db.String(30), nullable=False)
    preferred_time = db.Column(db.String(80), nullable=False)
    property_type = db.Column(db.String(40), default='Residential')
    contact_person = db.Column(db.String(120), default='')
    notes = db.Column(db.Text, default='')
    status = db.Column(db.String(40), default='Requested')
    engineer = db.Column(db.String(120), default='Unassigned')
    report_notes = db.Column(db.Text, default='')
    roof_area = db.Column(db.Float, default=0)
    roof_direction = db.Column(db.String(40), default='Not recorded')
    shading = db.Column(db.String(120), default='Not recorded')
    recommended_kw = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Quotation(db.Model):
    __tablename__ = 'quotations'
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'))
    requirement_id = db.Column(db.Integer, db.ForeignKey('requirements.id'))
    quotation_number = db.Column(db.String(40), unique=True, nullable=False)
    system_capacity_kw = db.Column(db.Float, nullable=False)
    system_type = db.Column(db.String(30), nullable=False)
    equipment_cost = db.Column(db.Float, nullable=False)
    installation_cost = db.Column(db.Float, nullable=False)
    transport_cost = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, nullable=False, default=0)
    final_amount = db.Column(db.Float, nullable=False)
    payment_terms = db.Column(db.String(120), default='30% advance, 50% before installation, 20% after completion')
    warranty_terms = db.Column(db.String(120), default='10 years equipment warranty')
    status = db.Column(db.String(40), default='Pending')
    customer_comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    survey = db.relationship('Survey', backref=db.backref('quotations', lazy=True))
    requirement = db.relationship('Requirement', backref=db.backref('quotations', lazy=True))


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    payment_type = db.Column(db.String(60), nullable=False)
    trx_ref = db.Column(db.String(100), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(40), default='Payment Verification Required')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    quotation = db.relationship('Quotation', backref=db.backref('payments', lazy=True))


class Installation(db.Model):
    __tablename__ = 'installations'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    team_lead = db.Column(db.String(120), default='Not Assigned')
    technician = db.Column(db.String(120), default='Not Assigned')
    status = db.Column(db.String(50), default='Project Created')
    capacity_kw = db.Column(db.Float, default=0)
    address = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    quotation = db.relationship('Quotation', backref=db.backref('installation', uselist=False))


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    brand = db.Column(db.String(80), default='Generic')
    model = db.Column(db.String(80), default='')
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    purchase_price = db.Column(db.Float, default=0)
    selling_price = db.Column(db.Float, default=0)
    supplier = db.Column(db.String(120), default='Local Supplier')
    warehouse = db.Column(db.String(120), default='Main Warehouse')
    warranty_years = db.Column(db.Integer, default=1)
    minimum_stock = db.Column(db.Integer, default=2)


class Warranty(db.Model):
    __tablename__ = 'warranties'
    id = db.Column(db.Integer, primary_key=True)
    component_name = db.Column(db.String(120), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    warranty_years = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), default='Active')
    claim_status = db.Column(db.String(40), default='No Claim')


class MaintenanceRequest(db.Model):
    __tablename__ = 'maintenance_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)




class SystemType(db.Model):
    __tablename__ = 'system_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True) # e.g. On-Grid, Off-Grid, Hybrid
    tagline = db.Column(db.String(150), nullable=True) # Short summary
    description = db.Column(db.Text, nullable=True)
    has_grid = db.Column(db.Boolean, default=True)
    requires_battery = db.Column(db.Boolean, default=False)
    provides_backup = db.Column(db.Boolean, default=False)
    supports_net_metering = db.Column(db.Boolean, default=False)

    # Relationship with packages
    packages = db.relationship('SolarPackage', backref='system_type_obj', lazy=True)

    # def __repr__(self):
    #     return f"<SystemType {self.name}>"