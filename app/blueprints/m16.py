from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Skill,
    UserSkillProgress,
    Lesson,
    UserLessonProgress,
    PlacementQuestion,
    PlacementTestResult,
    XpEvent,
    UserStreak,
    Badge,
    UserBadge,
)
from app.blueprints.auth import role_required
from app.services.dag_service import sync_user_skill_tree
from app.services.m16_service import (
    classify_score,
    award_xp,
    update_streak,
    check_and_award_badges,
    get_m16_dashboard_data,
    get_leaderboard,
    get_recommendations,
)

m16_bp = Blueprint("m16", __name__, url_prefix="/m16")


# ==============================================================================
# 1. CÁC TRANG GIAO DIỆN WEB (HTML VIEWS) CỦA MODULE M16
# ==============================================================================

@m16_bp.route("/")
@login_required
def index():
    """Tổng quan Năng lực số, Streak, Lịch sử XP & Gợi ý Học tập (Module M16)."""
    sync_user_skill_tree(current_user.id)
    data = get_m16_dashboard_data(current_user.id)
    recommendations = get_recommendations(current_user.id)
    return render_template(
        "m16/dashboard.html",
        data=data,
        recommendations=recommendations,
    )


@m16_bp.route("/achievements")
@login_required
def achievements():
    """Trang Thành tích, Huy hiệu (Badges) & Sổ cái Lịch sử nhận XP (XP Ledger)."""
    check_and_award_badges(current_user.id)
    all_badges = Badge.query.order_by(Badge.id.asc()).all()
    user_badge_map = {
        ub.badge_id: ub
        for ub in UserBadge.query.filter_by(user_id=current_user.id).all()
    }
    xp_events = (
        XpEvent.query.filter_by(user_id=current_user.id)
        .order_by(XpEvent.created_at.desc())
        .all()
    )
    streak = db.session.get(UserStreak, current_user.id) or update_streak(current_user.id)
    return render_template(
        "m16/achievements.html",
        all_badges=all_badges,
        user_badge_map=user_badge_map,
        xp_events=xp_events,
        streak=streak,
    )


@m16_bp.route("/leaderboard")
@login_required
def leaderboard():
    """Bảng xếp hạng XP & Chuỗi ngày học toàn hệ thống (Module M16)."""
    rows = get_leaderboard(limit=25)
    return render_template("m16/leaderboard.html", leaderboard=rows)


@m16_bp.route("/progress")
@login_required
def progress():
    """Chi tiết Tiến độ hoàn thành các Node Kỹ năng & Bài giảng (Module M16)."""
    sync_user_skill_tree(current_user.id)
    skills = Skill.query.order_by(Skill.tier.asc(), Skill.id.asc()).all()
    prog_map = {
        p.skill_id: p
        for p in UserSkillProgress.query.filter_by(user_id=current_user.id).all()
    }
    lessons = Lesson.query.order_by(Lesson.course_id.asc(), Lesson.order_index.asc()).all()
    lesson_prog_map = {
        lp.lesson_id: lp
        for lp in UserLessonProgress.query.filter_by(user_id=current_user.id).all()
    }

    mastered_count = sum(1 for p in prog_map.values() if p.status == "mastered")
    total_skills = len(skills)
    percent = round((mastered_count / total_skills) * 100) if total_skills else 0

    test_history = (
        PlacementTestResult.query.filter_by(user_id=current_user.id)
        .order_by(PlacementTestResult.completed_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "m16/progress.html",
        skills=skills,
        prog_map=prog_map,
        lessons=lessons,
        lesson_prog_map=lesson_prog_map,
        mastered_count=mastered_count,
        total_skills=total_skills,
        percent=percent,
        test_history=test_history,
    )


@m16_bp.route("/admin/questions", methods=["GET", "POST"])
@role_required("admin")
def admin_questions():
    """Trang Quản trị Ngân hàng Câu hỏi Kiểm tra Đầu vào (Admin - Module M16)."""
    if request.method == "POST":
        question_text = (request.form.get("question_text") or "").strip()
        opt_a = (request.form.get("opt_a") or "").strip()
        opt_b = (request.form.get("opt_b") or "").strip()
        opt_c = (request.form.get("opt_c") or "").strip()
        opt_d = (request.form.get("opt_d") or "").strip()
        correct_index = request.form.get("correct_index", type=int, default=0)
        topic = (request.form.get("topic") or "HTML").strip()
        difficulty_tier = request.form.get("difficulty_tier", type=int, default=1)
        skill_id = request.form.get("skill_id", type=int)
        explanation = (request.form.get("explanation") or "").strip()

        if not question_text or not all([opt_a, opt_b, opt_c, opt_d]) or correct_index not in (0, 1, 2, 3):
            flash("Vui lòng nhập đầy đủ nội dung câu hỏi, 4 lựa chọn A/B/C/D và đáp án đúng.", "danger")
        else:
            q = PlacementQuestion(
                skill_id=skill_id if skill_id else None,
                question_text=question_text,
                options_json=[opt_a, opt_b, opt_c, opt_d],
                correct_index=correct_index,
                topic=topic,
                difficulty_tier=max(1, min(4, difficulty_tier)),
                explanation=explanation,
                is_active=True,
            )
            db.session.add(q)
            db.session.commit()
            flash(f"Đã thêm câu hỏi #{q.id} vào Ngân hàng câu hỏi Test đầu vào.", "success")
        return redirect(url_for("m16.admin_questions"))

    questions = PlacementQuestion.query.order_by(PlacementQuestion.id.desc()).all()
    skills = Skill.query.order_by(Skill.tier.asc()).all()
    return render_template(
        "m16/admin_questions.html",
        questions=questions,
        skills=skills,
    )


@m16_bp.route("/admin/questions/<int:q_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_question(q_id: int):
    """Ẩn hoặc hiện lại câu hỏi trong ngân hàng đề Test đầu vào."""
    q = db.session.get(PlacementQuestion, q_id)
    if q:
        q.is_active = not q.is_active
        db.session.commit()
        status_label = "Đang hoạt động" if q.is_active else "Đã ẩn"
        flash(f"Cập nhật câu hỏi #{q.id}: {status_label}.", "success")
    return redirect(url_for("m16.admin_questions"))


# ==============================================================================
# 2. CÁC REST API JSON CỦA MODULE M16 (TƯƠNG THÍCH CHUẨN TÍCH HỢP M10/M16)
# ==============================================================================

@m16_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    return jsonify(get_m16_dashboard_data(current_user.id))


@m16_bp.route("/api/progress/complete", methods=["POST"])
@login_required
def api_progress_complete():
    """Endpoint nhận sự kiện hoàn thành node/bài học với eventKey chống cộng XP trùng."""
    body = request.get_json(silent=True) or {}
    node_id = body.get("nodeId")
    node_title = body.get("nodeTitle", "Node kỹ năng")
    event_key = body.get("eventKey")
    if not node_id or not event_key:
        return jsonify({"message": "Thiếu nodeId hoặc eventKey."}), 400

    gained = award_xp(
        user_id=current_user.id,
        event_key=str(event_key),
        reason=f"Hoàn thành node: {node_title}",
        xp=30,
    )
    return jsonify({"message": "Đã cập nhật tiến độ.", "gainedXp": gained})


@m16_bp.route("/api/leaderboard")
@login_required
def api_leaderboard():
    return jsonify({"leaderboard": get_leaderboard(limit=20)})


@m16_bp.route("/api/recommendations")
@login_required
def api_recommendations():
    return jsonify(
        {
            "recommendations": get_recommendations(current_user.id),
            "generatedBy": "M16 rule-based & DAG adaptive engine",
        }
    )


@m16_bp.route("/api/badges")
@login_required
def api_badges():
    check_and_award_badges(current_user.id)
    all_badges = Badge.query.order_by(Badge.id.asc()).all()
    owned_map = {
        ub.badge_id: ub
        for ub in UserBadge.query.filter_by(user_id=current_user.id).all()
    }
    return jsonify(
        {
            "badges": [
                {
                    "id": b.id,
                    "code": b.code,
                    "name": b.name,
                    "description": b.description,
                    "icon": b.icon,
                    "required_xp": b.required_xp,
                    "required_streak": b.required_streak,
                    "earned": b.id in owned_map,
                    "earned_at": owned_map[b.id].awarded_at.isoformat()
                    if b.id in owned_map and owned_map[b.id].awarded_at
                    else None,
                }
                for b in all_badges
            ]
        }
    )
