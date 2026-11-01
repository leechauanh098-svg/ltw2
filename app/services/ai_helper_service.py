import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"

LEVEL_RULES = {
    1: "Chỉ gợi ý hướng suy nghĩ. KHÔNG đưa ra đoạn code sửa lỗi.",
    2: "Chỉ ra chính xác dòng hoặc khái niệm gây lỗi. KHÔNG viết lại toàn bộ code.",
    3: "Giải thích đầy đủ nguyên nhân và đưa ví dụ cách sửa.",
}

BASE_PROMPT = (
    "Bạn là trợ lý học lập trình web cho người mới bắt đầu. "
    "Trả lời bằng tiếng Việt, ngắn gọn, thân thiện."
)


class AIError(Exception):
    pass


def _fallback_explain(code: str, error: str, level: int) -> str:
    """Fallback giải thích lỗi tiếng Việt theo 3 mức khi chưa cấu hình ANTHROPIC_API_KEY."""
    err_lower = error.lower()
    if level == 1:
        return (
            "💡 [Mức 1 - Gợi ý hướng suy nghĩ]:\n"
            f"- Hãy đọc kỹ thông báo: \"{error[:120]}\".\n"
            "- Kiểm tra lại kiểu dữ liệu đầu vào/đầu ra và điều kiện dừng hoặc cú pháp đóng mở thẻ/ngoặc trong đoạn code của bạn."
        )
    if level == 2:
        concept = "cú pháp hoặc biến chưa khởi tạo đúng"
        if "syntax" in err_lower or "indentation" in err_lower:
            concept = "lỗi cú pháp hoặc thụt lề (SyntaxError / IndentationError)"
        elif "nameerror" in err_lower or "not defined" in err_lower:
            concept = "gọi biến/hàm trước khi khai báo (NameError)"
        elif "typeerror" in err_lower or "valueerror" in err_lower:
            concept = "ép kiểu hoặc thao tác giữa hai kiểu dữ liệu không tương thích (TypeError / ValueError)"
        elif "indexerror" in err_lower:
            concept = "truy cập chỉ số vượt quá độ dài danh sách (IndexError)"
        return (
            f"🔍 [Mức 2 - Chỉ chỗ sai]:\n"
            f"- Nguyên nhân trực tiếp nằm ở: {concept}.\n"
            f"- Hãy rà soát dòng báo lỗi liên quan đến `{error[:100]}` và đối chiếu lại tên biến cũng như kiểu dữ liệu tại dòng đó."
        )
    return (
        "🛠️ [Mức 3 - Giải thích chi tiết & Ví dụ cách sửa]:\n"
        f"- Thông báo `{error[:120]}` xảy ra khi chương trình gặp biểu thức không hợp lệ hoặc kết quả trả về lệch định dạng.\n"
        "- Cách khắc phục mẫu:\n"
        "  1. Đảm bảo đọc dữ liệu bằng `sys.stdin.read().strip()` hoặc kiểm tra danh sách khác rỗng.\n"
        "  2. Nếu ghép chuỗi HTML, dùng f-string chuẩn như: `return f\"<h1>{title_text}</h1>\"`."
    )


def explain_error(code: str, error: str, level: int) -> str:
    if level not in LEVEL_RULES:
        level = 1

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_explain(code, error, level)

    payload = {
        "model": os.getenv("AI_MODEL", "claude-haiku-4-5"),
        "max_tokens": 600,
        "system": f"{BASE_PROMPT}\n{LEVEL_RULES[level]}",
        "messages": [{"role": "user", "content": f"Code:\n{code}\n\nLỗi:\n{error}"}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as e:
        raise AIError("Không gọi được AI, vui lòng thử lại sau") from e

    return "\n".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    ).strip()
