from app.models import User


def unique_username(base):
    """Turns an email-prefix into a username that is guaranteed not to collide
    with an existing user. Fixes the 'UNIQUE constraint failed: users.username'
    crash that used to happen whenever two people shared the same email prefix
    (e.g. sales1@gmail.com colliding with the seeded demo account 'sales1')."""
    base = (base or 'user').strip().lower() or 'user'
    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first() is not None:
        suffix += 1
        candidate = f'{base}{suffix}'
    return candidate
