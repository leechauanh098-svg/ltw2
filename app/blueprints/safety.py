from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.blueprints.auth import role_required
from app.extensions import db
from app.models import Report, User, UserBlock

safety_bp = Blueprint("safety", __name__, url_prefix="/safety")


@safety_bp.route("/block", methods=["POST"])
@login_required
def block():
    target_id = request.form.get("target_id", type=int)
    if not target_id or target_id == current_user.id or not db.session.get(User, target_id):
        flash("Không tìm thấy người dùng.", "danger")
        return redirect(url_for("buddy.index"))

    exists = UserBlock.query.filter_by(blocker_id=current_user.id, blocked_id=target_id).first()
    if not exists:
        db.session.add(UserBlock(blocker_id=current_user.id, blocked_id=target_id))
        db.session.commit()
    flash("Đã chặn. Người này sẽ không còn xuất hiện trong danh sách và không nhắn tin được.", "success")
    return redirect(url_for("buddy.index"))


@safety_bp.route("/report", methods=["POST"])
@login_required
def report():
    target_id = request.form.get("target_id", type=int)
    reason = (request.form.get("reason") or "Khác").strip()[:100]
    detail = (request.form.get("detail") or "").strip()[:400]

    if not target_id or target_id == current_user.id or not db.session.get(User, target_id):
        flash("Không tìm thấy người dùng.", "danger")
        return redirect(url_for("buddy.index"))

    text = f"{reason}: {detail}" if detail else reason
    db.session.add(Report(reporter_id=current_user.id, target_user_id=target_id, reason=text))
    db.session.commit()
    flash("Đã gửi báo cáo. Admin sẽ xem xét.", "success")
    return redirect(url_for("buddy.index"))


@safety_bp.route("/admin/reports")
@role_required("admin")
def admin_reports():
    reports = Report.query.filter_by(status="open").order_by(Report.created_at).all()
    return render_template("safety/admin_reports.html", reports=reports)


@safety_bp.route("/admin/reports/<int:report_id>/resolve", methods=["POST"])
@role_required("admin")
def resolve_report(report_id: int):
    r = db.session.get(Report, report_id)
    if r:
        r.status = "resolved"
        db.session.commit()
        flash(f"Đã đánh dấu xử lý báo cáo #{report_id}.", "success")
    return redirect(url_for("safety.admin_reports"))
