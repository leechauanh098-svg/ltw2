from typing import Dict, Any, List
from app.extensions import db
from app.models import Badge, UserBadge, Skill, UserSkillProgress


def generate_vietnamese_ai_feedback(
    verdict: str,
    source_code: str,
    stderr_text: str,
    expected_out: str,
    actual_out: str,
    exercise_title: str,
    hints: List[str],
    next_skill_name: str = "CSS3 & Flexbox hoặc JavaScript Căn bản",
) -> str:
    """
    Trợ lý AI tích hợp: Phân tích mã nguồn, trạng thái chấm (AC/WA/RE/CE/TLE) và thông báo lỗi
    để giải thích bằng tiếng Việt dễ hiểu cho người mới bắt đầu, kèm gợi ý bài học tiếp theo.
    """
    if "TODO" in source_code and verdict != "AC":
        return (
            "🤖 **Trợ lý AI phát hiện bạn chưa điền hết khung code mẫu:**\n"
            "- Trong bài tập hướng dẫn từng bước này, vẫn còn vị trí đánh dấu `# TODO` chưa được hoàn thiện.\n"
            f"- **Gợi ý bước 1:** {hints[0] if hints else 'Hãy đọc kỹ phần hướng dẫn ở khung bên trái và thay thế dòng TODO bằng biểu thức tính toán phù hợp.'}"
        )

    if verdict == "AC":
        return (
            f"🎉 **Xuất sắc! Trợ lý AI xác nhận code của bạn đã vượt qua 100% Test Cases cho bài '{exercise_title}'.**\n"
            "- **Điểm mạnh:** Bạn đã sử dụng đúng cấu trúc khung code và xử lý chuẩn xác định dạng Đầu vào/Đầu ra.\n"
            f"- **Gợi ý lộ trình tiếp theo:** Bạn đã sẵn sàng chinh phục bài học tiếp theo hoặc mở khóa nhánh **{next_skill_name}** trên Cây Kỹ Năng!"
        )

    if verdict == "CE":
        return (
            "🤖 **Giải thích lỗi Biên dịch / Cú pháp (Compilation Error) bằng tiếng Việt:**\n"
            "- Chương trình chưa thể chạy do viết sai cú pháp ngôn ngữ (ví dụ: thiếu dấu ngoặc `)`, dấu hai chấm `:`, hoặc thụt lề `IndentationError` chưa thẳng hàng).\n"
            f"- **Chi tiết kỹ thuật:** `{stderr_text[:220]}`\n"
            f"- **Gợi ý sửa nhanh:** {hints[0] if hints else 'Kiểm tra lại dòng báo lỗi xem đã đóng đủ ngoặc và thụt lề 4 dấu cách chuẩn Python chưa.'}"
        )

    if verdict == "RE":
        explanation = "Chương trình gặp lỗi phát sinh trong lúc đang chạy (Runtime Error)."
        if "ZeroDivisionError" in stderr_text:
            explanation = "Bạn đang thực hiện phép chia cho số `0` (`ZeroDivisionError`)."
        elif "IndexError" in stderr_text:
            explanation = "Bạn đang truy cập phần tử vượt quá độ dài của danh sách/mảng (`IndexError: list index out of range`)."
        elif "ValueError" in stderr_text:
            explanation = "Dữ liệu đầu vào không thể ép kiểu sang số nguyên (`ValueError`). Hãy kiểm tra lại hàm `split()` hoặc `int()`."
        elif "NameError" in stderr_text:
            explanation = "Bạn đang gọi tên một biến hoặc hàm chưa được khai báo (`NameError`)."
        elif "EOFError" in stderr_text:
            explanation = "Hàm `input()` đọc quá số dòng dữ liệu hiện có (`EOFError`). Hãy dùng `sys.stdin.read()` theo khung code mẫu."

        return (
            f"🤖 **Giải thích lỗi Thực thi (Runtime Error) bằng tiếng Việt:**\n"
            f"- **Nguyên nhân chính:** {explanation}\n"
            f"- **Gợi ý từng bước:** {hints[0] if hints else 'Hãy đối chiếu lại biến bạn vừa viết trong phần khung code với tên biến đã khai báo ở phía trên.'}"
        )

    if verdict == "TLE":
        return (
            "🤖 **Giải thích lỗi Quá thời gian giới hạn (Time Limit Exceeded - TLE):**\n"
            "- Chương trình chạy quá lâu (thường do vòng lặp `while` không có điều kiện dừng hoặc thuật toán lồng nhau quá nhiều cấp).\n"
            f"- **Gợi ý tối ưu:** {hints[-1] if hints else 'Kiểm tra điều kiện thoát của vòng lặp để tránh lặp vô tận.'}"
        )

    # Mặc định: Wrong Answer (WA)
    diff_hint = ""
    if expected_out and actual_out:
        if expected_out.lower() == actual_out.lower():
            diff_hint = "Kết quả của bạn đúng nội dung nhưng **sai chữ HOA / chữ thường** (ví dụ in `yes` thay vì `YES` hoặc sai tên thẻ HTML)."
        else:
            diff_hint = f"Với bộ test mẫu, hệ thống kỳ vọng kết quả là `{expected_out}` nhưng code của bạn lại in ra `{actual_out}`."

    return (
        "🤖 **Giải thích lỗi Sai kết quả (Wrong Answer - WA) bằng tiếng Việt:**\n"
        f"- **Phân tích đối chiếu:** {diff_hint}\n"
        f"- **Gợi ý từng bước:** {hints[0] if hints else 'Hãy kiểm tra lại công thức hoặc định dạng chuỗi in ra trong hàm print().'}"
    )


def award_badge_if_not_owned(user_id: int, badge_code: str) -> bool:
    """Trao huy hiệu cho người học nếu chưa sở hữu."""
    badge = Badge.query.filter_by(code=badge_code).first()
    if not badge:
        return False
    exists = UserBadge.query.filter_by(user_id=user_id, badge_id=badge.id).first()
    if not exists:
        db.session.add(UserBadge(user_id=user_id, badge_id=badge.id))
        db.session.commit()
        return True
    return False
