import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, session

from app import db
from app.models import ChatSession, ChatMessage, User, UserRole, Notification
from app.chatbot.ai import get_bot_reply

chatbot_bp = Blueprint('chatbot', __name__)

BOT_NAME = 'SolarEase Assistant'
GREETING = (
    "Assalam-o-Alaikum! Main SolarEase Assistant hoon. Apni solar/home energy requirement "
    "bataiye — jaise monthly bijli ka bill, roof area, ya system type (On-Grid / Hybrid / "
    "Off-Grid) — main turant madad karta hoon."
)


def _guest_token():
    """Anonymous visitors get a random token stored in their own browser session."""
    token = session.get('chat_guest_token')
    if not token:
        token = uuid.uuid4().hex
        session['chat_guest_token'] = token
    return token


def _identity():
    """Return ('customer', customer_id) for a logged-in customer, else ('guest', token)."""
    if session.get('role') == 'customer' and session.get('user_id'):
        return 'customer', session['user_id']
    return 'guest', _guest_token()


def _get_or_create_session():
    kind, ident = _identity()
    query = ChatSession.query
    if kind == 'customer':
        query = query.filter_by(customer_id=ident)
    else:
        query = query.filter_by(guest_token=ident)

    chat = query.filter(ChatSession.status != 'closed').order_by(ChatSession.id.desc()).first()
    if not chat:
        chat = ChatSession(
            customer_id=ident if kind == 'customer' else None,
            guest_token=ident if kind == 'guest' else None,
            status='bot',
        )
        db.session.add(chat)
        db.session.commit()
    return chat, kind


def _serialize(msg):
    return {
        'id': msg.id,
        'sender_type': msg.sender_type,
        'sender_name': msg.sender_name,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%H:%M'),
    }


def _notify_sales(chat):
    """Ping every sales-role staff member that a logged-in customer needs help."""
    sales_ids = {ur.user_id for ur in UserRole.query.filter_by(role='sales').all()}
    sales_ids |= {u.id for u in User.query.filter_by(role='sales').all()}

    customer_name = 'A customer'
    if chat.customer_id and chat.customer:
        customer_name = chat.customer.full_name

    for uid in sales_ids:
        db.session.add(Notification(
            user_id=uid,
            title='New live chat request',
            message=f'{customer_name} has started a live chat and needs sales assistance.',
            category='chat',
            event_type='Chat Request',
            link=f'/sales/chats/{chat.id}',
        ))


@chatbot_bp.route('/init', methods=['GET'])
def init():
    """Fetch (or start) the visitor's chat session and its message history."""
    chat, kind = _get_or_create_session()

    history = ChatMessage.query.filter_by(session_id=chat.id).order_by(ChatMessage.id.asc()).all()
    if not history:
        greeting = ChatMessage(
            session_id=chat.id, sender_type='bot', sender_name=BOT_NAME, message=GREETING,
        )
        db.session.add(greeting)
        db.session.commit()
        history = [greeting]

    return jsonify({
        'session_id': chat.id,
        'status': chat.status,
        'is_customer': kind == 'customer',
        'messages': [_serialize(m) for m in history],
    })


@chatbot_bp.route('/send', methods=['POST'])
def send():
    data = request.get_json(silent=True) or {}
    text = (data.get('message') or '').strip()
    if not text:
        return jsonify({'error': 'empty message'}), 400

    chat, kind = _get_or_create_session()

    sender_name = session.get('user_name', 'Visitor') if kind == 'customer' else 'Guest'
    user_msg = ChatMessage(session_id=chat.id, sender_type='user', sender_name=sender_name, message=text)
    db.session.add(user_msg)

    # A sales rep has already taken over this conversation — the bot stays silent
    # and the sales rep will see/reply to this message from their own inbox.
    if chat.status == 'active':
        db.session.commit()
        return jsonify({
            'session_id': chat.id,
            'status': chat.status,
            'messages': [_serialize(user_msg)],
        })

    history = ChatMessage.query.filter_by(session_id=chat.id).order_by(ChatMessage.id.asc()).all()
    history_payload = [{'sender_type': m.sender_type, 'message': m.message} for m in history]
    reply_text = get_bot_reply(history_payload, text)

    bot_msg = ChatMessage(session_id=chat.id, sender_type='bot', sender_name=BOT_NAME, message=reply_text)
    db.session.add(bot_msg)

    # First message from a logged-in customer -> raise a request to the sales team.
    # The bot keeps answering until a sales rep accepts the request.
    if kind == 'customer' and chat.status == 'bot':
        chat.status = 'pending_sales'
        _notify_sales(chat)

    chat.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'session_id': chat.id,
        'status': chat.status,
        'messages': [_serialize(user_msg), _serialize(bot_msg)],
    })


@chatbot_bp.route('/poll', methods=['GET'])
def poll():
    """Lightweight polling endpoint so the widget can pick up a sales rep's replies."""
    chat, kind = _get_or_create_session()
    after_id = request.args.get('after_id', 0, type=int)

    msgs = (ChatMessage.query
            .filter_by(session_id=chat.id)
            .filter(ChatMessage.id > after_id)
            .order_by(ChatMessage.id.asc())
            .all())

    return jsonify({
        'status': chat.status,
        'messages': [_serialize(m) for m in msgs],
    })
