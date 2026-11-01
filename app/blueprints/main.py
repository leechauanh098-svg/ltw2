from datetime import datetime, timezone
import markdown
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    User,
    Course,
    Lesson,
    UserLessonProgress,
    Exercise,
    Submission,
    Skill,
    UserSkillProgress,
    Roadmap,
    PlacementQuestion,
    PlacementTestResult,
    Badge,
)
from app.services.dag_service import sync_user_skill_tree
from app.services.ai_tutor_service import award_badge_if_not_owned
from app.services.m16_service import classify_score, award_xp
from app.blueprints.auth import role_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Trang chủ: Nếu là Khách hiển thị trang Giới thiệu & Lộ trình mẫu; nếu đã đăng nhập vào Dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.landing"))


@main_bp.route("/welcome")
def landing():
    """Trang giới thiệu dành cho Khách (Guest): Xem cây kỹ năng mẫu, làm thử Test đầu vào."""
    skills = Skill.query.order_by(Skill.tier.asc(), Skill.id.asc()).all()
    roadmaps = Roadmap.query.all()
    sample_exercises = Exercise.query.limit(3).all()
    return render_template(
        "landing.html",
        skills=skills,
        roadmaps=roadmaps,
        sample_exercises=sample_exercises,
    )


@main_bp.route("/slides")
def presentation_slides():
    """Trình chiếu slide thuyết trình dự án bằng Reveal.js."""
    return render_template("slides.html")


@main_bp.route("/placement-test", methods=["GET", "POST"])
def placement_test():
    """
    Bài Test Đầu Vào (Placement Test) cho cả Khách và Người học (M10 & M16):
    Đánh giá năng lực HTML/CSS/JS ban đầu để xếp người học vào đúng tầng trên Cây kỹ năng,
    đồng thời lưu lịch sử PlacementTestResult và ghi sổ cái XP của M16.
    """
    questions = (
        PlacementQuestion.query.filter_by(is_active=True)
        .order_by(PlacementQuestion.difficulty_tier.asc(), PlacementQuestion.id.asc())
        .all()
    )
    result_summary = None

    if request.method == "POST":
        correct_count = 0
        passed_skill_ids = set()
        details = []
        answers_map = {}

        for q in questions:
            selected = request.form.get(f"q_{q.id}")
            answers_map[str(q.id)] = selected
            is_correct = selected is not None and int(selected) == q.correct_index
            if is_correct:
                correct_count += 1
                if q.skill_id:
                    passed_skill_ids.add(q.skill_id)
            details.append(
                {
                    "question": q.question_text,
                    "is_correct": is_correct,
                    "correct_answer": q.options_json[q.correct_index],
                    "explanation": q.explanation,
                }
            )

        total_q = len(questions)
        score_100 = round((correct_count / total_q) * 100) if total_q else 0
        placement_info = classify_score(score_100)
        rec_level = placement_info["path"]
        unlocked_tier = placement_info["unlocked_tier"]

        # Nếu người học đã đăng nhập -> Lưu PlacementTestResult (M16), cộng XP qua sổ cái & Mở khóa Cây kỹ năng
        if current_user.is_authenticated:
            current_user.placement_done = True
            current_user.placement_level = rec_level

            test_res = PlacementTestResult(
                user_id=current_user.id,
                score=score_100,
                correct_count=correct_count,
                total_questions=total_q,
                level=placement_info["level"],
                recommended_path=rec_level,
                answers_json=answers_map,
            )
            db.session.add(test_res)
            db.session.flush()

            sync_user_skill_tree(current_user.id)
            if unlocked_tier >= 2:
                # Đánh dấu Mastered cho Node Tầng 1 (HTML5) để mở khóa ngay Tầng 2 (CSS3 & JS)
                tier1_skills = Skill.query.filter_by(tier=1).all()
                for s1 in tier1_skills:
                    p = UserSkillProgress.query.filter_by(
                        user_id=current_user.id, skill_id=s1.id
                    ).first()
                    if p:
                        p.status = "mastered"
                        p.earned_xp = max(p.earned_xp, s1.required_xp)
                        p.completed_exercises = max(
                            p.completed_exercises, s1.required_exercises_count
                        )
            if unlocked_tier >= 3:
                tier2_skills = Skill.query.filter_by(tier=2).all()
                for s2 in tier2_skills:
                    p = UserSkillProgress.query.filter_by(
                        user_id=current_user.id, skill_id=s2.id
                    ).first()
                    if p:
                        p.status = "mastered"
                        p.earned_xp = max(p.earned_xp, s2.required_xp)
                        p.completed_exercises = max(
                            p.completed_exercises, s2.required_exercises_count
                        )

            db.session.commit()
            sync_user_skill_tree(current_user.id)
            award_xp(
                user_id=current_user.id,
                event_key=f"test:{test_res.id}",
                reason=f"Hoàn thành bài kiểm tra đầu vào ({score_100}/100 điểm)",
                xp=max(20, correct_count * 15),
            )
            award_badge_if_not_owned(current_user.id, "placement_passed")

        result_summary = {
            "correct": correct_count,
            "total": total_q,
            "score": score_100,
            "level": placement_info["level"],
            "recommended_level": rec_level,
            "unlocked_tier": unlocked_tier,
            "details": details,
        }

    return render_template(
        "placement_test.html",
        questions=questions,
        result_summary=result_summary,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    sync_user_skill_tree(current_user.id)

    skills = Skill.query.order_by(Skill.tier.asc(), Skill.id.asc()).all()
    skill_progress = {
        p.skill_id: p
        for p in UserSkillProgress.query.filter_by(user_id=current_user.id).all()
    }
    exercises = Exercise.query.order_by(Exercise.id.asc()).all()
    ac_exercise_ids = {
        row[0]
        for row in db.session.query(Submission.exercise_id)
        .filter_by(user_id=current_user.id, status="AC")
        .distinct()
        .all()
    }
    courses = Course.query.all()
    completed_lesson_ids = {
        row[0]
        for row in db.session.query(UserLessonProgress.lesson_id)
        .filter_by(user_id=current_user.id, is_completed=True)
        .all()
    }
    roadmaps = Roadmap.query.all()
    recent_submissions = (
        Submission.query.filter_by(user_id=current_user.id)
        .order_by(Submission.created_at.desc())
        .limit(6)
        .all()
    )

    # Tìm bạn học cùng lộ trình (Study Buddies): Các học viên khác đang học cùng hoặc gần tầng kỹ năng
    study_buddies = (
        User.query.filter(User.id != current_user.id, User.role == "learner")
        .order_by(User.total_xp.desc())
        .limit(5)
        .all()
    )

    all_badges = Badge.query.all()
    owned_badge_ids = {ub.badge_id for ub in current_user.badges}

    mastered_skills_count = sum(
        1 for p in skill_progress.values() if p.status == "mastered"
    )

    return render_template(
        "dashboard.html",
        skills=skills,
        skill_progress=skill_progress,
        exercises=exercises,
        ac_exercise_ids=ac_exercise_ids,
        courses=courses,
        completed_lesson_ids=completed_lesson_ids,
        roadmaps=roadmaps,
        recent_submissions=recent_submissions,
        mastered_skills_count=mastered_skills_count,
        study_buddies=study_buddies,
        all_badges=all_badges,
        owned_badge_ids=owned_badge_ids,
    )


@main_bp.route("/lessons/<slug>")
@login_required
def lesson_detail(slug: str):
    lesson = Lesson.query.filter_by(slug=slug).first_or_404()
    html_content = markdown.markdown(
        lesson.content_markdown, extensions=["fenced_code", "tables"]
    )
    progress = UserLessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson.id
    ).first()
    related_exercises = lesson.exercises.all()

    return render_template(
        "lessons/detail.html",
        lesson=lesson,
        html_content=html_content,
        progress=progress,
        related_exercises=related_exercises,
    )


@main_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@login_required
def complete_lesson(lesson_id: int):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return jsonify({"error": "Not found"}), 404

    progress = UserLessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson.id
    ).first()
    if not progress:
        progress = UserLessonProgress(
            user_id=current_user.id,
            lesson_id=lesson.id,
            is_completed=True,
            time_spent_seconds=int(request.form.get("time_spent", 60)),
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(progress)
        db.session.commit()
        award_xp(
            user_id=current_user.id,
            event_key=f"lesson:{lesson.id}:completed",
            reason=f"Đọc hoàn thành bài giảng: {lesson.title}",
            xp=lesson.xp_reward,
        )
        flash(
            f"Đã hoàn thành bài giảng (+{lesson.xp_reward} XP)! Hãy làm bài tập thực hành bên dưới để củng cố kiến thức.",
            "success",
        )
    else:
        flash("Bạn đã hoàn thành bài giảng này. Hãy tiến hành làm bài thực hành củng cố!", "info")

    # Nếu người học bấm nút "Hoàn thành Bài giảng & Thực hành Ngay", chuyển thẳng tới Phòng Lab của bài giảng đó
    next_ex_slug = request.form.get("next_exercise_slug")
    if next_ex_slug:
        return redirect(url_for("judge.workspace", slug=next_ex_slug))

    return redirect(url_for("main.lesson_detail", slug=lesson.slug))


@main_bp.route("/mentor-portal")
@role_required("instructor", "admin")
def mentor_portal():
    """
    Cổng quản lý dành cho Mentor/Giảng viên và Quản trị viên (Module M10):
    - Xem tiến độ và nhận xét bài làm của người học.
    - Quản lý tài khoản và phân quyền (Admin).
    """
    learners = User.query.order_by(User.total_xp.desc()).all()
    submissions = Submission.query.order_by(Submission.created_at.desc()).limit(15).all()
    skills = Skill.query.order_by(Skill.tier.asc()).all()
    return render_template(
        "mentor_portal.html",
        learners=learners,
        submissions=submissions,
        skills=skills,
    )


@main_bp.route("/mentor-portal/review/<int:submission_id>", methods=["POST"])
@role_required("instructor", "admin")
def review_submission(submission_id: int):
    sub = db.session.get(Submission, submission_id)
    if sub:
        sub.mentor_comment = request.form.get("mentor_comment", "").strip()
        sub.mentor_name = current_user.username
        db.session.commit()
        flash(f"Đã lưu nhận xét của Mentor cho bài nộp #{sub.id} của {sub.user.username}!", "success")
    return redirect(url_for("main.mentor_portal"))


@main_bp.route("/mentor-portal/role/<int:user_id>", methods=["POST"])
@role_required("admin")
def update_user_role(user_id: int):
    user = db.session.get(User, user_id)
    new_role = request.form.get("role")
    if user and new_role in ("learner", "instructor", "admin"):
        user.role = new_role
        db.session.commit()
        flash(f"Đã cập nhật quyền của tài khoản {user.username} thành {new_role.upper()}.", "success")
    return redirect(url_for("main.mentor_portal"))
