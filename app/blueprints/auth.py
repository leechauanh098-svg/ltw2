from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from app.services.dag_service import sync_user_skill_tree
from app.services.ai_tutor_service import award_badge_if_not_owned

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def role_required(*roles):
    """Decorator kiểm soát phân quyền RBAC (Learner / Instructor / Admin)."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        if user and user.check_password(password):
            login_user(user)
            sync_user_skill_tree(user.id)
            flash(f"Chào mừng {user.username} quay trở lại lộ trình Lập trình Web!", "success")
            return redirect(url_for("main.dashboard"))
        flash("Tên đăng nhập hoặc mật khẩu không chính xác.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("Vui lòng điền đầy đủ thông tin đăng ký.", "warning")
        return redirect(url_for("auth.login"))

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("Tên người dùng hoặc email đã tồn tại.", "danger")
        return redirect(url_for("auth.login"))

    user = User(username=username, email=email, role="learner", total_xp=10)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    sync_user_skill_tree(user.id)
    award_badge_if_not_owned(user.id, "welcome_web")
    login_user(user)
    flash("Đăng ký thành công! Bạn nhận được huy hiệu 'Tân binh Lập trình Web' (+10 XP).", "success")
    return redirect(url_for("main.placement_test"))


@auth_bp.route("/quick-login/<role>")
def quick_login(role: str):
    """Đăng nhập nhanh 1-click dành cho 3 vai trò: Người học, Mentor/Giảng viên, Quản trị viên."""
    role_map = {
        "learner": "hocvien",
        "instructor": "mentor",
        "admin": "admin",
    }
    target_username = role_map.get(role, "hocvien")
    user = User.query.filter_by(username=target_username).first()
    if user:
        login_user(user)
        sync_user_skill_tree(user.id)
        flash(f"Đã đăng nhập nhanh với vai trò {user.role.upper()} ({user.username})!", "info")
        return redirect(url_for("main.dashboard"))
    flash("Tài khoản demo chưa được khởi tạo.", "warning")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Đã đăng xuất. Bạn hiện đang ở chế độ Khách (Guest).", "info")
    return redirect(url_for("main.landing"))
