"""Central role/access helpers for SolarEase."""

CUSTOMER = 'customer'
SALES = 'sales'
ENGINEER = 'engineer'
TECHNICIAN = 'technician'
INVENTORY_MANAGER = 'inventory_manager'
FINANCE = 'finance'
ADMIN = 'admin'

ROLES = [CUSTOMER, SALES, ENGINEER, TECHNICIAN, INVENTORY_MANAGER, FINANCE, ADMIN]
STAFF_ROLES = [SALES, ENGINEER, TECHNICIAN, INVENTORY_MANAGER, FINANCE, ADMIN]

ROLE_LABELS = {
    CUSTOMER: 'Customer',
    SALES: 'Sales Representative',
    ENGINEER: 'Solar Engineer',
    TECHNICIAN: 'Installation Technician',
    INVENTORY_MANAGER: 'Inventory Manager',
    FINANCE: 'Finance Officer',
    ADMIN: 'Administrator',
}

ROLE_DASHBOARD_ENDPOINT = {
    CUSTOMER: 'customers.dashboard',
    SALES: 'sales.dashboard',
    ENGINEER: 'surveys.engineer_dashboard',
    TECHNICIAN: 'installations.technician_dashboard',
    INVENTORY_MANAGER: 'inventory.stock',
    FINANCE: 'payments.finance_dashboard',
    ADMIN: 'admin.dashboard',
}

# Login landing priority. Admin wins, then the remaining staff roles, then customer.
DASHBOARD_PRIORITY = [ADMIN, SALES, ENGINEER, TECHNICIAN, INVENTORY_MANAGER, FINANCE, CUSTOMER]


def dashboard_for(role):
    return ROLE_DASHBOARD_ENDPOINT.get(role, 'customers.dashboard')


def label_for(role):
    return ROLE_LABELS.get(role, role.replace('_', ' ').title() if role else 'Unknown')


def get_user_roles(user):
    """Return persisted roles, while keeping legacy one-role accounts compatible."""
    if not user:
        return []
    try:
        assigned = [ur.role for ur in user.assigned_roles]
    except Exception:
        assigned = []
    if user.role and user.role not in assigned:
        assigned.insert(0, user.role)
    # Preserve the documented order and remove duplicates.
    return [r for r in ROLES if r in assigned]


def sync_user_roles(user, roles):
    """Persist a user's complete role set and keep legacy User.role in sync."""
    from app import db
    from app.models import UserRole
    clean = [r for r in ROLES if r in set(roles)]
    if not clean:
        clean = [CUSTOMER]
    existing = {ur.role: ur for ur in user.assigned_roles}
    for role, row in existing.items():
        if role not in clean:
            db.session.delete(row)
    for role in clean:
        if role not in existing:
            db.session.add(UserRole(user_id=user.id, role=role))
    # Legacy column remains useful for older code/data. Use a deterministic primary role.
    for role in DASHBOARD_PRIORITY:
        if role in clean:
            user.role = role
            break
    return clean
