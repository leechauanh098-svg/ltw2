from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event, Engine, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from app.extensions import db, login_manager


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


LargeText = db.Text().with_variant(LONGTEXT, "mysql")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(191), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum("learner", "instructor", "admin", name="user_roles", native_enum=False),
        default="learner",
        nullable=False,
    )
    total_xp = db.Column(db.Integer, default=0, nullable=False)
    current_streak = db.Column(db.Integer, default=1, nullable=False)
    placement_done = db.Column(db.Boolean, default=False, nullable=False)
    placement_level = db.Column(db.String(100), default="Người mới bắt đầu (Tier 1)")
    current_focus_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    focus_skill = db.relationship("Skill", foreign_keys=[current_focus_skill_id])
    badges = db.relationship("UserBadge", backref="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin_or_instructor(self) -> bool:
        return self.role in ("admin", "instructor")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Skill(db.Model):
    """Đỉnh (Node) trên đồ thị Cây kỹ năng Lập trình Web (HTML -> CSS -> JS -> DOM -> Backend)"""
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(100), default="code")
    tier = db.Column(db.Integer, default=1, nullable=False)
    required_xp = db.Column(db.Integer, default=0, nullable=False)
    required_exercises_count = db.Column(db.Integer, default=1, nullable=False)

    courses = db.relationship("Course", backref="skill", lazy="dynamic")
    exercises = db.relationship("Exercise", backref="skill", lazy="dynamic")


class SkillPrerequisite(db.Model):
    """Cạnh có hướng (Directed Edge) của đồ thị DAG: prerequisite_id -> skill_id"""
    __tablename__ = "skill_prerequisites"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    prerequisite_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("skill_id", "prerequisite_id", name="uq_skill_prereq"),
        CheckConstraint("skill_id != prerequisite_id", name="ck_no_self_loop"),
        Index("idx_dag_forward", "prerequisite_id", "skill_id"),
        Index("idx_dag_backward", "skill_id", "prerequisite_id"),
    )


class UserSkillProgress(db.Model):
    __tablename__ = "user_skill_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(
        db.Enum("locked", "unlocked", "in_progress", "mastered", name="skill_status", native_enum=False),
        default="locked",
        nullable=False,
    )
    earned_xp = db.Column(db.Integer, default=0, nullable=False)
    completed_exercises = db.Column(db.Integer, default=0, nullable=False)
    unlocked_at = db.Column(db.DateTime)
    mastered_at = db.Column(db.DateTime)

    skill = db.relationship("Skill")

    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
        Index("idx_user_skill_status", "user_id", "status"),
    )


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(191), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=True)

    lessons = db.relationship("Lesson", backref="course", order_by="Lesson.order_index", cascade="all, delete-orphan")


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(191), unique=True, nullable=False)
    order_index = db.Column(db.Integer, default=1, nullable=False)
    content_markdown = db.Column(LargeText, nullable=False)
    video_url = db.Column(db.String(500))
    xp_reward = db.Column(db.Integer, default=20, nullable=False)

    exercises = db.relationship("Exercise", backref="lesson", lazy="dynamic")

    __table_args__ = (Index("idx_lesson_course_order", "course_id", "order_index"),)


class UserLessonProgress(db.Model):
    __tablename__ = "user_lesson_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    time_spent_seconds = db.Column(db.Integer, default=0, nullable=False)
    completed_at = db.Column(db.DateTime)

    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)


class Exercise(db.Model):
    """Bài tập hướng dẫn từng bước có sẵn khung code (Scaffolded Starter Code & Hints)"""
    __tablename__ = "exercises"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"), index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(191), unique=True, nullable=False, index=True)
    problem_statement = db.Column(LargeText, nullable=False)
    difficulty = db.Column(
        db.Enum("easy", "medium", "hard", name="exercise_diff", native_enum=False),
        default="easy",
        nullable=False,
        index=True,
    )
    scaffold_level = db.Column(
        db.String(100), default="Mức 1: Có sẵn 70% khung code (Điền vào chỗ trống)"
    )
    hints = db.Column(db.JSON, default=list)  # Danh sách gợi ý từng bước cho người mới
    tags = db.Column(db.JSON, default=list)
    starter_code = db.Column(db.JSON, default=dict)
    time_limit_ms = db.Column(db.Integer, default=1500, nullable=False)
    memory_limit_kb = db.Column(db.Integer, default=65536, nullable=False)
    xp_reward = db.Column(db.Integer, default=50, nullable=False)

    test_cases = db.relationship(
        "TestCase", backref="exercise", order_by="TestCase.order_index", cascade="all, delete-orphan"
    )


class TestCase(db.Model):
    __tablename__ = "test_cases"
    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    input_data = db.Column(LargeText, nullable=False)
    expected_output = db.Column(LargeText, nullable=False)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    score_weight = db.Column(db.Integer, default=1, nullable=False)
    order_index = db.Column(db.Integer, default=1, nullable=False)


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    language = db.Column(db.String(32), default="python", nullable=False)
    source_code = db.Column(LargeText, nullable=False)
    status = db.Column(
        db.Enum(
            "PENDING", "RUNNING", "AC", "WA", "TLE", "MLE", "RE", "CE",
            name="submission_verdict", native_enum=False
        ),
        default="PENDING",
        nullable=False,
    )
    execution_time_ms = db.Column(db.Integer, default=0)
    memory_used_kb = db.Column(db.Integer, default=0)
    passed_test_cases = db.Column(db.Integer, default=0)
    total_test_cases = db.Column(db.Integer, default=0)
    details_json = db.Column(db.JSON, default=list)
    ai_explanation = db.Column(db.Text)       # Giải thích lỗi sai & gợi ý bằng tiếng Việt từ Trợ lý AI
    mentor_comment = db.Column(db.Text)       # Nhận xét của Mentor / Giảng viên
    mentor_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    exercise = db.relationship("Exercise")
    user = db.relationship("User")

    __table_args__ = (
        Index("idx_sub_user_created", "user_id", "created_at"),
        Index("idx_sub_user_ex_status", "user_id", "exercise_id", "status"),
    )


class Roadmap(db.Model):
    __tablename__ = "roadmaps"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(191), unique=True, nullable=False)
    description = db.Column(db.Text)
    target_role = db.Column(db.String(100))

    nodes = db.relationship(
        "RoadmapNode", backref="roadmap", order_by="RoadmapNode.step_order", cascade="all, delete-orphan"
    )


class RoadmapNode(db.Model):
    __tablename__ = "roadmap_nodes"
    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    branch_name = db.Column(db.String(100), default="Core")

    skill = db.relationship("Skill")


class PlacementQuestion(db.Model):
    """Ngân hàng câu hỏi Test đầu vào để đánh giá năng lực xếp lộ trình (M10 & M16)"""
    __tablename__ = "placement_questions"
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"))
    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.JSON, nullable=False)  # ["A...", "B...", "C...", "D..."]
    correct_index = db.Column(db.Integer, default=0, nullable=False)
    explanation = db.Column(db.Text)
    difficulty_tier = db.Column(db.Integer, default=1, nullable=False)
    topic = db.Column(db.String(64), default="HTML", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    skill = db.relationship("Skill")


class PlacementTestResult(db.Model):
    """Lịch sử làm bài kiểm tra đầu vào & đánh giá năng lực (Module M16)"""
    __tablename__ = "placement_test_results"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Integer, default=0, nullable=False)
    correct_count = db.Column(db.Integer, default=0, nullable=False)
    total_questions = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.String(64), nullable=False)
    recommended_path = db.Column(db.String(150), nullable=False)
    answers_json = db.Column(db.JSON, default=dict)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User")


class XpEvent(db.Model):
    """Sổ cái điểm kinh nghiệm chống cộng trùng (Module M16)"""
    __tablename__ = "xp_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key = db.Column(db.String(150), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    xp = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_user_xp_event"),
        CheckConstraint("xp > 0", name="ck_xp_positive"),
    )


class UserStreak(db.Model):
    """Theo dõi chuỗi ngày học liên tiếp (Module M16)"""
    __tablename__ = "user_streaks"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    current_streak = db.Column(db.Integer, default=1, nullable=False)
    longest_streak = db.Column(db.Integer, default=1, nullable=False)
    last_study_date = db.Column(db.Date)

    user = db.relationship("User")


class Badge(db.Model):
    """Huy hiệu thành tích (Gamification kiểu Duolingo/freeCodeCamp - M10 & M16)"""
    __tablename__ = "badges"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    icon = db.Column(db.String(64), default="fa-medal")
    color = db.Column(db.String(32), default="blue")
    required_xp = db.Column(db.Integer, default=0, nullable=False)
    required_streak = db.Column(db.Integer, default=0, nullable=False)


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    awarded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    badge = db.relationship("Badge")

    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)
