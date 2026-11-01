from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models import Skill, SkillPrerequisite, UserSkillProgress, Exercise, Submission, User


def would_create_cycle(skill_id: int, prerequisite_id: int) -> bool:
    """
    Kiểm tra xem việc thêm cạnh có hướng (prerequisite_id -> skill_id)
    có tạo ra chu trình trên đồ thị Cây kỹ năng (DAG) hay không.
    """
    if skill_id == prerequisite_id:
        return True

    edges = SkillPrerequisite.query.all()
    adj = defaultdict(list)
    for edge in edges:
        adj[edge.prerequisite_id].append(edge.skill_id)

    queue = deque([skill_id])
    visited = {skill_id}
    while queue:
        curr = queue.popleft()
        if curr == prerequisite_id:
            return True
        for nxt in adj[curr]:
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return False


def sync_user_skill_tree(user_id: int) -> List[str]:
    """
    Đồng bộ trạng thái Cây kỹ năng (DAG) của học viên:
    1. Các node gốc (không có điều kiện tiên quyết) mặc định được mở khóa ('unlocked').
    2. Nếu một node có số bài tập AC >= required_exercises_count (hoặc đã được mở khóa qua Test đầu vào) -> 'mastered'.
    3. Nếu tất cả các node cha (prerequisites) của node X đã 'mastered' -> mở khóa node X ('unlocked').
    """
    skills = Skill.query.order_by(Skill.tier.asc()).all()
    edges = SkillPrerequisite.query.all()

    prereq_map = defaultdict(list)
    for e in edges:
        prereq_map[e.skill_id].append(e.prerequisite_id)

    existing_progress = {
        p.skill_id: p for p in UserSkillProgress.query.filter_by(user_id=user_id).all()
    }

    ac_exercise_ids = {
        row[0]
        for row in db.session.query(Submission.exercise_id)
        .filter_by(user_id=user_id, status="AC")
        .distinct()
        .all()
    }
    exercises_by_skill = defaultdict(list)
    for ex in Exercise.query.all():
        if ex.skill_id:
            exercises_by_skill[ex.skill_id].append(ex)

    newly_updated = []
    now = datetime.now(timezone.utc)

    changed = True
    while changed:
        changed = False
        for skill in skills:
            prog = existing_progress.get(skill.id)
            if not prog:
                prog = UserSkillProgress(
                    user_id=user_id,
                    skill_id=skill.id,
                    status="locked",
                    earned_xp=0,
                    completed_exercises=0,
                )
                db.session.add(prog)
                existing_progress[skill.id] = prog

            skill_exs = exercises_by_skill.get(skill.id, [])
            completed_cnt = sum(1 for ex in skill_exs if ex.id in ac_exercise_ids)
            earned_xp = sum(ex.xp_reward for ex in skill_exs if ex.id in ac_exercise_ids)

            # Giữ nguyên nếu đã được đánh dấu mastered từ bài Test đầu vào
            if prog.status != "mastered":
                prog.completed_exercises = completed_cnt
                prog.earned_xp = earned_xp
            else:
                prog.completed_exercises = max(prog.completed_exercises, completed_cnt)
                prog.earned_xp = max(prog.earned_xp, earned_xp)

            parents = prereq_map.get(skill.id, [])
            all_parents_mastered = all(
                existing_progress.get(pid) and existing_progress[pid].status == "mastered"
                for pid in parents
            )

            if prog.status == "locked" and all_parents_mastered:
                prog.status = "unlocked"
                prog.unlocked_at = now
                newly_updated.append(f"Mở khóa kỹ năng: {skill.name}")
                changed = True

            if prog.status in ("unlocked", "in_progress"):
                req_cnt = max(1, skill.required_exercises_count)
                if completed_cnt >= req_cnt and earned_xp >= skill.required_xp:
                    prog.status = "mastered"
                    prog.mastered_at = now
                    newly_updated.append(f"Thành thạo kỹ năng: {skill.name}")
                    changed = True
                elif completed_cnt > 0 and prog.status == "unlocked":
                    prog.status = "in_progress"

    # Cập nhật node kỹ năng mục tiêu hiện tại của học viên (để ghép cặp Tìm bạn học cùng lộ trình)
    user = db.session.get(User, user_id)
    if user:
        active_skill = next(
            (
                s
                for s in skills
                if existing_progress.get(s.id)
                and existing_progress[s.id].status in ("unlocked", "in_progress")
            ),
            skills[-1] if skills else None,
        )
        if active_skill:
            user.current_focus_skill_id = active_skill.id

    db.session.commit()
    return newly_updated


def serialize_dag_for_cytoscape(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Xuất dữ liệu đồ thị DAG sang chuẩn JSON của Cytoscape.js + Dagre.
    Hỗ trợ cả Khách (user_id=None -> hiển thị cây kỹ năng mẫu) và Người học đã đăng nhập.
    """
    if user_id is not None:
        sync_user_skill_tree(user_id)
        progress_map = {
            p.skill_id: p for p in UserSkillProgress.query.filter_by(user_id=user_id).all()
        }
    else:
        progress_map = {}

    skills = Skill.query.order_by(Skill.tier.asc(), Skill.id.asc()).all()
    edges = SkillPrerequisite.query.all()

    nodes_data = []
    for s in skills:
        prog = progress_map.get(s.id)
        if user_id is None:
            status = "unlocked" if s.tier == 1 else "locked"
            completed = 0
            earned_xp = 0
        else:
            status = prog.status if prog else "locked"
            completed = prog.completed_exercises if prog else 0
            earned_xp = prog.earned_xp if prog else 0

        nodes_data.append(
            {
                "data": {
                    "id": f"skill_{s.id}",
                    "skill_id": s.id,
                    "slug": s.slug,
                    "name": s.name,
                    "tier": f"Tầng {s.tier}",
                    "description": s.description,
                    "status": status,
                    "completed_exercises": completed,
                    "required_exercises": s.required_exercises_count,
                    "earned_xp": earned_xp,
                    "required_xp": s.required_xp,
                    "progress_label": f"{completed}/{s.required_exercises_count} bài",
                }
            }
        )

    edges_data = []
    for e in edges:
        parent_prog = progress_map.get(e.prerequisite_id)
        edge_active = "true" if (parent_prog and parent_prog.status == "mastered") else "false"
        edges_data.append(
            {
                "data": {
                    "id": f"edge_{e.prerequisite_id}_{e.skill_id}",
                    "source": f"skill_{e.prerequisite_id}",
                    "target": f"skill_{e.skill_id}",
                    "active": edge_active,
                }
            }
        )

    return {"nodes": nodes_data, "edges": edges_data}
