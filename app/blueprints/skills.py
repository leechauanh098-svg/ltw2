from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import current_user
from app.extensions import db
from app.models import Skill, SkillPrerequisite, UserSkillProgress
from app.services.dag_service import (
    serialize_dag_for_cytoscape,
    would_create_cycle,
    sync_user_skill_tree,
)
from app.blueprints.auth import role_required

skills_bp = Blueprint("skills", __name__, url_prefix="/skills")


@skills_bp.route("/")
def tree_view():
    """Cho phép cả Khách (xem cây kỹ năng mẫu) và Người học xem Cây Kỹ Năng Lập trình Web."""
    if current_user.is_authenticated:
        sync_user_skill_tree(current_user.id)
    all_skills = Skill.query.order_by(Skill.tier.asc(), Skill.id.asc()).all()
    return render_template("skills/tree.html", all_skills=all_skills)


@skills_bp.route("/api/dag-graph")
def api_dag_graph():
    uid = current_user.id if current_user.is_authenticated else None
    data = serialize_dag_for_cytoscape(uid)
    return jsonify(data)


@skills_bp.route("/api/node/<int:skill_id>")
def api_skill_detail(skill_id: int):
    skill = db.session.get(Skill, skill_id)
    if not skill:
        return jsonify({"error": "Not found"}), 404

    prog = None
    if current_user.is_authenticated:
        prog = UserSkillProgress.query.filter_by(
            user_id=current_user.id, skill_id=skill.id
        ).first()

    prereq_edges = SkillPrerequisite.query.filter_by(skill_id=skill.id).all()
    prereq_names = [
        db.session.get(Skill, e.prerequisite_id).name
        for e in prereq_edges
        if db.session.get(Skill, e.prerequisite_id)
    ]

    exercises = [
        {
            "id": ex.id,
            "title": ex.title,
            "slug": ex.slug,
            "difficulty": ex.difficulty,
            "scaffold_level": ex.scaffold_level,
            "xp_reward": ex.xp_reward,
            "lesson_title": ex.lesson.title if ex.lesson else None,
            "lesson_slug": ex.lesson.slug if ex.lesson else None,
        }
        for ex in skill.exercises.all()
    ]
    courses = [
        {
            "title": c.title,
            "lessons": [{"title": l.title, "slug": l.slug} for l in c.lessons],
        }
        for c in skill.courses.all()
    ]

    status = prog.status if prog else ("unlocked" if skill.tier == 1 else "locked")

    return jsonify(
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "tier": skill.tier,
            "status": status,
            "completed_exercises": prog.completed_exercises if prog else 0,
            "required_exercises": skill.required_exercises_count,
            "earned_xp": prog.earned_xp if prog else 0,
            "required_xp": skill.required_xp,
            "prerequisites": prereq_names,
            "exercises": exercises,
            "courses": courses,
        }
    )


@skills_bp.route("/admin/add-edge", methods=["POST"])
@role_required("admin", "instructor")
def add_prerequisite_edge():
    """API dành cho Mentor/Admin thêm điều kiện tiên quyết trên DAG (có kiểm tra chống chu trình)."""
    prerequisite_id = int(request.form.get("prerequisite_id", 0))
    skill_id = int(request.form.get("skill_id", 0))

    if would_create_cycle(skill_id=skill_id, prerequisite_id=prerequisite_id):
        flash(
            "Lỗi DAG: Không thể thêm điều kiện tiên quyết này vì sẽ tạo ra chu trình (Cycle)!",
            "danger",
        )
        return redirect(url_for("skills.tree_view"))

    exists = SkillPrerequisite.query.filter_by(
        skill_id=skill_id, prerequisite_id=prerequisite_id
    ).first()
    if exists:
        flash("Điều kiện tiên quyết này đã tồn tại.", "warning")
    else:
        edge = SkillPrerequisite(skill_id=skill_id, prerequisite_id=prerequisite_id)
        db.session.add(edge)
        db.session.commit()
        flash("Đã thêm cạnh điều kiện tiên quyết vào Cây Kỹ Năng (DAG) thành công!", "success")

    return redirect(url_for("skills.tree_view"))
