import pytest
from config import TestConfig
from app import create_app
from app.extensions import db
from app.seed import seed_initial_data, seed_buddy_demo, seed_m16_data
from app.models import User, Badge, UserBadge, XpEvent, PlacementQuestion
from app.services.m16_service import (
    classify_score,
    award_xp,
    get_leaderboard,
    get_recommendations,
)


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_initial_data()
        seed_buddy_demo()
        seed_m16_data()
        yield app
        db.session.remove()
        db.drop_all()


def test_classify_score_m16():
    assert classify_score(20)["level"] == "Beginner"
    assert classify_score(45)["level"] == "Basic"
    assert classify_score(70)["level"] == "Intermediate"
    assert classify_score(95)["level"] == "Advanced"


def test_xp_ledger_deduplication_and_badge_auto_unlock(app):
    with app.app_context():
        learner = User.query.filter_by(username="hocvien").one()
        initial_xp = learner.total_xp

        # Cộng XP lần 1 với event_key 'node:101:completed' -> phải nhận đủ 80 XP
        gained_1 = award_xp(learner.id, "node:101:completed", "Hoàn thành node HTML", 80)
        assert gained_1 == 80
        assert learner.total_xp == initial_xp + 80

        # Gửi lại cùng event_key -> chống cộng điểm trùng (trả về 0)
        gained_2 = award_xp(learner.id, "node:101:completed", "Hoàn thành node HTML", 80)
        assert gained_2 == 0
        assert learner.total_xp == initial_xp + 80

        # Vì tổng XP của hocvien đã vượt 100 XP (30 + 80 = 110) và streak >= 3 -> tự động mở khóa huy hiệu xp_100 và streak_3
        owned_codes = {
            ub.badge.code
            for ub in UserBadge.query.filter_by(user_id=learner.id).all()
        }
        assert "first_xp" in owned_codes
        assert "xp_100" in owned_codes
        assert "streak_3" in owned_codes


def test_leaderboard_and_recommendations(app):
    with app.app_context():
        board = get_leaderboard(limit=10)
        assert len(board) >= 4
        # Đảm bảo xếp hạng giảm dần theo total_xp
        assert board[0]["total_xp"] >= board[1]["total_xp"]
        assert board[0]["rank"] == 1

        learner = User.query.filter_by(username="hocvien").one()
        recs = get_recommendations(learner.id)
        assert len(recs) >= 1
        assert "title" in recs[0]


def test_all_merged_routes_m10_m12_m16(app):
    client = app.test_client()

    # 1. Đăng nhập với tài khoản học viên (hocvien / 123456)
    res_login = client.post(
        "/auth/login",
        data={"username": "hocvien", "password": "123456"},
        follow_redirects=True,
    )
    assert res_login.status_code == 200

    # 2. Kiểm tra tất cả các trang của M16 & M12 cho Learner
    for url in [
        "/dashboard",
        "/placement-test",
        "/m16/",
        "/m16/achievements",
        "/m16/leaderboard",
        "/m16/progress",
        "/m16/api/dashboard",
        "/m16/api/leaderboard",
        "/m16/api/badges",
        "/m16/api/recommendations",
        "/buddy/",
        "/chat/",
    ]:
        r = client.get(url)
        assert r.status_code == 200, f"Route {url} failed with {r.status_code}"

    # 3. Kiểm tra API Trợ lý AI 3 mức của M12 (/ai/explain)
    r_ai = client.post(
        "/ai/explain",
        json={"code": "print(x)", "error": "NameError: name 'x' is not defined", "level": 2},
    )
    assert r_ai.status_code == 200
    assert r_ai.get_json()["ok"] is True

    # 4. Đăng nhập Admin (admin / 123456) và kiểm tra trang Quản trị M12 & M16
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"username": "admin", "password": "123456"},
        follow_redirects=True,
    )
    for admin_url in ["/m16/admin/questions", "/safety/admin/reports", "/mentor-portal"]:
        r = client.get(admin_url)
        assert r.status_code == 200, f"Admin route {admin_url} failed with {r.status_code}"

    # 5. Admin thêm câu hỏi mới vào Ngân hàng câu hỏi M16
    r_add_q = client.post(
        "/m16/admin/questions",
        data={
            "question_text": "Thẻ nào tạo liên kết trong HTML?",
            "opt_a": "<a>",
            "opt_b": "<p>",
            "opt_c": "<div>",
            "opt_d": "<span>",
            "correct_index": "0",
            "topic": "HTML5",
            "difficulty_tier": "1",
            "explanation": "Thẻ <a> dùng để tạo hyperlink.",
        },
        follow_redirects=True,
    )
    assert r_add_q.status_code == 200
    assert "Thẻ nào tạo liên kết trong HTML?" in r_add_q.get_data(as_text=True)
