import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app import create_app
from app.extensions import db, socketio
from app.seed import seed_initial_data, seed_buddy_demo, seed_m16_data

app = create_app()


def init_db_and_seed():
    with app.app_context():
        db.create_all()
        seed_initial_data()
        seed_buddy_demo()
        seed_m16_data()


# Tự động khởi tạo database và seed dữ liệu khi khởi động (hỗ trợ Gunicorn trên Render)
init_db_and_seed()


if __name__ == "__main__":
    print("\n" + "=" * 75)
    print("🚀 WEBSITE HỌC LẬP TRÌNH WEB THEO LỘ TRÌNH NEU (TÍCH HỢP M10 + M12 + M16)")
    print("👉 Truy cập ngay tại: http://127.0.0.1:5000")
    print("👤 Vai trò 1 - Khách (Guest): Xem giới thiệu, Cây kỹ năng mẫu, Test đầu vào")
    print("🎓 Vai trò 2 - Người học:     hocvien / 123456 (Bạn học: minh_anh_k65 / 123456)")
    print("👨‍🏫 Vai trò 3 - Mentor / GV:   mentor  / 123456")
    print("🛡️  Vai trò 4 - Quản trị viên: admin   / 123456")
    print("=" * 75 + "\n")
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, allow_unsafe_werkzeug=True)
