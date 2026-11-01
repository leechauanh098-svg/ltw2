import pytest
from config import TestConfig
from app import create_app
from app.extensions import db
from app.seed import seed_initial_data
from app.models import User, Skill, Exercise, Submission, UserSkillProgress
from app.services.dag_service import would_create_cycle
from app.workers.sandbox_runner import run_testcase_in_sandbox
from app.workers.judge_worker import evaluate_submission_task


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_initial_data()
        yield app
        db.session.remove()
        db.drop_all()


def test_sandbox_runner_verdicts():
    # 1. Kiểm thử Accepted (AC)
    res_ac = run_testcase_in_sandbox(
        language="python",
        source_code="import sys\nprint(f'<h1>{sys.stdin.read().strip()}</h1>')",
        stdin_data="Xin chao Web\n",
        expected_output="<h1>Xin chao Web</h1>\n",
        time_limit_ms=1000,
    )
    assert res_ac.verdict == "AC"

    # 2. Kiểm thử Wrong Answer (WA)
    res_wa = run_testcase_in_sandbox(
        language="python",
        source_code="print('<h2>Sai the</h2>')",
        stdin_data="Xin chao Web\n",
        expected_output="<h1>Xin chao Web</h1>\n",
        time_limit_ms=1000,
    )
    assert res_wa.verdict == "WA"

    # 3. Kiểm thử Time Limit Exceeded (TLE)
    res_tle = run_testcase_in_sandbox(
        language="python",
        source_code="while True: pass",
        stdin_data="",
        expected_output="",
        time_limit_ms=300,
    )
    assert res_tle.verdict == "TLE"

    # 4. Kiểm thử Runtime Error (RE)
    res_re = run_testcase_in_sandbox(
        language="python",
        source_code="print(1 / 0)",
        stdin_data="",
        expected_output="",
        time_limit_ms=1000,
    )
    assert res_re.verdict == "RE"


def test_web_dag_cycle_and_auto_unlock_with_ai_tutor(app):
    with app.app_context():
        s_html = Skill.query.filter_by(slug="html5-semantic").first()
        s_css = Skill.query.filter_by(slug="css3-flexbox-grid").first()
        s_flask = Skill.query.filter_by(slug="python-flask-backend").first()

        # Kiểm tra chống chu trình trên Cây kỹ năng Web (HTML -> CSS -> DOM -> Flask)
        assert would_create_cycle(skill_id=s_html.id, prerequisite_id=s_flask.id) is True

        learner = User.query.filter_by(username="hocvien").first()
        ex_html = Exercise.query.filter_by(slug="bo-sinh-the-tieu-de-html5").first()

        prog_css_before = UserSkillProgress.query.filter_by(
            user_id=learner.id, skill_id=s_css.id
        ).first()
        assert prog_css_before.status == "locked"

        # 1. Nếu sinh viên nộp nguyên khung code mẫu chưa điền đáp án (# TODO) -> phải báo WA và AI nhắc hoàn thiện TODO
        sub_todo = Submission(
            user_id=learner.id,
            exercise_id=ex_html.id,
            language="python",
            source_code=ex_html.starter_code["python"],
            status="PENDING",
        )
        db.session.add(sub_todo)
        db.session.commit()
        evaluate_submission_task(app, sub_todo.id)
        db.session.refresh(sub_todo)
        assert sub_todo.status == "WA"
        assert "TODO" in sub_todo.ai_explanation

        # 2. Khi sinh viên tự điền đúng đáp án vào khung code -> đạt AC và mở khóa Node Tầng 2
        completed_code = ex_html.starter_code["python"].replace(
            'return ""', 'return f"<h1>{title_text}</h1>"'
        )
        sub = Submission(
            user_id=learner.id,
            exercise_id=ex_html.id,
            language="python",
            source_code=completed_code,
            status="PENDING",
        )
        db.session.add(sub)
        db.session.commit()

        evaluate_submission_task(app, sub.id)

        db.session.refresh(sub)
        assert sub.status == "AC"
        assert sub.passed_test_cases == 3
        assert "Trợ lý AI" in sub.ai_explanation

        # Sau khi giải xong bài tập HTML5 (Tầng 1), Node CSS3 (Tầng 2) tự động mở khóa!
        prog_html_after = UserSkillProgress.query.filter_by(
            user_id=learner.id, skill_id=s_html.id
        ).first()
        prog_css_after = UserSkillProgress.query.filter_by(
            user_id=learner.id, skill_id=s_css.id
        ).first()

        assert prog_html_after.status == "mastered"
        assert prog_css_after.status == "unlocked"
