from datetime import date, timedelta
from typing import Dict, Any, List
from app.extensions import db
from app.models import (
    User,
    Skill,
    UserSkillProgress,
    Lesson,
    UserLessonProgress,
    PlacementTestResult,
    XpEvent,
    UserStreak,
    Badge,
    UserBadge,
)


def classify_score(score: int) -> Dict[str, Any]:
    """
    Phân loại trình độ và lộ trình đề xuất dựa trên thang điểm 0-100 (Module M16).
    Đồng thời ánh xạ sang tầng mở khóa trên Cây Kỹ năng (DAG) của M10.
    """
    if score <= 25:
        return {
            "level": "Beginner",
            "path": "Tầng 1: Nhập môn HTML5 & Cấu trúc Web (Beginner)",
            "unlocked_tier": 1,
        }
    if score <= 50:
        return {
            "level": "Basic",
            "path": "Tầng 2: CSS3 Flexbox & JavaScript Căn bản (Foundation)",
            "unlocked_tier": 2,
        }
    if score <= 75:
        return {
            "level": "Intermediate",
            "path": "Tầng 3: DOM Manipulation & RESTful Web API (Intermediate)",
            "unlocked_tier": 3,
        }
    return {
        "level": "Advanced",
        "path": "Tầng 4: Lập trình Web Backend MVC & Thương mại Điện tử (Advanced)",
        "unlocked_tier": 3,
    }


def update_streak(user_id: int) -> UserStreak:
    """
    Cập nhật chuỗi ngày học liên tiếp (Streak) theo ngày thực tế (M16)
    và đồng bộ trực tiếp vào trường current_streak của bảng users (M10).
    """
    today = date.today()
    streak = db.session.get(UserStreak, user_id)
    user = db.session.get(User, user_id)

    if streak is None:
        initial_val = user.current_streak if (user and user.current_streak > 0) else 1
        streak = UserStreak(
            user_id=user_id,
            current_streak=initial_val,
            longest_streak=initial_val,
            last_study_date=today,
        )
        db.session.add(streak)
    else:
        if streak.last_study_date == today:
            pass
        elif streak.last_study_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
        streak.last_study_date = today

    if user:
        user.current_streak = streak.current_streak

    db.session.commit()
    return streak


def check_and_award_badges(user_id: int) -> List[Badge]:
    """
    Kiểm tra tổng XP và chuỗi Streak hiện tại để tự động trao các Huy hiệu (Badges)
    có điều kiện required_xp hoặc required_streak (Module M16).
    """
    user = db.session.get(User, user_id)
    if not user:
        return []

    streak = db.session.get(UserStreak, user_id)
    curr_streak = streak.current_streak if streak else user.current_streak
    total_xp = user.total_xp

    owned_badge_ids = {
        ub.badge_id for ub in UserBadge.query.filter_by(user_id=user_id).all()
    }
    candidate_badges = Badge.query.all()
    newly_awarded = []

    for b in candidate_badges:
        if b.id in owned_badge_ids:
            continue
        # Chỉ tự động xét các huy hiệu có điều kiện ngưỡng XP hoặc Streak > 0
        if b.required_xp == 0 and b.required_streak == 0:
            continue
        xp_ok = b.required_xp == 0 or total_xp >= b.required_xp
        streak_ok = b.required_streak == 0 or curr_streak >= b.required_streak
        if xp_ok and streak_ok:
            db.session.add(UserBadge(user_id=user_id, badge_id=b.id))
            newly_awarded.append(b)

    if newly_awarded:
        db.session.commit()
    return newly_awarded


def award_xp(user_id: int, event_key: str, reason: str, xp: int) -> int:
    """
    Ghi nhận điểm kinh nghiệm vào Sổ cái XpEvent (chống cộng trùng bằng event_key).
    Nếu sự kiện mới hợp lệ -> Cộng vào user.total_xp, cập nhật Streak và xét Huy hiệu.
    """
    if xp <= 0:
        return 0

    existing = XpEvent.query.filter_by(user_id=user_id, event_key=event_key).first()
    if existing:
        return 0

    event = XpEvent(user_id=user_id, event_key=event_key, reason=reason, xp=xp)
    db.session.add(event)

    user = db.session.get(User, user_id)
    if user:
        user.total_xp += xp

    db.session.commit()
    update_streak(user_id)
    check_and_award_badges(user_id)
    return xp


def get_m16_dashboard_data(user_id: int) -> Dict[str, Any]:
    """Tổng hợp dữ liệu Dashboard năng lực số & Gamification cho người học."""
    user = db.session.get(User, user_id)
    streak = db.session.get(UserStreak, user_id)
    if not streak and user:
        streak = update_streak(user_id)

    skills_total = Skill.query.count()
    skills_mastered = UserSkillProgress.query.filter_by(
        user_id=user_id, status="mastered"
    ).count()

    lessons_total = Lesson.query.count()
    lessons_completed = UserLessonProgress.query.filter_by(
        user_id=user_id, is_completed=True
    ).count()

    latest_test = (
        PlacementTestResult.query.filter_by(user_id=user_id)
        .order_by(PlacementTestResult.completed_at.desc())
        .first()
    )

    user_badges = (
        UserBadge.query.filter_by(user_id=user_id)
        .order_by(UserBadge.awarded_at.desc())
        .all()
    )

    xp_events = (
        XpEvent.query.filter_by(user_id=user_id)
        .order_by(XpEvent.created_at.desc())
        .limit(15)
        .all()
    )

    return {
        "total_xp": user.total_xp if user else 0,
        "streak": {
            "current_streak": streak.current_streak if streak else 1,
            "longest_streak": streak.longest_streak if streak else 1,
            "last_study_date": streak.last_study_date.isoformat()
            if (streak and streak.last_study_date)
            else None,
        },
        "progress": {
            "completed": skills_mastered,
            "total": skills_total,
            "lessons_completed": lessons_completed,
            "lessons_total": lessons_total,
        },
        "badges": [
            {
                "code": ub.badge.code,
                "name": ub.badge.name,
                "description": ub.badge.description,
                "icon": ub.badge.icon,
                "color": ub.badge.color,
                "earned_at": ub.awarded_at.isoformat() if ub.awarded_at else None,
            }
            for ub in user_badges
            if ub.badge
        ],
        "latest_test": {
            "score": latest_test.score,
            "correct_count": latest_test.correct_count,
            "total_questions": latest_test.total_questions,
            "level": latest_test.level,
            "recommended_path": latest_test.recommended_path,
            "completed_at": latest_test.completed_at.strftime("%d/%m/%Y %H:%M")
            if latest_test.completed_at
            else "",
        }
        if latest_test
        else None,
        "xp_history": [
            {
                "id": ev.id,
                "event_key": ev.event_key,
                "reason": ev.reason,
                "xp": ev.xp,
                "created_at": ev.created_at.strftime("%d/%m/%Y %H:%M")
                if ev.created_at
                else "",
            }
            for ev in xp_events
        ],
    }


def get_leaderboard(limit: int = 20) -> List[Dict[str, Any]]:
    """Bảng xếp hạng XP học viên toàn hệ thống."""
    users = (
        User.query.filter_by(role="learner")
        .order_by(User.total_xp.desc(), User.current_streak.desc(), User.id.asc())
        .limit(limit)
        .all()
    )
    rows = []
    for idx, u in enumerate(users, start=1):
        mastered_cnt = UserSkillProgress.query.filter_by(
            user_id=u.id, status="mastered"
        ).count()
        rows.append(
            {
                "rank": idx,
                "user_id": u.id,
                "username": u.username,
                "placement_level": u.placement_level,
                "total_xp": u.total_xp,
                "current_streak": u.current_streak,
                "badges_count": len(u.badges),
                "mastered_nodes": mastered_cnt,
            }
        )
    return rows


def get_recommendations(user_id: int) -> List[Dict[str, str]]:
    """Gợi ý bài học & lộ trình cá nhân hóa dựa trên kết quả Test đầu vào và tiến độ Cây kỹ năng."""
    latest_test = (
        PlacementTestResult.query.filter_by(user_id=user_id)
        .order_by(PlacementTestResult.completed_at.desc())
        .first()
    )
    unlocked_progs = (
        UserSkillProgress.query.filter(
            UserSkillProgress.user_id == user_id,
            UserSkillProgress.status.in_(["unlocked", "in_progress"]),
        )
        .all()
    )

    recs = []
    if not latest_test:
        recs.append(
            {
                "title": "Thực hiện Bài Kiểm tra Trình độ Đầu vào (Placement Test)",
                "reason": "Bạn chưa có lịch sử làm bài đánh giá năng lực. Hãy làm bài test để hệ thống tự động mở khóa các kỹ năng phù hợp và nhận ngay +20 XP.",
                "action_url": "/placement-test",
                "action_label": "Làm Test ngay",
            }
        )
    else:
        recs.append(
            {
                "title": f"Lộ trình trọng tâm: {latest_test.recommended_path}",
                "reason": f"Dựa trên kết quả kiểm tra gần nhất ({latest_test.score}/100 điểm • Trình độ {latest_test.level}).",
                "action_url": "/dashboard",
                "action_label": "Vào Lộ trình",
            }
        )

    for p in unlocked_progs[:2]:
        if p.skill:
            recs.append(
                {
                    "title": f"Chinh phục Node kỹ năng: {p.skill.name}",
                    "reason": f"Node này đang ở trạng thái {p.status.upper()} ({p.completed_exercises}/{p.skill.required_exercises_count} bài tập hoàn thành). Hãy đọc bài giảng và giải bài tập để đạt Mastered!",
                    "action_url": "/skills/",
                    "action_label": "Mở Cây Kỹ năng",
                }
            )

    if len(recs) < 3:
        recs.append(
            {
                "title": "Tìm Bạn Học Cùng Lộ Trình (Study Buddy)",
                "reason": "Ghép cặp với bạn học cùng trình độ trên lộ trình NEU để trao đổi bài tập qua phòng Chat thời gian thực.",
                "action_url": "/buddy/",
                "action_label": "Tìm Bạn học",
            }
        )
    return recs
