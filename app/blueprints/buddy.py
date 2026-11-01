from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Roadmap
from app.services import buddy_service as svc

buddy_bp = Blueprint("buddy", __name__, url_prefix="/buddy")


@buddy_bp.route("/")
@login_required
def index():
    if current_user.role != "learner":
        flash("Tính năng Bạn học chỉ dành cho người học.", "warning")
        return redirect(url_for("main.dashboard"))

    roadmaps = Roadmap.query.order_by(Roadmap.id).all()
    profile = svc.get_profile(current_user.id)
    candidates = svc.find_candidates(current_user.id) if profile else []
    return render_template(
        "buddy/index.html", roadmaps=roadmaps, profile=profile, candidates=candidates
    )


@buddy_bp.route("/profile", methods=["POST"])
@login_required
def save_profile():
    roadmap_id = request.form.get("roadmap_id", type=int)
    level = request.form.get("level", type=int)
    available = request.form.get("available") == "on"

    if not roadmap_id or level not in (1, 2, 3) or not db.session.get(Roadmap, roadmap_id):
        flash("Thông tin hồ sơ không hợp lệ.", "danger")
        return redirect(url_for("buddy.index"))

    svc.save_profile(current_user.id, roadmap_id, level, available)
    flash("Đã lưu hồ sơ bạn học.", "success")
    return redirect(url_for("buddy.index"))


@buddy_bp.route("/swipe", methods=["POST"])
@login_required
def swipe():
    target_id = request.form.get("target_id", type=int)
    action = request.form.get("action")

    if not target_id or target_id == current_user.id or action not in ("like", "pass"):
        flash("Yêu cầu không hợp lệ.", "danger")
        return redirect(url_for("buddy.index"))

    try:
        result = svc.swipe(current_user.id, target_id, action)
    except ValueError as e:
        flash(str(e), "warning")
        return redirect(url_for("buddy.index"))

    if result["matched"]:
        flash("Ghép cặp thành công! Hãy bắt đầu trò chuyện.", "success")
        return redirect(url_for("chat.index", room=result["room_id"]))
    return redirect(url_for("buddy.index"))
