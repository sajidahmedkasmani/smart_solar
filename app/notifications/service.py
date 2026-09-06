from datetime import datetime

from flask import url_for, current_app

from app import db
from app.models import Notification, Customer, User


def create_notification(recipient_id, title, message, *, event_type='General',
                         category='general', link=None, channel='Dashboard',
                         send_email=False, recipient_type='customer'):
    """Create an in-app notification and optionally send an email.

    Customer and staff accounts use separate tables in SolarEase. Customer
    notifications therefore target ``customer_id`` while staff notifications
    target ``user_id``. This keeps notification delivery aligned with the
    actual authentication model instead of mixing Customer.id with User.id.
    """
    if not recipient_id:
        return None

    notification_kwargs = dict(
        title=title,
        message=message,
        category=category,
        channel=channel,
        event_type=event_type,
        link=link,
        is_read=False,
    )
    if recipient_type == 'customer':
        # Customer authentication uses customers.id. Keep a safe legacy
        # fallback for older modules that still pass a users.id value.
        if Customer.query.get(recipient_id):
            notification_kwargs['customer_id'] = recipient_id
        elif User.query.get(recipient_id):
            notification_kwargs['user_id'] = recipient_id
        else:
            return None
    else:
        notification_kwargs['user_id'] = recipient_id

    notification = Notification(**notification_kwargs)
    db.session.add(notification)

    if send_email:
        recipient = None
        if recipient_type == 'customer':
            recipient = Customer.query.get(recipient_id)
        else:
            recipient = User.query.get(recipient_id)

        if recipient and getattr(recipient, 'email', None):
            try:
                from flask_mail import Message
                from app import mail
                msg = Message(
                    subject=title,
                    recipients=[recipient.email],
                    body=message,
                )
                mail.send(msg)
            except Exception as exc:
                current_app.logger.warning('Notification email failed: %s', exc)

    return notification


def create_customer_notification(customer_id, title, message, **kwargs):
    return create_notification(
        customer_id,
        title,
        message,
        recipient_type='customer',
        **kwargs,
    )


def create_staff_notification(user_id, title, message, **kwargs):
    return create_notification(
        user_id,
        title,
        message,
        recipient_type='staff',
        **kwargs,
    )
