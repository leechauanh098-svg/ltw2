from flask import current_app
from app.extensions import db, judge_executor
from app.models import Submission, Exercise, User, Skill
from app.workers.sandbox_runner import run_testcase_in_sandbox, normalize_output
from app.services.dag_service import sync_user_skill_tree
from app.services.ai_tutor_service import generate_vietnamese_ai_feedback, award_badge_if_not_owned
from app.services.m16_service import award_xp


def evaluate_submission_task(app, submission_id: int) -> None:
    """
    Hàm chạy trong Background Thread (không cần Redis/Celery).
    Chấm lần lượt từng TestCase của bài tập và cập nhật kết quả, XP, Huy hiệu, Giải thích AI và Skill Tree.
    """
    with app.app_context():
        sub = db.session.get(Submission, submission_id)
        if not sub:
            return

        sub.status = "RUNNING"
        db.session.commit()

        exercise = db.session.get(Exercise, sub.exercise_id)
        test_cases = exercise.test_cases

        if not test_cases:
            sub.status = "AC"
            sub.passed_test_cases = 0
            sub.total_test_cases = 0
            db.session.commit()
            return

        already_ac = (
            Submission.query.filter(
                Submission.user_id == sub.user_id,
                Submission.exercise_id == sub.exercise_id,
                Submission.status == "AC",
                Submission.id != sub.id,
            ).first()
            is not None
        )

        passed_count = 0
        max_time_ms = 0
        max_mem_kb = 0
        overall_verdict = "AC"
        details = []
        first_failed_stderr = ""
        first_failed_expected = ""
        first_failed_actual = ""

        for idx, tc in enumerate(test_cases, start=1):
            res = run_testcase_in_sandbox(
                language=sub.language,
                source_code=sub.source_code,
                stdin_data=tc.input_data,
                expected_output=tc.expected_output,
                time_limit_ms=exercise.time_limit_ms,
                memory_limit_kb=exercise.memory_limit_kb,
            )

            max_time_ms = max(max_time_ms, res.execution_time_ms)
            max_mem_kb = max(max_mem_kb, res.memory_used_kb)

            if res.verdict == "AC":
                passed_count += 1
            elif overall_verdict == "AC":
                overall_verdict = res.verdict
                first_failed_stderr = res.stderr
                first_failed_expected = normalize_output(tc.expected_output)
                first_failed_actual = normalize_output(res.stdout)

            details.append(
                {
                    "index": idx,
                    "is_sample": tc.is_sample,
                    "verdict": res.verdict,
                    "time_ms": res.execution_time_ms,
                    "memory_kb": res.memory_used_kb,
                    "input": tc.input_data if tc.is_sample else "[Test case ẩn]",
                    "expected_output": normalize_output(tc.expected_output)
                    if tc.is_sample
                    else "[Ẩn]",
                    "actual_output": normalize_output(res.stdout)
                    if tc.is_sample
                    else ("[Đúng]" if res.verdict == "AC" else "[Sai kết quả]"),
                    "stderr": res.stderr[:500] if res.stderr else "",
                }
            )

            if res.verdict == "CE":
                break

        # Sinh nhận xét từ Trợ lý AI bằng tiếng Việt
        next_skill = Skill.query.filter(Skill.tier > (exercise.skill.tier if exercise.skill else 1)).first()
        sub.ai_explanation = generate_vietnamese_ai_feedback(
            verdict=overall_verdict,
            source_code=sub.source_code,
            stderr_text=first_failed_stderr,
            expected_out=first_failed_expected,
            actual_out=first_failed_actual,
            exercise_title=exercise.title,
            hints=exercise.hints or [],
            next_skill_name=next_skill.name if next_skill else "Lập trình Web Backend với Flask",
        )

        sub.status = overall_verdict
        sub.passed_test_cases = passed_count
        sub.total_test_cases = len(test_cases)
        sub.execution_time_ms = max_time_ms
        sub.memory_used_kb = max_mem_kb
        sub.details_json = details
        db.session.commit()

        # Nếu đạt AC lần đầu tiên -> Thưởng XP qua sổ cái M16, cập nhật Streak, trao Huy hiệu và mở khóa Cây Kỹ Năng (DAG)
        if overall_verdict == "AC" and not already_ac:
            award_xp(
                user_id=sub.user_id,
                event_key=f"exercise:{exercise.id}:ac",
                reason=f"Giải thành công bài tập: {exercise.title}",
                xp=exercise.xp_reward,
            )
            sync_user_skill_tree(sub.user_id)
            award_badge_if_not_owned(sub.user_id, "first_ac")


def enqueue_submission(submission_id: int) -> None:
    """Đẩy tác vụ chấm bài vào ThreadPoolExecutor bất đồng bộ."""
    app = current_app._get_current_object()
    judge_executor.submit(evaluate_submission_task, app, submission_id)
