import pytest
from config import TestConfig
from app import create_app
from app.extensions import db
from app.seed import seed_initial_data
from app.models import User, Roadmap, ChatRoom, UserBlock
from app.services import buddy_service as svc
from app.services.buddy_rules import is_compatible


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_initial_data()
        yield app
        db.session.remove()
        db.drop_all()


def _users():
    a = User.query.filter_by(username="minh_anh_k65").one()
    b = User.query.filter_by(username="tuan_kiet_k65").one()
    c = User.query.filter_by(username="lan_huong_k64").one()
    return a, b, c


def test_quy_tac_ghep_cap():
    me = {"roadmap_id": 1, "level": 2}
    assert is_compatible(me, {"roadmap_id": 1, "level": 3, "available": True})
    assert not is_compatible(me, {"roadmap_id": 1, "level": 4, "available": True})
    assert not is_compatible(me, {"roadmap_id": 2, "level": 2, "available": True})
    assert not is_compatible(me, {"roadmap_id": 1, "level": 2, "available": False})


def test_ung_vien_dung_lo_trinh_va_trinh_do(app):
    r = Roadmap.query.first()
    a, b, c = _users()
    svc.save_profile(a.id, r.id, 1, True)
    svc.save_profile(b.id, r.id, 2, True)   # lệch 1 bậc -> là ứng viên
    svc.save_profile(c.id, r.id, 3, True)   # lệch 2 bậc -> không
    ids = [p.user_id for p in svc.find_candidates(a.id)]
    assert b.id in ids
    assert c.id not in ids


def test_ghep_doi_khi_ca_hai_cung_like(app):
    r = Roadmap.query.first()
    a, b, _ = _users()
    svc.save_profile(a.id, r.id, 1, True)
    svc.save_profile(b.id, r.id, 1, True)

    assert svc.swipe(a.id, b.id, "like")["matched"] is False
    result = svc.swipe(b.id, a.id, "like")
    assert result["matched"] is True and result["room_id"]

    room = db.session.get(ChatRoom, result["room_id"])
    assert svc.can_send(a.id, room)


def test_bi_chan_khong_hien_thi_va_khong_gui_duoc(app):
    r = Roadmap.query.first()
    a, b, _ = _users()
    svc.save_profile(a.id, r.id, 1, True)
    svc.save_profile(b.id, r.id, 1, True)

    db.session.add(UserBlock(blocker_id=a.id, blocked_id=b.id))
    db.session.commit()

    assert b.id not in [p.user_id for p in svc.find_candidates(a.id)]
    with pytest.raises(ValueError):
        svc.swipe(a.id, b.id, "like")
