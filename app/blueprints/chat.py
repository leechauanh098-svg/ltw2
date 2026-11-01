from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_socketio import emit, join_room

from app.extensions import db, socketio
from app.models import ChatRoom, User
from app.services import buddy_service as svc

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/")
@login_required
def index():
    uid = current_user.id
    rooms = svc.list_rooms(uid)

    current = None
    room_id = request.args.get("room", type=int)
    if room_id:
        candidate = db.session.get(ChatRoom, room_id)
        if candidate and svc.is_member(uid, candidate):
            current = candidate
        else:
            flash("Bạn không có quyền vào phòng này.", "danger")
    if current is None and rooms:
        current = rooms[0][0]

    messages, can_send, other_id, current_title = [], False, None, ""
    if current:
        messages = svc.recent_messages(current.id)
        can_send = svc.can_send(uid, current)
        other_id = svc.other_member_id(current, uid) if current.type == "pair" else None
        current_title = svc.room_title(current, uid)

    learners = User.query.filter(User.role == "learner", User.id != uid).order_by(User.username).all()
    return render_template(
        "chat/index.html",
        rooms=rooms,
        current=current,
        messages=messages,
        can_send=can_send,
        other_id=other_id,
        current_title=current_title,
        learners=learners,
    )


@chat_bp.route("/group", methods=["POST"])
@login_required
def create_group():
    name = (request.form.get("name") or "").strip()
    member_ids = [int(x) for x in request.form.getlist("member_ids") if x.isdigit()]
    if not name:
        flash("Cần đặt tên cho nhóm.", "warning")
        return redirect(url_for("chat.index"))

    room = svc.create_group(current_user.id, name, member_ids)
    flash("Đã tạo nhóm học.", "success")
    return redirect(url_for("chat.index", room=room.id))


# ---------- Socket.IO ----------

@socketio.on("connect")
def on_connect(auth=None):
    if not current_user.is_authenticated:
        return False  # từ chối kết nối nếu chưa đăng nhập


@socketio.on("join_chat_room")
def on_join_chat_room(data):
    if not current_user.is_authenticated:
        return
    room = db.session.get(ChatRoom, int((data or {}).get("room_id", 0)))
    if room and svc.is_member(current_user.id, room):
        join_room(f"room:{room.id}")


@socketio.on("send_message")
def on_send_message(data):
    if not current_user.is_authenticated:
        return {"ok": False, "error": "Chưa đăng nhập"}

    data = data or {}
    content = str(data.get("content", "")).strip()
    if not content or len(content) > 500:
        return {"ok": False, "error": "Tin nhắn phải từ 1 đến 500 ký tự"}

    try:
        room = db.session.get(ChatRoom, int(data.get("room_id", 0)))
    except (TypeError, ValueError):
        room = None
    if room is None or not svc.can_send(current_user.id, room):
        return {"ok": False, "error": "Không thể gửi tin nhắn trong phòng này"}

    msg = svc.save_message(room, current_user.id, content)
    emit(
        "new_message",
        {
            "id": msg.id,
            "room_id": room.id,
            "user_id": current_user.id,
            "username": current_user.username,
            "content": msg.content,
        },
        to=f"room:{room.id}",
    )
    return {"ok": True}
