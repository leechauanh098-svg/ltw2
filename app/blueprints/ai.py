from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.services.ai_helper_service import AIError, explain_error

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


@ai_bp.route("/explain", methods=["POST"])
@login_required
def explain():
    data = request.get_json(silent=True) or request.form
    code = str(data.get("code", ""))[:4000]
    error = str(data.get("error", "")).strip()[:2000]
    try:
        level = int(data.get("level", 1))
    except (TypeError, ValueError):
        level = 1

    if not error:
        return jsonify(ok=False, error="Hãy nhập thông báo lỗi hoặc câu hỏi"), 400

    try:
        answer = explain_error(code, error, level)
    except AIError as e:
        return jsonify(ok=False, error=str(e)), 503
    return jsonify(ok=True, answer=answer)
