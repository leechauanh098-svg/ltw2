from datetime import datetime, timezone

from app.extensions import db
from app.models import BuddyProfile, BuddySwipe, ChatRoom, Message, RoomMember, User, UserBlock
from app.services.buddy_rules import is_compatible


def _as_dict(p: BuddyProfile) -> dict:
    return {"roadmap_id": p.roadmap_id, "level": p.level, "available": p.available}


def get_profile(user_id: int):
    return db.session.get(BuddyProfile, user_id)


def blocked_ids(user_id: int) -> set[int]:
    """Những người đã chặn hoặc bị chặn bởi user_id (chặn hai chiều)."""
    rows = UserBlock.query.filter(
        (UserBlock.blocker_id == user_id) | (UserBlock.blocked_id == user_id)
    ).all()
    return {r.blocked_id if r.blocker_id == user_id else r.blocker_id for r in rows}


def save_profile(user_id: int, roadmap_id: int, level: int, available: bool) -> BuddyProfile:
    profile = get_profile(user_id) or BuddyProfile(user_id=user_id)
    profile.roadmap_id = roadmap_id
    profile.level = level
    profile.available = available
    db.session.add(profile)
    db.session.commit()
    return profile


def find_candidates(user_id: int) -> list[BuddyProfile]:
    me = get_profile(user_id)
    if me is None:
        return []

    swiped = {s.to_user_id for s in BuddySwipe.query.filter_by(from_user_id=user_id).all()}
    blocked = blocked_ids(user_id)
    others = BuddyProfile.query.filter(
        BuddyProfile.roadmap_id == me.roadmap_id,
        BuddyProfile.user_id != user_id,
    ).all()

    result = [
        p for p in others
        if p.user_id not in swiped
        and p.user_id not in blocked
        and is_compatible(_as_dict(me), _as_dict(p))
    ]
    result.sort(key=lambda p: (abs(p.level - me.level), p.user.username))
    return result[:20]


def _find_pair_room(a: int, b: int):
    room_ids = [rid for (rid,) in db.session.query(RoomMember.room_id).filter(RoomMember.user_id == a).all()]
    if not room_ids:
        return None
    for room in ChatRoom.query.filter(ChatRoom.id.in_(room_ids), ChatRoom.type == "pair").all():
        if any(m.user_id == b for m in room.members):
            return room
    return None


def _create_pair_room(a: int, b: int) -> ChatRoom:
    room = ChatRoom(type="pair", created_by=a)
    room.members = [RoomMember(user_id=a), RoomMember(user_id=b)]
    db.session.add(room)
    db.session.flush()
    return room


def swipe(user_id: int, target_id: int, action: str) -> dict:
    me, other = get_profile(user_id), get_profile(target_id)
    if me is None or other is None or not is_compatible(_as_dict(me), _as_dict(other)):
        raise ValueError("Người này không còn là ứng viên phù hợp")
    if target_id in blocked_ids(user_id):
        raise ValueError("Không thể ghép với người này")

    record = db.session.get(BuddySwipe, (user_id, target_id))
    if record is None:
        record = BuddySwipe(from_user_id=user_id, to_user_id=target_id)
        db.session.add(record)
    record.action = action
    record.created_at = datetime.now(timezone.utc)

    room = None
    if action == "like":
        mutual = BuddySwipe.query.filter_by(
            from_user_id=target_id, to_user_id=user_id, action="like"
        ).first()
        if mutual:
            room = _find_pair_room(user_id, target_id) or _create_pair_room(user_id, target_id)

    db.session.commit()
    return {"matched": room is not None, "room_id": room.id if room else None}


def create_group(creator_id: int, name: str, member_ids: list[int]) -> ChatRoom:
    ids = {creator_id, *member_ids}
    valid_ids = [u.id for u in User.query.filter(User.id.in_(ids)).all()]
    room = ChatRoom(type="group", name=name[:100], created_by=creator_id)
    room.members = [RoomMember(user_id=uid) for uid in valid_ids]
    db.session.add(room)
    db.session.commit()
    return room


def is_member(user_id: int, room: ChatRoom) -> bool:
    return any(m.user_id == user_id for m in room.members)


def other_member_id(room: ChatRoom, user_id: int):
    for m in room.members:
        if m.user_id != user_id:
            return m.user_id
    return None


def room_title(room: ChatRoom, user_id: int) -> str:
    if room.type == "group":
        return room.name or "Nhóm học"
    other = next((m.user for m in room.members if m.user_id != user_id), None)
    return other.username if other else "Phòng riêng"


def list_rooms(user_id: int) -> list[tuple[ChatRoom, str]]:
    rooms = (
        ChatRoom.query.join(RoomMember, RoomMember.room_id == ChatRoom.id)
        .filter(RoomMember.user_id == user_id)
        .order_by(ChatRoom.id.desc())
        .all()
    )
    return [(r, room_title(r, user_id)) for r in rooms]


def can_send(user_id: int, room: ChatRoom) -> bool:
    if not is_member(user_id, room):
        return False
    if room.type == "pair":
        other = other_member_id(room, user_id)
        if other is not None and other in blocked_ids(user_id):
            return False
    return True


def recent_messages(room_id: int, limit: int = 50) -> list[Message]:
    msgs = Message.query.filter_by(room_id=room_id).order_by(Message.id.desc()).limit(limit).all()
    return list(reversed(msgs))


def save_message(room: ChatRoom, user_id: int, content: str) -> Message:
    msg = Message(room_id=room.id, user_id=user_id, content=content)
    db.session.add(msg)
    db.session.commit()
    return msg
