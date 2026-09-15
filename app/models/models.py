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
    status = db.Column(db.Integer, default=1, nullable=False)



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
    status = db.Column(db.Integer, default=1, nullable=False)

    # Email verification (form signups only; Google sign-ups are pre-verified)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(64), nullable=True, index=True)
    verification_token_expires_at = db.Column(db.DateTime, nullable=True)


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __table_args__ = (db.UniqueConstraint('user_id', 'role', name='uq_user_role'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False, index=True)
    status = db.Column(db.Integer, default=1, nullable=False)


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
    status = db.Column(db.Integer, default=1, nullable=False)


# class Survey(db.Model):
#     __tablename__ = 'surveys'
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
#     customer_name = db.Column(db.String(120), nullable=False)
#     phone = db.Column(db.String(30), nullable=False)
#     address = db.Column(db.Text, nullable=False)
#     city = db.Column(db.String(80), default='Karachi')
#     preferred_date = db.Column(db.String(30), nullable=False)
#     preferred_time = db.Column(db.String(80), nullable=False)
#     property_type = db.Column(db.String(40), default='Residential')
#     contact_person = db.Column(db.String(120), default='')
#     notes = db.Column(db.Text, default='')
#     status = db.Column(db.String(40), default='Requested')
#     # engineer = db.Column(db.String(120), default='Unassigned')
#     report_notes = db.Column(db.Text, default='')
#     roof_area = db.Column(db.Float, default=0)
#     roof_direction = db.Column(db.String(40), default='Not recorded')
#     shading = db.Column(db.String(120), default='Not recorded')
#     recommended_kw = db.Column(db.Float, default=0)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

#     engineer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
#     # Relationship to easily access engineer object (e.g., survey.assigned_engineer.name)
#     assigned_engineer = db.relationship('User', foreign_keys=[engineer_id], backref='assigned_surveys')


# from datetime import datetime
# from app import db  # Ya jahan se aapka db instance import hota hai

class Survey(db.Model):
    __tablename__ = 'surveys'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )

    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(80), default='Karachi')

    preferred_date = db.Column(db.String(30), nullable=False)
    preferred_time = db.Column(db.String(80), nullable=False)

    property_type = db.Column(
        db.String(40),
        default='Residential'
    )

    contact_person = db.Column(
        db.String(120),
        default=''
    )

    notes = db.Column(
        db.Text,
        default=''
    )

    # STATUS
    # 0 = Pending Customer Approval
    # 1 = Scheduled / Assigned
    # 2 = In Progress
    # 3 = Completed
    # 4 = Cancelled
    # 5 = Pending Admin Assignment

    status = db.Column(
        db.Integer,
        default=5,
        nullable=False
    )

    rescheduled_by_admin = db.Column(
        db.Boolean,
        default=False
    )

    # Survey timing
    started_at = db.Column(
        db.DateTime,
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # Technical report
    report_notes = db.Column(
        db.Text,
        default=''
    )

    roof_area = db.Column(
        db.Float,
        default=0
    )

    roof_direction = db.Column(
        db.String(40),
        default='Not recorded'
    )

    shading = db.Column(
        db.String(120),
        default='Not recorded'
    )

    recommended_kw = db.Column(
        db.Float,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Assigned engineer
    engineer_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )

    assigned_engineer = db.relationship(
        'User',
        foreign_keys=[engineer_id],
        backref='assigned_surveys'
    )

    # Customer
    customer = db.relationship(
        'User',
        foreign_keys=[user_id],
        backref='my_surveys'
    )
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)

    # Staff notifications use user_id; customer notifications use customer_id.
    # Both are nullable so the customer and staff authentication tables can
    # remain separate without forcing a customer id into users.id.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey('customers.id'),
        nullable=True,
        index=True
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    # Module 23 notification metadata. These fields remain optional so
    # existing notifications created by older modules continue to work.
    category = db.Column(db.String(40), default='general')
    channel = db.Column(db.String(30), default='Dashboard')
    event_type = db.Column(db.String(80), default='General')
    link = db.Column(db.String(255), nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        'User',
        backref=db.backref(
            'notifications',
            lazy=True
        )
    )
    customer = db.relationship(
        'Customer',
        backref=db.backref('notifications', lazy=True)
    )


class SurveyImage(db.Model):
    __tablename__ = 'survey_images'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    survey_id = db.Column(
        db.Integer,
        db.ForeignKey('surveys.id'),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    image_type = db.Column(
        db.String(50),
        default='site'
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    survey = db.relationship(
        'Survey',
        backref=db.backref(
            'images',
            lazy=True,
            cascade='all, delete-orphan'
        )
    )

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
    # Customer quotation decision
    decision_reason = db.Column(db.Text, default='')
    decision_at = db.Column(db.DateTime, nullable=True)
    # Customer requested quotation changes
    revision_requested = db.Column(db.Boolean, default=False)
    revision_status = db.Column(db.String(30), default='')
    revision_reason = db.Column(db.Text, default='')
    # Customer-editable requested values
    requested_system_capacity_kw = db.Column(db.Float, nullable=True)
    requested_system_type = db.Column(db.String(30), nullable=True)
    requested_equipment_cost = db.Column(db.Float, nullable=True)
    requested_installation_cost = db.Column(db.Float, nullable=True)
    # Sales review of customer's requested changes
    sales_review_reason = db.Column(db.Text, default='')
    sales_review_at = db.Column(db.DateTime, nullable=True)
    # Contract / Agreement
    contract_generated = db.Column(db.Boolean, default=False)
    contract_accepted = db.Column(db.Boolean, default=False)
    contract_accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    survey = db.relationship('Survey', backref=db.backref('quotations', lazy=True))
    requirement = db.relationship('Requirement', backref=db.backref('quotations', lazy=True))


# class Payment(db.Model):
#     __tablename__ = 'payments'
#     id = db.Column(db.Integer, primary_key=True)
#     quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
#     payment_method = db.Column(db.String(50), nullable=False)
#     payment_type = db.Column(db.String(60), nullable=False)
#     trx_ref = db.Column(db.String(100), nullable=False)
#     amount_paid = db.Column(db.Float, nullable=False)
#     status = db.Column(db.String(40), default='Payment Verification Required')
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     quotation = db.relationship('Quotation', backref=db.backref('payments', lazy=True))


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


# class Inventory(db.Model):
#     __tablename__ = 'inventory'
#     id = db.Column(db.Integer, primary_key=True)
#     item_name = db.Column(db.String(120), nullable=False)
#     category = db.Column(db.String(60), nullable=False)
#     brand = db.Column(db.String(80), default='Generic')
#     model = db.Column(db.String(80), default='')
#     serial_number = db.Column(db.String(100), unique=True, nullable=True)
#     quantity = db.Column(db.Integer, nullable=False, default=0)
#     purchase_price = db.Column(db.Float, default=0)
#     selling_price = db.Column(db.Float, default=0)
#     supplier = db.Column(db.String(120), default='Local Supplier')
#     warehouse = db.Column(db.String(120), default='Main Warehouse')
#     warranty_years = db.Column(db.Integer, default=1)
#     minimum_stock = db.Column(db.Integer, default=2)




# Existing Inventory Model
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

# --- NEW INVENTORY MODULE MODELS ---

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    invoice_number = db.Column(db.String(80))
    
    inventory = db.relationship('Inventory', backref='purchases')
    supplier_rel = db.relationship('Supplier', backref='purchases')

class ProjectAssignment(db.Model):
    __tablename__ = 'project_assignments'
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    project_name = db.Column(db.String(120), nullable=False) # e.g. Site SUR-004 / Customer Name
    quantity_assigned = db.Column(db.Integer, nullable=False)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    inventory = db.relationship('Inventory', backref='project_allocations')

class DamagedItem(db.Model):
    __tablename__ = 'damaged_items'
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    quantity_damaged = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    reported_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Reported') # Reported / Replaced / Scrapped

    inventory = db.relationship('Inventory', backref='damaged_logs')


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
    # Customer accounts authenticate against customers.id. user_id remains as
    # a nullable legacy/staff reference for older records.
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Request Submitted', nullable=False)
    assigned_to = db.Column(db.String(120), nullable=True)
    scheduled_visit = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('maintenance_requests', lazy=True))
    user = db.relationship('User', foreign_keys=[user_id])







class Complaint(db.Model):
    """Customer complaint tracking for Module 22."""
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True
    )
    complaint_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Submitted')
    admin_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    customer = db.relationship(
        'Customer', backref=db.backref('complaints', lazy=True)
    )

class MaintenancePlan(db.Model):
    """Annual maintenance plans offered to customers."""
    __tablename__ = 'maintenance_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    visits_per_year = db.Column(db.Integer, nullable=False, default=2)
    includes_cleaning = db.Column(db.Boolean, default=False, nullable=False)
    includes_performance_check = db.Column(db.Boolean, default=False, nullable=False)
    includes_emergency_support = db.Column(db.Boolean, default=False, nullable=False)
    includes_minor_repairs = db.Column(db.Boolean, default=False, nullable=False)
    priority_visits = db.Column(db.Boolean, default=False, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    duration_months = db.Column(db.Integer, nullable=False, default=12)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscriptions = db.relationship(
        'CustomerSubscription',
        back_populates='plan',
        lazy=True
    )


class CustomerSubscription(db.Model):
    """Customer's annual maintenance contract/order."""
    __tablename__ = 'customer_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('maintenance_plans.id'), nullable=False)
    contract_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default='Pending Payment')
    payment_status = db.Column(db.String(30), nullable=False, default='Pending')
    payment_method = db.Column(db.String(50), nullable=True)
    transaction_reference = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    renewed_from_id = db.Column(db.Integer, db.ForeignKey('customer_subscriptions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='maintenance_subscriptions')
    plan = db.relationship('MaintenancePlan', back_populates='subscriptions')
    renewed_from = db.relationship(
        'CustomerSubscription',
        remote_side=[id],
        uselist=False
    )


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
    status = db.Column(db.Integer, default=1, nullable=False)

    # Relationship with packages
    packages = db.relationship('SolarPackage', backref='system_type_obj', lazy=True)

    # def __repr__(self):
    #     return f"<SystemType {self.name}>





# class Project(db.Model):
    # __tablename__ = 'projects'
    # id = db.Column(db.Integer, primary_key=True)
    # quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    # customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    # project_name = db.Column(db.String(120), nullable=False)
    # status = db.Column(db.String(50), default='Pending Advance') 
    # # Statuses: Pending Advance, Material Pending, In Installation, Completed
    # created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # quotation = db.relationship('Quotation', backref=db.backref('project', uselist=False))
    # customer = db.relationship('Customer', backref='projects')


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    # 1. Foreign Key Column Add Karein
    technician_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) 

    project_name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), default='Pending Advance') 
    # Statuses: Pending Advance, Material Pending, In Installation, Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quotation = db.relationship('Quotation', backref=db.backref('project', uselist=False))
    customer = db.relationship('Customer', backref='projects')
    
    # 2. Technician Relationship Add Karein
    technician = db.relationship('User', foreign_keys=[technician_id], backref='assigned_projects')



class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    milestone_name = db.Column(db.String(50), nullable=False) # e.g. '30% Advance Payment'
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='Bank Transfer')
    receipt_file = db.Column(db.String(255), nullable=True) # Uploaded slip
    status = db.Column(db.String(50), default='Pending') 
    # Statuses: Pending, Verification Required, Paid, Failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref='payments')

# =========================================================
# Live Chatbot / Sales Handoff (Chat Widget) Models
# =========================================================
class ChatSession(db.Model):
    """One ongoing chat thread — either a guest visitor or a logged-in customer.

    status values:
      'bot'           -> only the AI assistant replies (fresh / guest chat)
      'pending_sales' -> a logged-in customer has messaged; sales team notified,
                         AI assistant still replies until a sales rep accepts
      'active'        -> a sales rep accepted; AI assistant stops replying,
                         only that sales rep talks to the customer from here
      'closed'        -> conversation archived / ended
    """
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True)

    # Set when the visitor is a logged-in customer (Customer.id).
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)

    # Set when the visitor is NOT logged in (random token stored in their browser session).
    guest_token = db.Column(db.String(64), nullable=True, index=True)

    status = db.Column(db.String(20), default='bot', nullable=False)

    # Sales rep (User.id) who accepted this chat request.
    assigned_sales_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('chat_sessions', lazy=True))
    assigned_sales = db.relationship('User', foreign_keys=[assigned_sales_id])


class ChatMessage(db.Model):
    """A single message inside a ChatSession."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False, index=True)

    # sender_type: 'user' (customer/guest visitor), 'bot' (AI assistant), 'sales' (sales rep)
    sender_type = db.Column(db.String(10), nullable=False)
    sender_name = db.Column(db.String(120), default='')
    message = db.Column(db.Text, nullable=False)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('ChatSession', backref=db.backref('messages', lazy=True, order_by='ChatMessage.id'))
