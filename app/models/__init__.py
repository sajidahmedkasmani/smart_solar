from .models import (
    User, Customer, UserRole, StaffRoleRequest, Requirement, SolarPackage, Survey,
    SurveyImage, Notification, Quotation, Payment, Installation, Inventory,
    Warranty, MaintenanceRequest, SystemType,
    Supplier, PurchaseOrder, ProjectAssignment, DamagedItem  # <-- Added
)

__all__ = [
    'User', 'Customer', 'UserRole', 'StaffRoleRequest', 'Requirement', 'SolarPackage',
    'Survey', 'SurveyImage', 'Notification', 'Quotation', 'Payment', 'Installation',
    'Inventory', 'Warranty', 'MaintenanceRequest', 'SystemType',
    'Supplier', 'PurchaseOrder', 'ProjectAssignment', 'DamagedItem'  # <-- Added
]