import markdown
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Exercise, Submission, UserSkillProgress, Skill, UserLessonProgress
from app.workers.sandbox_runner import run_testcase_in_sandbox, normalize_output
from app.workers.judge_worker import enqueue_submission
from app.services.dag_service import sync_user_skill_tree
from app.services.ai_tutor_service import generate_vietnamese_ai_feedback

judge_bp = Blueprint("judge", __name__, url_prefix="/judge")


@judge_bp.route("/workspace/<slug>")
@login_required
def workspace(slug: str):
    exercise = Exercise.query.filter_by(slug=slug).first_or_404()
    sync_user_skill_tree(current_user.id)

    problem_html = markdown.markdown(
        exercise.problem_statement, extensions=["fenced_code", "tables"]
    )
    lesson_html = ""
    lesson_completed = False
    if exercise.lesson:
        lesson_html = markdown.markdown(
            exercise.lesson.content_markdown, extensions=["fenced_code", "tables"]
        )
        lesson_completed = (
            UserLessonProgress.query.filter_by(
                user_id=current_user.id, lesson_id=exercise.lesson.id, is_completed=True
            ).first()
            is not None
        )

    sample_tests = [tc for tc in exercise.test_cases if tc.is_sample]
    my_submissions = (
        Submission.query.filter_by(user_id=current_user.id, exercise_id=exercise.id)
        .order_by(Submission.created_at.desc())
        .limit(10)
        .all()
    )

    skill_prog = None
    if exercise.skill_id:
        skill_prog = UserSkillProgress.query.filter_by(
            user_id=current_user.id, skill_id=exercise.skill_id
        ).first()

    return render_template(
        "judge/workspace.html",
        exercise=exercise,
        problem_html=problem_html,
        lesson_html=lesson_html,
        lesson_completed=lesson_completed,
        sample_tests=sample_tests,
        my_submissions=my_submissions,
        skill_prog=skill_prog,
    )


@judge_bp.route("/api/run-sample", methods=["POST"])
@login_required
def run_sample():
    """Chạy thử trực tiếp với các Sample Test Cases công khai + Trợ lý AI giải thích lỗi tiếng Việt."""
    data = request.get_json() or {}
    exercise_id = data.get("exercise_id")
    language = data.get("language", "python")
    source_code = data.get("source_code", "")

    exercise = db.session.get(Exercise, exercise_id)
    if not exercise:
        return jsonify({"error": "Không tìm thấy bài tập"}), 404

    sample_cases = [tc for tc in exercise.test_cases if tc.is_sample]
    results = []
    overall = "AC"
    first_stderr = ""
    first_exp = ""
    first_act = ""

    for idx, tc in enumerate(sample_cases, start=1):
        res = run_testcase_in_sandbox(
            language=language,
            source_code=source_code,
            stdin_data=tc.input_data,
            expected_output=tc.expected_output,
            time_limit_ms=exercise.time_limit_ms,
            memory_limit_kb=exercise.memory_limit_kb,
        )
        if res.verdict != "AC" and overall == "AC":
            overall = res.verdict
            first_stderr = res.stderr
            first_exp = normalize_output(tc.expected_output)
            first_act = normalize_output(res.stdout)

        results.append(
            {
                "index": idx,
                "verdict": res.verdict,
                "time_ms": res.execution_time_ms,
                "memory_kb": res.memory_used_kb,
                "input": tc.input_data,
                "expected_output": normalize_output(tc.expected_output),
                "actual_output": normalize_output(res.stdout),
                "stderr": res.stderr[:500] if res.stderr else "",
            }
        )

    ai_feedback = generate_vietnamese_ai_feedback(
        verdict=overall,
        source_code=source_code,
        stderr_text=first_stderr,
        expected_out=first_exp,
        actual_out=first_act,
        exercise_title=exercise.title,
        hints=exercise.hints or [],
    )

    return jsonify(
        {
            "overall_verdict": overall,
            "details": results,
            "ai_explanation": ai_feedback,
        }
    )


@judge_bp.route("/api/submit", methods=["POST"])
@login_required
def submit_code():
    """Tạo bản ghi Submission (PENDING) và đẩy vào Background Thread chấm bất đồng bộ."""
    data = request.get_json() or {}
    exercise_id = data.get("exercise_id")
    language = data.get("language", "python")
    source_code = data.get("source_code", "")

    exercise = db.session.get(Exercise, exercise_id)
    if not exercise:
        return jsonify({"error": "Không tìm thấy bài tập"}), 404

    sub = Submission(
        user_id=current_user.id,
        exercise_id=exercise.id,
        language=language,
        source_code=source_code,
        status="PENDING",
    )
    db.session.add(sub)
    db.session.commit()

    enqueue_submission(sub.id)

    return jsonify(
        {
            "submission_id": sub.id,
            "status": sub.status,
            "message": "Đã đưa bài nộp vào hàng đợi chấm tự động...",
        }
    ), 202


@judge_bp.route("/api/status/<int:submission_id>")
@login_required
def submission_status(submission_id: int):
    """API để Frontend Polling trạng thái chấm bài + Giải thích của Trợ lý AI theo thời gian thực."""
    sub = db.session.get(Submission, submission_id)
    if not sub or sub.user_id != current_user.id:
        return jsonify({"error": "Không tìm thấy bài nộp"}), 404

    return jsonify(
        {
            "submission_id": sub.id,
            "status": sub.status,
            "passed_test_cases": sub.passed_test_cases,
            "total_test_cases": sub.total_test_cases,
            "execution_time_ms": sub.execution_time_ms,
            "memory_used_kb": sub.memory_used_kb,
            "details": sub.details_json or [],
            "ai_explanation": sub.ai_explanation or "",
            "user_total_xp": current_user.total_xp,
        }
    )
