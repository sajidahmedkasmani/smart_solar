import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from config import Config
from flask_mail import Mail

mail = Mail()

db = SQLAlchemy()

def create_app(config_class=Config):
    # Change this line: remove instance_relative_config=True
    app = Flask(__name__)
    app.config.from_object(config_class)

    mail.init_app(app)
    
    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    # ... remaining code ...

    # HTML templates ke liye globals
    app.jinja_env.globals['APP_NAME'] = app.config['APP_NAME']
    app.jinja_env.globals['APP_TITLE'] = app.config['APP_TITLE']
    app.jinja_env.globals['APP_TAGLINE'] = app.config['APP_TAGLINE']
    app.jinja_env.globals['COMPANY_EMAIL'] = app.config['COMPANY_EMAIL']

    app.jinja_env.globals['GOOGLE_CLIENT_ID'] = app.config['GOOGLE_CLIENT_ID']

    from app.roles import dashboard_for, label_for, get_user_roles
    app.jinja_env.globals['dashboard_for'] = dashboard_for
    app.jinja_env.globals['label_for'] = label_for
    app.jinja_env.globals['get_user_roles'] = get_user_roles

    from app.auth.routes import auth_bp
    from app.customers.routes import customers_bp
    from app.sales.routes import sales_bp
    from app.surveys.routes import surveys_bp
    from app.quotations.routes import quotations_bp
    from app.inventory.routes import inventory_bp
    from app.installations.routes import installations_bp
    from app.payments.routes import payments_bp
    from app.maintenance.routes import maintenance_bp
    from app.warranties.routes import warranties_bp
    from app.admin.routes import admin_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(customers_bp, url_prefix='/customer')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(surveys_bp, url_prefix='/surveys')
    app.register_blueprint(quotations_bp, url_prefix='/quotations')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(installations_bp, url_prefix='/installations')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(maintenance_bp, url_prefix='/maintenance')
    app.register_blueprint(warranties_bp, url_prefix='/warranties')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        from app.models import SolarPackage
        return __import__('flask').render_template(
            'landing_page/index.html',
            packages=SolarPackage.query.order_by(SolarPackage.id.desc()).limit(3).all()
        )

    with app.app_context():
        db.create_all()
        upgrade_legacy_schema()
        seed_role_assignments()
        seed_data()

    return app


def upgrade_legacy_schema():
    """SQLite compatibility migrations for updated schemas."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    # Maintenance requests table check
    if 'maintenance_requests' in tables:
        columns = {c['name'] for c in inspector.get_columns('maintenance_requests')}
        if 'user_id' not in columns:
            db.session.execute(db.text('ALTER TABLE maintenance_requests ADD COLUMN user_id INTEGER'))
            db.session.commit()

    # Solar packages foreign key migration check for existing DBs
    if 'solar_packages' in tables:
        columns = {c['name'] for c in inspector.get_columns('solar_packages')}
        if 'system_type_id' not in columns:
            db.session.execute(db.text('ALTER TABLE solar_packages ADD COLUMN system_type_id INTEGER'))
            db.session.commit()


def seed_role_assignments():
    """Create role rows for legacy users without changing their existing data."""
    from app.models import User, Customer, UserRole
    from app.roles import ROLES, get_user_roles

    for user in User.query.all():
        if not user.role or user.role not in ROLES:
            user.role = 'customer'
        exists = UserRole.query.filter_by(user_id=user.id).first()
        if not exists:
            db.session.add(UserRole(user_id=user.id, role=user.role))

    for user in User.query.all():
        if 'customer' in get_user_roles(user):
            if not Customer.query.filter_by(user_id=user.id).first():
                db.session.add(Customer(user_id=user.id, full_name=user.full_name, email=user.email, phone=''))
    db.session.commit()


def seed_data():
    from app.models import SolarPackage, Inventory, User, SystemType
    from werkzeug.security import generate_password_hash

    # 1. Seed System Types first
    if SystemType.query.count() == 0:
        db.session.add_all([
            SystemType(
                name='On-Grid',
                tagline='Grid-tied bill reduction with net-metering',
                description='Direct grid connection for maximum power savings.',
                has_grid=True,
                requires_battery=False,
                provides_backup=False,
                supports_net_metering=True
            ),
            SystemType(
                name='Hybrid',
                tagline='Grid-connected with battery backup capabilities',
                description='Combines grid connectivity with battery storage during loadshedding.',
                has_grid=True,
                requires_battery=True,
                provides_backup=True,
                supports_net_metering=True
            ),
            SystemType(
                name='Off-Grid',
                tagline='Standalone system for remote or un-serviced locations',
                description='Fully independent system utilizing heavy batteries or direct pumping.',
                has_grid=False,
                requires_battery=True,
                provides_backup=True,
                supports_net_metering=False
            )
        ])
        db.session.commit()

    # Fetch references for linking FKs
    on_grid = SystemType.query.filter_by(name='On-Grid').first()
    hybrid = SystemType.query.filter_by(name='Hybrid').first()
    off_grid = SystemType.query.filter_by(name='Off-Grid').first()

    # 2. Seed Solar Packages using system_type_id
    if SolarPackage.query.count() == 0:
        db.session.add_all([
            SolarPackage(
                name='3 kW Residential On-Grid',
                system_type_id=on_grid.id if on_grid else None,
                capacity_kw=3,
                panels_info='6 × 550 W panels',
                inverter_info='3 kW On-Grid inverter',
                battery_info='Not included',
                description='Bill reduction and net-metering ready.',
                warranty_years=10,
                price=525000
            ),
            SolarPackage(
                name='5 kW Residential Hybrid',
                system_type_id=hybrid.id if hybrid else None,
                capacity_kw=5,
                panels_info='10 × 550 W panels',
                inverter_info='5 kW Hybrid inverter',
                battery_info='2 × Lithium batteries',
                description='Grid connected with battery backup.',
                warranty_years=10,
                price=1250000
            ),
            SolarPackage(
                name='8 kW Hybrid System',
                system_type_id=hybrid.id if hybrid else None,
                capacity_kw=8,
                panels_info='15 × 550 W panels',
                inverter_info='8 kW Hybrid inverter',
                battery_info='2 × Lithium batteries',
                description='High-capacity home backup solution.',
                warranty_years=10,
                price=1650000
            ),
            SolarPackage(
                name='10 kW Commercial',
                system_type_id=on_grid.id if on_grid else None,
                capacity_kw=10,
                panels_info='19 × 550 W panels',
                inverter_info='10 kW On-Grid inverter',
                battery_info='Not included',
                description='Commercial bill reduction solution.',
                warranty_years=10,
                price=1750000
            ),
            SolarPackage(
                name='20 kW Commercial Hybrid',
                system_type_id=hybrid.id if hybrid else None,
                capacity_kw=20,
                panels_info='37 × 550 W panels',
                inverter_info='20 kW Hybrid inverter',
                battery_info='Commercial battery bank',
                description='Commercial backup and generation.',
                warranty_years=10,
                price=3400000
            ),
            SolarPackage(
                name='50 kW Industrial',
                system_type_id=on_grid.id if on_grid else None,
                capacity_kw=50,
                panels_info='91 × 550 W panels',
                inverter_info='50 kW Industrial inverter',
                battery_info='Not included',
                description='Large-scale industrial generation.',
                warranty_years=10,
                price=7500000
            ),
            SolarPackage(
                name='Agricultural Tube-Well System',
                system_type_id=off_grid.id if off_grid else None,
                capacity_kw=15,
                panels_info='28 × 550 W panels',
                inverter_info='15 kW Solar pump inverter',
                battery_info='Optional',
                description='Solar solution for agricultural pumping.',
                warranty_years=8,
                price=2500000
            ),
        ])

    # 3. Seed Inventory
    if Inventory.query.count() == 0:
        db.session.add_all([
            Inventory(item_name='550W Mono Solar Panel', category='Solar Panel', brand='Tier-1', model='N-Type 550W', quantity=50, purchase_price=28000, selling_price=35000, minimum_stock=10),
            Inventory(item_name='5kW Hybrid Inverter', category='Inverter', brand='SolarEase', model='SE-H5', quantity=10, purchase_price=220000, selling_price=275000, minimum_stock=2),
            Inventory(item_name='Lithium Battery 5kWh', category='Battery', brand='SolarEase', model='LFP-5', quantity=12, purchase_price=180000, selling_price=230000, minimum_stock=2),
            Inventory(item_name='DC Cable 6mm', category='Cable', brand='Generic', model='PV-6', quantity=200, purchase_price=250, selling_price=350, minimum_stock=30),
        ])

    # 4. Seed Administrator User
    admin = User.query.filter_by(email='admin@solarease.pk').first()
    if not admin:
        db.session.add(User(
            full_name='SolarEase Administrator',
            username='admin',
            email='admin@solarease.pk',
            password=generate_password_hash('admin123'),
            role='admin',
        ))
    else:
        admin.role = 'admin'
        if not admin.password.startswith(('scrypt:', 'pbkdf2:', 'argon2:')):
            admin.password = generate_password_hash('admin123')
    
    db.session.commit()