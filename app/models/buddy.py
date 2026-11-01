from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class BuddyProfile(db.Model):
    """Hồ sơ bạn học: lộ trình, trình độ 1-3, có đang sẵn sàng ghép không."""
    __tablename__ = "buddy_profiles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)
    available = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    user = db.relationship("User")
    roadmap = db.relationship("Roadmap")

    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 3", name="ck_buddy_level"),)


class BuddySwipe(db.Model):
    """Lượt quẹt: like hoặc pass. Hai người cùng like thì ghép đôi."""
    __tablename__ = "buddy_swipes"
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    action = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    __table_args__ = (CheckConstraint("action IN ('like', 'pass')", name="ck_swipe_action"),)


class ChatRoom(db.Model):
    """Phòng chat: pair (2 người) hoặc group (nhóm học)."""
    __tablename__ = "chat_rooms"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=_now)

    members = db.relationship("RoomMember", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("type IN ('pair', 'group')", name="ck_room_type"),)


class RoomMember(db.Model):
    __tablename__ = "room_members"
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id", ondelete="CASCADE"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    user = db.relationship("User")


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    author = db.relationship("User")


class UserBlock(db.Model):
    __tablename__ = "user_blocks"
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), default="open", nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    target = db.relationship("User", foreign_keys=[target_user_id])
    reporter = db.relationship("User", foreign_keys=[reporter_id])

    __table_args__ = (CheckConstraint("status IN ('open', 'resolved')", name="ck_report_status"),)
