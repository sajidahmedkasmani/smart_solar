# SolarEase Role & Login Rules

## Separate entry points
- Customer login: `/auth/login`
- Customer registration: `/auth/register` (customer accounts only)
- Staff/Admin login: `/admin/login` (no registration link)

## Staff account creation
Only an Administrator can create staff accounts from **Users & Access**. The Admin selects one or more staff roles at creation time.

## Multi-role access
A single staff email can have any combination of:
- Sales Representative
- Solar Engineer
- Installation Technician
- Inventory Manager
- Finance Officer
- Administrator

The sidebar on the staff dashboard is generated from the user's assigned roles. Customers never receive the staff dashboard.

## Permission enforcement
Role checks are enforced in backend decorators, not only by hiding sidebar links. Administrator access is not automatically assigned to other users; only an account explicitly containing the `admin` role has Administrator access.

## Customer separation
A dedicated `customers` table stores customer profiles. Legacy `users` rows remain for compatibility with existing foreign keys/workflows, but customer-only accounts are excluded from the Admin Staff Users table and cannot enter `/admin/login` or staff-only routes.

## Admin Users UI
The Admin **Users & Access** screen uses the same dashboard visual shell. Every staff row has a single Access dropdown containing role checkboxes, allowing the Admin to grant/remove multiple roles and save them together.
