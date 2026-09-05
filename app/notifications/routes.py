from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, session, request

from app import db
from app.models import Notification
from app.auth.decorators import role_required

notifications_bp = Blueprint('notifications', __name__)


def _recipient_filter():
    recipient_id = session.get('user_id')
    roles = session.get('roles') or [session.get('role')]
    if isinstance(roles, str):
        roles = [roles]
    if 'customer' in roles and not any(r in {'admin', 'finance', 'sales', 'engineer', 'technician', 'inventory_manager'} for r in roles):
        return {'customer_id': recipient_id}
    return {'user_id': recipient_id}


@notifications_bp.route('/')
@role_required('customer', 'admin', 'finance', 'sales', 'engineer', 'technician', 'inventory_manager')
def index():
    filters = _recipient_filter()
    notifications = (Notification.query
                     .filter_by(**filters)
                     .order_by(Notification.created_at.desc(), Notification.id.desc())
                     .all())
    unread_count = sum(1 for item in notifications if not item.is_read)
    return render_template(
        'notifications.html',
        notifications=notifications,
        unread_count=unread_count,
    )


@notifications_bp.route('/read/<int:notification_id>', methods=['POST', 'GET'])
@role_required('customer', 'admin', 'finance', 'sales', 'engineer', 'technician', 'inventory_manager')
def mark_read(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        **_recipient_filter(),
    ).first_or_404()
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    if notification.link:
        return redirect(notification.link)
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/read-all', methods=['POST'])
@role_required('customer', 'admin', 'finance', 'sales', 'engineer', 'technician', 'inventory_manager')
def mark_all_read():
    Notification.query.filter_by(
        **_recipient_filter(),
        is_read=False,
    ).update({
        'is_read': True,
        'read_at': datetime.utcnow(),
    }, synchronize_session=False)
    db.session.commit()
    return redirect(url_for('notifications.index'))
