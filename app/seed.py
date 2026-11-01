from app.extensions import db
from app.models import (
    User,
    Skill,
    SkillPrerequisite,
    Course,
    Lesson,
    Exercise,
    TestCase,
    Roadmap,
    RoadmapNode,
    PlacementQuestion,
    PlacementTestResult,
    XpEvent,
    UserStreak,
    Badge,
    UserBadge,
    BuddyProfile,
)
from app.services.dag_service import sync_user_skill_tree


def seed_initial_data() -> None:
    """
    Khởi tạo dữ liệu mẫu bám sát Đề cương Học phần của Khoa CNTT - Trường Đại học Kinh tế Quốc dân (NEU):
    1. Học phần Thiết kế Web (Mã HP: CNTT1165 - 3 tín chỉ)
    2. Học phần Lập trình Web (Mã HP: CNTT1188 - 3 tín chỉ, tiên quyết: CNTT1165)
    Thiết kế theo mô hình: ĐỌC BÀI GIẢNG TRƯỚC -> THỰC HÀNH CỦNG CỐ NGAY TRÊN WEB.
    """
    if User.query.first() is not None:
        return

    # 1. Tạo Huy hiệu (Badges)
    b1 = Badge(
        code="welcome_web",
        name="Sinh viên CNTT - NEU",
        description="Bắt đầu lộ trình học Thiết kế & Lập trình Web (CNTT1165 & CNTT1188).",
        icon="fa-graduation-cap",
        color="emerald",
    )
    b2 = Badge(
        code="placement_passed",
        name="Định vị Năng lực Web",
        description="Hoàn thành bài Test đầu vào để xếp lộ trình học cá nhân hóa.",
        icon="fa-compass",
        color="blue",
    )
    b3 = Badge(
        code="first_ac",
        name="Lý thuyết đi đôi Thực hành",
        description="Đọc bài giảng và giải thành công (AC) bài tập thực hành củng cố đầu tiên.",
        icon="fa-award",
        color="amber",
    )
    b4 = Badge(
        code="dag_explorer",
        name="Chinh phục CNTT1165 & CNTT1188",
        description="Mở khóa các nhánh kỹ năng Thiết kế Web Frontend & Lập trình Web Backend.",
        icon="fa-sitemap",
        color="indigo",
    )
    db.session.add_all([b1, b2, b3, b4])
    db.session.flush()

    # 2. Tạo Đồ thị Cây Kỹ Năng (DAG - 6 Nodes bám sát 2 học phần CNTT1165 & CNTT1188 của NEU)
    s_html = Skill(
        slug="html5-semantic",
        name="1. [CNTT1165] HTML5 & Cấu trúc Web",
        description="Chương 1 & 2 (Thiết kế Web): Nguyên lý WWW, cấu trúc tài liệu HTML5, bảng biểu, biểu mẫu (Form) và các thẻ ngữ nghĩa.",
        tier=1,
        required_xp=50,
        required_exercises_count=1,
    )
    s_css = Skill(
        slug="css3-flexbox-grid",
        name="2A. [CNTT1165] CSS3, Flexbox & Responsive",
        description="Chương 3 & 4 (Thiết kế Web): Bộ chọn CSS, Box Model, dàn trang với Flexbox/Grid và giao diện thích ứng đa thiết bị.",
        tier=2,
        required_xp=60,
        required_exercises_count=1,
    )
    s_js = Skill(
        slug="javascript-fundamentals",
        name="2B. [CNTT1165] Lập trình JavaScript Client",
        description="Chương 5 (Thiết kế Web): Cú pháp JavaScript ES6+, biến, kiểu dữ liệu, cấu trúc điều khiển, mảng và hàm xử lý phía trình duyệt.",
        tier=2,
        required_xp=60,
        required_exercises_count=1,
    )
    s_dom = Skill(
        slug="dom-events",
        name="3A. [CNTT1165] DOM, Sự kiện & Kiểm tra Form",
        description="Chương 6 (Thiết kế Web): Tương tác cây DOM, lắng nghe sự kiện (Event Handling) và kiểm tra hợp lệ biểu mẫu (Form Validation).",
        tier=3,
        required_xp=80,
        required_exercises_count=1,
    )
    s_async = Skill(
        slug="json-fetch-api",
        name="3B. [CNTT1188] Kiến trúc Client-Server & Web API",
        description="Chương 1 & 2 (Lập trình Web): Giao thức HTTP, mã trạng thái (Status Codes), RESTful Web API và trao đổi dữ liệu JSON.",
        tier=3,
        required_xp=80,
        required_exercises_count=1,
    )
    s_flask = Skill(
        slug="python-flask-backend",
        name="4. [CNTT1188] Backend MVC, CSDL & Thương mại Điện tử",
        description="Chương 3, 4 & 5 (Lập trình Web): Mô hình MVC, kết nối CSDL qua ORM (CRUD) và xây dựng nghiệp vụ Website Thương mại Điện tử.",
        tier=4,
        required_xp=100,
        required_exercises_count=1,
    )

    db.session.add_all([s_html, s_css, s_js, s_dom, s_async, s_flask])
    db.session.flush()

    edges = [
        SkillPrerequisite(prerequisite_id=s_html.id, skill_id=s_css.id),
        SkillPrerequisite(prerequisite_id=s_html.id, skill_id=s_js.id),
        SkillPrerequisite(prerequisite_id=s_css.id, skill_id=s_dom.id),
        SkillPrerequisite(prerequisite_id=s_js.id, skill_id=s_dom.id),
        SkillPrerequisite(prerequisite_id=s_js.id, skill_id=s_async.id),
        SkillPrerequisite(prerequisite_id=s_dom.id, skill_id=s_flask.id),
        SkillPrerequisite(prerequisite_id=s_async.id, skill_id=s_flask.id),
    ]
    db.session.add_all(edges)
    db.session.flush()

    # 3. Tạo Tài khoản 4 Vai trò + Bạn học cùng lộ trình tại NEU
    learner = User(
        username="hocvien",
        email="sv.cntt@neu.edu.vn",
        role="learner",
        total_xp=30,
        current_streak=4,
        placement_done=False,
        placement_level="Đang học: CNTT1165 - Chương 1 & 2 (HTML5)",
        current_focus_skill_id=s_html.id,
    )
    learner.set_password("123456")

    mentor = User(
        username="mentor",
        email="gv.cntt@neu.edu.vn",
        role="instructor",
        total_xp=450,
        current_streak=15,
        placement_done=True,
        placement_level="Giảng viên / Mentor Khoa CNTT - NEU",
        current_focus_skill_id=s_dom.id,
    )
    mentor.set_password("123456")

    admin = User(
        username="admin",
        email="admin.sitde@neu.edu.vn",
        role="admin",
        total_xp=980,
        current_streak=30,
        placement_done=True,
        placement_level="Quản trị viên Hệ thống LMS NEU",
        current_focus_skill_id=s_flask.id,
    )
    admin.set_password("123456")

    peer1 = User(
        username="minh_anh_k65",
        email="minhanh.k65@neu.edu.vn",
        role="learner",
        total_xp=55,
        current_streak=5,
        placement_done=True,
        placement_level="Đang học: [CNTT1165] HTML5 & Cấu trúc Web",
        current_focus_skill_id=s_html.id,
    )
    peer1.set_password("123456")

    peer2 = User(
        username="tuan_kiet_k65",
        email="tuankiet.k65@neu.edu.vn",
        role="learner",
        total_xp=115,
        current_streak=7,
        placement_done=True,
        placement_level="Đang học: [CNTT1165] CSS3 & Flexbox",
        current_focus_skill_id=s_css.id,
    )
    peer2.set_password("123456")

    peer3 = User(
        username="lan_huong_k64",
        email="lanhuong.k64@neu.edu.vn",
        role="learner",
        total_xp=160,
        current_streak=9,
        placement_done=True,
        placement_level="Đang học: [CNTT1188] Lập trình Web Backend",
        current_focus_skill_id=s_js.id,
    )
    peer3.set_password("123456")

    db.session.add_all([learner, mentor, admin, peer1, peer2, peer3])
    db.session.flush()
    db.session.add(UserBadge(user_id=learner.id, badge_id=b1.id))

    # 4. Ngân hàng Câu hỏi Test Đầu Vào (Bám sát đề cương CNTT1165 & CNTT1188)
    placement_questions = [
        PlacementQuestion(
            skill_id=s_html.id,
            difficulty_tier=1,
            question_text="Câu 1 [CNTT1165 - HTML5]: Thẻ HTML ngữ nghĩa nào dùng để bao bọc phần nội dung chính độc lập của một trang web?",
            options_json=["<main>", "<div id='main'>", "<section-main>", "<header>"],
            correct_index=0,
            explanation="Thẻ <main> trong HTML5 chỉ định nội dung chính của tài liệu, giúp công cụ tìm kiếm (SEO) và trình đọc màn hình nhận diện cấu trúc chuẩn.",
        ),
        PlacementQuestion(
            skill_id=s_css.id,
            difficulty_tier=2,
            question_text="Câu 2 [CNTT1165 - CSS3 Flexbox]: Để căn giữa các phần tử con theo trục chính (Main Axis) trong một khung Flexbox, ta dùng thuộc tính nào?",
            options_json=[
                "align-items: center;",
                "justify-content: center;",
                "display: block-center;",
                "text-align: middle;",
            ],
            correct_index=1,
            explanation="justify-content căn chỉnh các phần tử dọc theo trục chính (Main Axis), còn align-items căn theo trục phụ (Cross Axis).",
        ),
        PlacementQuestion(
            skill_id=s_js.id,
            difficulty_tier=2,
            question_text="Câu 3 [CNTT1165 - JavaScript]: Phương thức mảng nào trong ES6 tạo ra một mảng mới bằng cách áp dụng hàm biến đổi lên từng phần tử của mảng gốc?",
            options_json=["Array.forEach()", "Array.map()", "Array.filter()", "Array.push()"],
            correct_index=1,
            explanation="Array.map() duyệt qua từng phần tử và trả về một mảng mới có cùng độ dài với các giá trị đã biến đổi.",
        ),
        PlacementQuestion(
            skill_id=s_dom.id,
            difficulty_tier=3,
            question_text="Câu 4 [CNTT1165 - DOM & Events]: Phương thức chuẩn nào dùng để gắn bộ lắng nghe sự kiện 'click' vào một phần tử nút bấm trên DOM?",
            options_json=[
                "btn.addEventListener('click', handler)",
                "btn.onClickEvent(handler)",
                "document.click(btn, handler)",
                "btn.listen('click')",
            ],
            correct_index=0,
            explanation="addEventListener cho phép gắn nhiều hàm xử lý sự kiện lên cùng một phần tử DOM mà không ghi đè nhau.",
        ),
        PlacementQuestion(
            skill_id=s_flask.id,
            difficulty_tier=4,
            question_text="Câu 5 [CNTT1188 - Lập trình Web]: Khi trình duyệt gửi dữ liệu biểu mẫu Đăng nhập (gồm mật khẩu) lên Server, phương thức HTTP nào an toàn và đúng chuẩn nhất?",
            options_json=["GET", "POST", "DELETE", "HEAD"],
            correct_index=1,
            explanation="POST gửi dữ liệu bên trong phần thân (Request Body) thay vì hiển thị lộ liễu trên thanh địa chỉ URL như GET.",
        ),
    ]
    db.session.add_all(placement_questions)

    # 5. Hai Học phần Chuẩn Đề cương NEU: CNTT1165 (Thiết kế Web) & CNTT1188 (Lập trình Web)
    course_tkw = Course(
        skill_id=s_html.id,
        title="Học phần 1: Thiết kế Web (Mã HP: CNTT1165 - 3 Tín chỉ | Khoa CNTT - NEU)",
        slug="cntt1165-thiet-ke-web-neu",
        description="Trang bị kiến thức nền tảng và chuyên sâu về xây dựng giao diện Web (HTML5, CSS3, Flexbox/Grid, Responsive, JavaScript & DOM).",
    )
    course_ltw = Course(
        skill_id=s_async.id,
        title="Học phần 2: Lập trình Web (Mã HP: CNTT1188 - 3 Tín chỉ | Khoa CNTT - NEU)",
        slug="cntt1188-lap-trinh-web-neu",
        description="Kiến trúc Client-Server, RESTful Web API, mô hình MVC, kết nối Cơ sở dữ liệu (ORM) và xây dựng ứng dụng Thương mại Điện tử.",
    )
    db.session.add_all([course_tkw, course_ltw])
    db.session.flush()

    # 6. BÀI GIẢNG LÝ THUYẾT (ĐỌC TRƯỚC) -> GẮN TRỰC TIẾP VỚI BÀI TẬP THỰC HÀNH CỦNG CỐ (LÀM NGAY SAU ĐÓ)
    l1 = Lesson(
        course_id=course_tkw.id,
        title="[CNTT1165 - Chương 1 & 2] Tổng quan Web & Ngôn ngữ Đánh dấu HTML5 Ngữ nghĩa",
        slug="cntt1165-chuong-1-2-tong-quan-va-html5",
        order_index=1,
        xp_reward=25,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương CNTT1165 - Khoa CNTT NEU)
Trong Chương 1 & Chương 2 của học phần **Thiết kế Web (CNTT1165)**, sinh viên nắm vững:
- Nguyên lý hoạt động của **World Wide Web (WWW)**, khái niệm Trang web tĩnh (Static Web) và Trang web động (Dynamic Web).
- Cấu trúc chuẩn của một tài liệu **HTML5** và cách trình duyệt phân tích cú pháp thẻ đóng/mở.

## 2. Kiến thức Cốt lõi Cần Nhớ (Đọc kỹ trước khi làm bài thực hành)
Mọi phần tử HTML đều được cấu tạo bởi **Thẻ mở (Opening Tag)**, **Nội dung (Content)** và **Thẻ đóng (Closing Tag)**:

```html
<h1>Chào mừng Tân sinh viên Khoa CNTT - NEU</h1>
<p>Đây là đoạn văn bản mô tả khóa học Thiết kế Web.</p>
```

### Bảng các thẻ HTML5 Ngữ nghĩa (Semantic Tags) quan trọng:
| Thẻ HTML5 | Ý nghĩa & Công dụng |
| :--- | :--- |
| `<h1>` đến `<h6>` | Các cấp tiêu đề của trang web (`<h1>` là tiêu đề quan trọng nhất). |
| `<header>`, `<nav>` | Phần đầu trang và thanh điều hướng menu. |
| `<main>`, `<article>` | Phần nội dung chính độc lập của trang web. |
| `<form>`, `<input>` | Biểu mẫu thu thập dữ liệu từ người dùng gửi lên máy chủ. |

## 3. Áp dụng vào Bài tập Thực hành Củng cố ngay bên dưới
Khi lập trình giao diện hoặc viết hàm sinh giao diện tự động (Template Rendering), ta thường ghép chuỗi dữ liệu văn bản `title_text` vào giữa cặp thẻ `<h1>` và `</h1>`:
```python
def render_h1_tag(title_text: str) -> str:
    return f"<h1>{title_text}</h1>"
```
👉 **Hãy nhấn nút "Hoàn thành Bài đọc & Chuyển sang Thực hành" ở bên dưới để tự tay viết dòng code này trong Phòng Lab!**
""",
    )

    l2 = Lesson(
        course_id=course_tkw.id,
        title="[CNTT1165 - Chương 3 & 4] Định dạng CSS3, Box Model, Flexbox & Responsive Web Design",
        slug="cntt1165-chuong-3-4-css3-flexbox-responsive",
        order_index=2,
        xp_reward=25,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương CNTT1165 - Chương 3 & 4)
Sau khi dựng xong khung HTML5 ở Chương 2, Chương 3 & 4 trang bị cho bạn kỹ năng định dạng thẩm mỹ và chia bố cục đa thiết bị với **CSS3**:
- **Mô hình Hộp (CSS Box Model):** Gồm `Content` (Nội dung) $\rightarrow$ `Padding` (Đệm trong) $\rightarrow$ `Border` (Viền) $\rightarrow$ `Margin` (Lề ngoài).
- **Bố cục Flexbox (`display: flex`):** Dàn các khối sản phẩm/bài học nằm ngang trên cùng một hàng và cách đều nhau một khoảng `gap`.

## 2. Công thức Tính Độ rộng Cột trong Hệ thống Lưới (Grid / Flexbox)
Giả sử bạn thiết kế giao diện trang chủ có khung chứa rộng `container_width` (px), chia thành `cols` cột bằng nhau, và giữa các cột liền kề có khoảng trống `gap` (px):
- Số khoảng trống giữa `cols` cột luôn là: `(cols - 1)` khoảng trống.
- Tổng diện tích dành cho khoảng trống là: `total_gap = (cols - 1) * gap`.
- Độ rộng còn lại chia đều cho mỗi cột là:
```python
total_gap = (cols - 1) * gap
col_width = (container_width - total_gap) // cols
```

| Tham số đầu vào | Phép tính `total_gap` | Độ rộng mỗi cột (`col_width`) |
| :--- | :--- | :--- |
| `container = 1200px`, `cols = 3`, `gap = 30px` | `(3 - 1) * 30 = 60px` | `(1200 - 60) // 3 = 380px` |
| `container = 1000px`, `cols = 4`, `gap = 20px` | `(4 - 1) * 20 = 60px` | `(1000 - 60) // 4 = 235px` |

👉 **Hãy đọc kỹ công thức trên rồi bấm chuyển sang Bài tập Thực hành số 2 để củng cố kiến thức CSS Flexbox!**
""",
    )

    l3 = Lesson(
        course_id=course_tkw.id,
        title="[CNTT1165 - Chương 5] Lập trình JavaScript Phía Trình duyệt (Client-side Scripting)",
        slug="cntt1165-chuong-5-javascript-client-side",
        order_index=3,
        xp_reward=25,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương CNTT1165 - Chương 5)
HTML và CSS chỉ tạo ra trang web tĩnh. Để trang web có thể tính toán giỏ hàng, lọc sản phẩm ngay lập tức mà không cần tải lại trang, ta sử dụng ngôn ngữ kịch bản **JavaScript** (hoặc xử lý mảng tương đương trong Python):
- Làm việc với **Mảng / Danh sách (Arrays / Lists)** lưu giá các mặt hàng.
- Sử dụng **Cấu trúc rẽ nhánh (`if / else`)** để áp dụng quy tắc khuyến mãi thương mại điện tử.

## 2. Minh họa Xử lý Logic Giỏ hàng (Shopping Cart Logic)
Khi khách hàng thêm $N$ sản phẩm vào giỏ hàng với danh sách giá `prices`:
1. Tính tổng tiền gốc của toàn bộ sản phẩm: `total = sum(prices)`.
2. Kiểm tra điều kiện khuyến mãi: Nếu `total >= 500`, giảm trừ ngay `50` vào tổng thanh toán:
```python
total = sum(prices)
if total >= 500:
    total = total - 50
return total
```
👉 **Sau khi nắm vững quy tắc trên, hãy bấm xuống Bài tập Thực hành số 3 để tự hoàn thiện hàm tính tiền giỏ hàng!**
""",
    )

    l4 = Lesson(
        course_id=course_tkw.id,
        title="[CNTT1165 - Chương 6] Thao tác DOM, Sự kiện (Events) & Kiểm tra Biểu mẫu (Form Validation)",
        slug="cntt1165-chuong-6-dom-events-form-validation",
        order_index=4,
        xp_reward=30,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương CNTT1165 - Chương 6)
Trong ứng dụng Web thực tế, người dùng thường nhập sai định dạng dữ liệu vào các biểu mẫu Đăng ký / Đăng nhập. Kiểm tra dữ liệu ngay tại trình duyệt (**Client-side Form Validation**) giúp:
- Phản hồi tức thì cho người dùng mà không tốn băng thông gửi request lỗi lên Server.
- Bảo vệ hệ thống khỏi dữ liệu rác.

## 2. Quy tắc Kiểm tra Địa chỉ Email Hợp lệ
Một chuỗi `email` được coi là hợp lệ (`VALID`) khi thỏa mãn cả 3 điều kiện:
1. Không chứa dấu cách (`" " not in email`) và có đúng **1 ký tự `@`** (`email.count("@") == 1`).
2. Khi tách `local, domain = email.split("@")`, cả phần tên `local` và phần tên miền `domain` đều không được rỗng.
3. Phần `domain` phải chứa ít nhất một dấu chấm `.` và không bắt đầu hay kết thúc bằng dấu chấm (`not domain.startswith(".") and not domain.endswith(".")`).

```python
if " " in email or email.count("@") != 1:
    return "INVALID"
local, domain = email.split("@")
if not local or not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
    return "INVALID"
return "VALID"
```
👉 **Hãy chuyển sang Bài tập Thực hành số 4 bên dưới để lập trình bộ kiểm tra Form này!**
""",
    )

    l5 = Lesson(
        course_id=course_ltw.id,
        title="[CNTT1188 - Chương 1 & 2] Kiến trúc Client-Server, Giao thức HTTP & RESTful Web API",
        slug="cntt1188-chuong-1-2-client-server-http-api",
        order_index=1,
        xp_reward=30,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương Lập trình Web CNTT1188 - Khoa CNTT NEU)
Bước sang học phần **Lập trình Web (CNTT1188)**, bạn tìm hiểu cách Trình duyệt (Client) giao tiếp với Máy chủ (Server) qua giao thức **HTTP/HTTPS** và kiến trúc **RESTful API**:
- Mỗi khi Client gửi một **HTTP Request**, Server sẽ xử lý và trả về một **HTTP Response** kèm **Mã trạng thái 3 chữ số (HTTP Status Code)**.

## 2. Bảng Phân loại Mã trạng thái HTTP (HTTP Status Codes)
| Dải mã số | Tên nhóm trạng thái | Ý nghĩa điển hình |
| :--- | :--- | :--- |
| **`200 <= code < 300`** (`2xx`) | **`SUCCESS`** | Thành công (VD: `200 OK`, `201 Created`, `202 Accepted`). |
| **`300 <= code < 400`** (`3xx`) | **`REDIRECT`** | Chuyển hướng URL (VD: `301 Moved Permanently`, `302 Found`). |
| **`400 <= code < 500`** (`4xx`) | **`CLIENT_ERROR`** | Lỗi từ phía trình duyệt/người dùng (VD: `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`). |
| **`500 <= code < 600`** (`5xx`) | **`SERVER_ERROR`** | Lỗi hệ thống phía máy chủ Backend (VD: `500 Internal Server Error`, `502 Bad Gateway`). |

👉 **Hãy ghi nhớ 4 dải mã số `2xx`, `3xx`, `4xx`, `5xx` trên để làm ngay Bài tập Thực hành số 5 củng cố kiến thức HTTP!**
""",
    )

    l6 = Lesson(
        course_id=course_ltw.id,
        title="[CNTT1188 - Chương 3, 4 & 5] Backend MVC, Kết nối CSDL (ORM) & Nghiệp vụ Thương mại Điện tử",
        slug="cntt1188-chuong-3-4-5-backend-mvc-ecommerce",
        order_index=2,
        xp_reward=35,
        content_markdown="""
## 1. Mục tiêu Bài giảng (Đề cương Lập trình Web CNTT1188 - Đồ án Thương mại Điện tử)
Phần trọng tâm cuối cùng của học phần **CNTT1188** tại NEU là xây dựng tầng xử lý nghiệp vụ phía Server (**Controller / Service Layer** trong mô hình MVC) cho một **Website Thương mại Điện tử**:
- Không bao giờ tin tưởng hoàn toàn vào số tiền tính sẵn dưới trình duyệt (vì người dùng có thể dùng F12 sửa code JS).
- Mọi công thức tính thành tiền, chiết khấu VIP và thuế giá trị gia tăng (VAT) đều phải được tính toán lại trên **Backend Server** trước khi lưu vào Cơ sở dữ liệu.

## 2. Công thức Nghiệp vụ Tính Hóa đơn Đặt hàng trên Backend
Cho đơn giá sản phẩm `unit_price` và số lượng đặt mua `quantity`:
1. **Thành tiền gốc (`subtotal`):** `subtotal = unit_price * quantity`
2. **Chiết khấu mua sỉ (`discount`):** Nếu mua từ 10 sản phẩm trở lên (`quantity >= 10`), giảm `10%` trên thành tiền gốc (`subtotal * 90 // 100`). Ngược lại không giảm (`after_discount = subtotal`).
3. **Cộng thuế VAT 10% (`final_amount`):** `final_amount = after_discount * 110 // 100`.

👉 **Hãy bấm chuyển sang Bài tập Thực hành số 6 bên dưới để hoàn thành toàn bộ Cây Kỹ năng Lập trình Web NEU!**
""",
    )

    db.session.add_all([l1, l2, l3, l4, l5, l6])
    db.session.flush()

    # 7. BÀI TẬP THỰC HÀNH CỦNG CỐ KIẾN THỨC (CHƯA ĐIỀN ĐÁP ÁN - ĐỂ SINH VIÊN ĐỌC BÀI GIẢNG XONG TỰ LÀM)
    ex1 = Exercise(
        skill_id=s_html.id,
        lesson_id=l1.id,
        title="Thực hành Bài 1 [CNTT1165]: Bộ sinh Thẻ Tiêu đề HTML5 Tự động",
        slug="bo-sinh-the-tieu-de-html5",
        difficulty="easy",
        scaffold_level="Mức 1 (Cho người mới): Đã có sẵn 80% khung code, sinh viên điền 1 dòng TODO",
        xp_reward=50,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1165", "html5", "tier-1"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng Chương 2): Phần tử tiêu đề bậc 1 có thẻ mở <h1> và thẻ đóng </h1>.",
            "Gợi ý 2: Dùng f-string trong Python: return f'<h1>{title_text}</h1>'",
            "Gợi ý 3: Xóa dòng return '' mặc định và thay bằng câu lệnh trả về chuỗi thẻ <h1>.",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1165 - Chương 1 & 2] HTML5 Ngữ nghĩa`
Sau khi đọc xong phần lý thuyết về **Thẻ mở (Opening Tag)** và **Thẻ đóng (Closing Tag)** trong bài giảng Chương 2, bạn hãy áp dụng ngay vào bài tập thực hành này.

### Yêu cầu bài tập
Cho một chuỗi văn bản `title_text` đọc từ đầu vào chuẩn. Hãy hoàn thành vị trí `# TODO` trong khung code bên phải để hàm `render_h1_tag(title_text)` trả về phần tử HTML tiêu đề bậc 1 có dạng:
`<h1>Nội dung tiêu đề</h1>`

> 💡 **Lưu ý:** Nếu quên cú pháp, bạn có thể nhấn nút **"📖 Xem Lý thuyết Bài giảng"** ngay phía trên đề bài này để đọc lại ví dụ mẫu!
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def render_h1_tag(title_text: str) -> str:\n"
                "    # BÀI TẬP CỦNG CỐ BÀI GIẢNG CHƯƠNG 2 (MỨC 1 - 80% KHUNG CODE):\n"
                "    # TODO: Dựa vào kiến thức trong bài giảng, hãy bọc title_text vào cặp thẻ <h1> và </h1>\n"
                "    return \"\"\n\n"
                "if __name__ == '__main__':\n"
                "    text = sys.stdin.read().strip()\n"
                "    print(render_h1_tag(text))\n"
            ),
            "cpp": (
                "#include <iostream>\n#include <string>\nusing namespace std;\n\n"
                "int main() {\n"
                "    string text;\n"
                "    getline(cin, text);\n"
                "    // TODO: Hãy in ra chuỗi có dạng <h1>text</h1>\n"
                "    cout << \"\" << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    ex2 = Exercise(
        skill_id=s_css.id,
        lesson_id=l2.id,
        title="Thực hành Bài 2 [CNTT1165]: Tính Độ rộng Cột Responsive Flexbox",
        slug="tinh-do-rong-cot-css-flexbox",
        difficulty="easy",
        scaffold_level="Mức 2 (60% khung code): Áp dụng công thức Flexbox trong Bài giảng Chương 3 & 4",
        xp_reward=60,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1165", "css3", "flexbox", "tier-2"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng Chương 3 & 4): Tổng khoảng trống giữa các cột là total_gap = (cols - 1) * gap.",
            "Gợi ý 2: Độ rộng mỗi cột là col_width = (container_width - total_gap) // cols.",
            "Gợi ý 3: Trả về kết quả kèm hậu tố đơn vị: return f'{col_width}px'.",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1165 - Chương 3 & 4] CSS3 & Bố cục Flexbox`
Áp dụng công thức chia cột lưới Flexbox bạn vừa đọc trong bài giảng Chương 3 & 4.

### Yêu cầu bài tập
Cho 3 số nguyên `container_width`, `cols`, và `gap` trên một dòng.
Hãy hoàn thành phần `# TODO` trong hàm `calculate_flex_column_width` theo công thức:
$$\text{Column Width} = \left\lfloor \frac{\text{container\_width} - (\text{cols} - 1) \times \text{gap}}{\text{cols}} \right\rfloor$$
In ra chuỗi kết quả kèm đơn vị `px` (ví dụ: `380px`).
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def calculate_flex_column_width(container_width: int, cols: int, gap: int) -> str:\n"
                "    # BÀI TẬP CỦNG CỐ BÀI GIẢNG CHƯƠNG 3 & 4 (MỨC 2 - 60% KHUNG CODE):\n"
                "    # TODO Bước 1: Tính tổng khoảng cách (total_gap) giữa các cột\n"
                "    total_gap = 0\n"
                "    \n"
                "    # TODO Bước 2: Tính độ rộng mỗi cột (col_width) và trả về chuỗi kèm đơn vị 'px'\n"
                "    col_width = 0\n"
                "    return f\"{col_width}px\"\n\n"
                "if __name__ == '__main__':\n"
                "    data = sys.stdin.read().split()\n"
                "    if len(data) >= 3:\n"
                "        w, c, g = int(data[0]), int(data[1]), int(data[2])\n"
                "        print(calculate_flex_column_width(w, c, g))\n"
            ),
            "cpp": (
                "#include <iostream>\nusing namespace std;\n\n"
                "int main() {\n"
                "    int w, cols, gap;\n"
                "    if (cin >> w >> cols >> gap) {\n"
                "        // TODO: Tính độ rộng mỗi cột và in kèm đơn vị px\n"
                "        int col_w = 0;\n"
                "        cout << col_w << \"px\" << endl;\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    ex3 = Exercise(
        skill_id=s_js.id,
        lesson_id=l3.id,
        title="Thực hành Bài 3 [CNTT1165]: Tính Tổng Giỏ Hàng Thương Mại Điện Tử",
        slug="tinh-tong-gio-hang-web",
        difficulty="medium",
        scaffold_level="Mức 3 (40% khung code): Củng cố cấu trúc điều khiển & mảng (Chương 5)",
        xp_reward=60,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1165", "javascript", "tier-2"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng Chương 5): Tính tổng danh sách giá bằng hàm sum(prices).",
            "Gợi ý 2: Nếu tổng >= 500 thì trừ đi 50 (khuyến mãi đơn hàng lớn).",
            "Gợi ý 3: Trả về số nguyên tổng tiền cuối cùng.",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1165 - Chương 5] Xử lý Logic Client-side`
Áp dụng kỹ thuật tính tổng mảng và cấu trúc rẽ nhánh `if/else` từ bài giảng Chương 5.

### Yêu cầu bài tập
- Dòng 1: Số lượng sản phẩm $N$ trong giỏ hàng.
- Dòng 2: $N$ số nguyên biểu thị giá của từng sản phẩm (nghìn đồng).
- **Quy tắc khuyến mãi:** Nếu tổng giá trị giỏ hàng $\ge 500$, khách hàng được **giảm ngay 50**. Ngược lại giữ nguyên.
Hãy hoàn thành phần `# TODO` trong hàm `checkout_total(prices)` để trả về số tiền khách phải thanh toán.
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def checkout_total(prices: list[int]) -> int:\n"
                "    # BÀI TẬP CỦNG CỐ BÀI GIẢNG CHƯƠNG 5 (MỨC 3 - 40% KHUNG CODE):\n"
                "    # TODO: Tính tổng danh sách prices, nếu tổng >= 500 thì trừ đi 50\n"
                "    return 0\n\n"
                "if __name__ == '__main__':\n"
                "    tokens = sys.stdin.read().split()\n"
                "    if tokens:\n"
                "        n = int(tokens[0])\n"
                "        items = [int(x) for x in tokens[1:1+n]]\n"
                "        print(checkout_total(items))\n"
            ),
            "cpp": (
                "#include <iostream>\nusing namespace std;\n\n"
                "int main() {\n"
                "    int n; if (!(cin >> n)) return 0;\n"
                "    // TODO: Đọc n mức giá, tính tổng và giảm 50 nếu tổng >= 500\n"
                "    cout << 0 << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    ex4 = Exercise(
        skill_id=s_dom.id,
        lesson_id=l4.id,
        title="Thực hành Bài 4 [CNTT1165]: Kiểm tra Hợp lệ Email Đăng ký (Form Validation)",
        slug="kiem-tra-hop-le-email-form",
        difficulty="medium",
        scaffold_level="Mức 4 (30% khung code): Củng cố kiểm tra Biểu mẫu Web (Chương 6)",
        xp_reward=80,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1165", "dom", "form-validation", "tier-3"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng Chương 6): Kiểm tra ' ' not in email và email.count('@') == 1.",
            "Gợi ý 2: Tách local, domain = email.split('@'). Kiểm tra cả local và domain đều khác rỗng.",
            "Gợi ý 3: Kiểm tra '.' in domain và not domain.startswith('.') và not domain.endswith('.').",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1165 - Chương 6] DOM & Kiểm tra Biểu mẫu (Form Validation)`
Áp dụng 3 quy tắc kiểm tra dữ liệu Email trước khi gửi biểu mẫu lên Server đã học trong Bài giảng Chương 6.

### Yêu cầu bài tập
Cho một chuỗi `email` trên một dòng. Một email được coi là hợp lệ (`VALID`) nếu thỏa mãn đồng thời:
1. Không chứa khoảng trắng và có đúng **1 ký tự `@`**.
2. Phần tên trước `@` (`local`) không được rỗng.
3. Phần tên miền sau `@` (`domain`) có chứa ít nhất một dấu chấm `.` và dấu chấm không nằm ở ngay đầu hay cuối `domain`.

Hãy in ra `VALID` nếu hợp lệ, ngược lại in ra `INVALID`.
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def validate_email(email: str) -> str:\n"
                "    # BÀI TẬP CỦNG CỐ BÀI GIẢNG CHƯƠNG 6 (MỨC 4 - 30% KHUNG CODE):\n"
                "    # TODO: Kiểm tra các điều kiện hợp lệ của email và trả về 'VALID' hoặc 'INVALID'\n"
                "    return \"INVALID\"\n\n"
                "if __name__ == '__main__':\n"
                "    raw_email = sys.stdin.read().strip()\n"
                "    print(validate_email(raw_email))\n"
            ),
            "cpp": (
                "#include <iostream>\n#include <string>\nusing namespace std;\n\n"
                "int main() {\n"
                "    string email;\n"
                "    if (cin >> email) {\n"
                "        // TODO: Kiểm tra email và in ra VALID hoặc INVALID\n"
                "        cout << \"INVALID\" << endl;\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    ex5 = Exercise(
        skill_id=s_async.id,
        lesson_id=l5.id,
        title="Thực hành Bài 5 [CNTT1188]: Phân loại Mã Trạng thái HTTP Response (REST API)",
        slug="phan-loai-ma-trang-thai-http-api",
        difficulty="medium",
        scaffold_level="Mức 4 (30% khung code): Củng cố Giao thức HTTP & Web API (CNTT1188 - Chương 1 & 2)",
        xp_reward=80,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1188", "http", "rest-api", "tier-3"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng CNTT1188 Chương 1 & 2): Nếu 200 <= status_code < 300 trả về 'SUCCESS'.",
            "Gợi ý 2: Nếu 300 <= status_code < 400 trả về 'REDIRECT'; nếu 400 <= status_code < 500 trả về 'CLIENT_ERROR'.",
            "Gợi ý 3: Nếu 500 <= status_code < 600 trả về 'SERVER_ERROR', các trường hợp khác trả về 'UNKNOWN'.",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1188 - Chương 1 & 2] Giao thức HTTP & RESTful Web API`
Áp dụng bảng phân loại dải mã trạng thái HTTP Response bạn vừa đọc trong bài giảng.

### Yêu cầu bài tập
Cho một số nguyên `status_code` biểu thị mã trạng thái HTTP trả về từ Web Server. Hãy phân loại mã trạng thái đó thành một trong các nhãn sau:
- `200 <= code < 300`: in ra `SUCCESS`
- `300 <= code < 400`: in ra `REDIRECT`
- `400 <= code < 500`: in ra `CLIENT_ERROR`
- `500 <= code < 600`: in ra `SERVER_ERROR`
- Ngoài các khoảng trên: in ra `UNKNOWN`
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def classify_http_status(status_code: int) -> str:\n"
                "    # BÀI TẬP CỦNG CỐ CNTT1188 CHƯƠNG 1 & 2:\n"
                "    # TODO: Phân loại mã trạng thái HTTP theo 4 dải 2xx, 3xx, 4xx, 5xx\n"
                "    return \"UNKNOWN\"\n\n"
                "if __name__ == '__main__':\n"
                "    line = sys.stdin.read().strip()\n"
                "    if line:\n"
                "        print(classify_http_status(int(line)))\n"
            ),
            "cpp": (
                "#include <iostream>\nusing namespace std;\n\n"
                "int main() {\n"
                "    int code;\n"
                "    if (cin >> code) {\n"
                "        // TODO: In ra nhãn phân loại mã trạng thái HTTP\n"
                "        cout << \"UNKNOWN\" << endl;\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    ex6 = Exercise(
        skill_id=s_flask.id,
        lesson_id=l6.id,
        title="Thực hành Bài 6 [CNTT1188]: Xử lý Nghiệp vụ Tính Thuế VAT & Chiết khấu Đơn hàng Backend",
        slug="tinh-thue-vat-va-chiet-khau-backend",
        difficulty="hard",
        scaffold_level="Mức 5 (25% khung code): Củng cố Nghiệp vụ Thương mại Điện tử Backend (CNTT1188)",
        xp_reward=100,
        time_limit_ms=1000,
        memory_limit_kb=65536,
        tags=["cntt1188", "backend", "mvc", "ecommerce", "tier-4"],
        hints=[
            "Gợi ý 1 (Từ Bài giảng CNTT1188 Chương 4): Tính thành tiền gốc subtotal = unit_price * quantity.",
            "Gợi ý 2: Nếu quantity >= 10 thì after_discount = (subtotal * 90) // 100, ngược lại after_discount = subtotal.",
            "Gợi ý 3: Cộng thêm 10% thuế VAT: final_amount = (after_discount * 110) // 100.",
        ],
        problem_statement=r"""
### Củng cố kiến thức sau Bài giảng: `[CNTT1188 - Chương 3, 4 & 5] Nghiệp vụ Thương mại Điện tử Backend`
Áp dụng quy trình tính hóa đơn đặt hàng phía Server trong bài giảng đồ án Thương mại Điện tử.

### Yêu cầu bài tập
Cho hai số nguyên `unit_price` (đơn giá) và `quantity` (số lượng đặt mua) trên cùng một dòng.
Hãy tính tổng số tiền cuối cùng (`final_amount`) theo 3 bước:
1. `subtotal = unit_price * quantity`
2. Nếu `quantity >= 10`, được giảm giá sỉ 10%: `after_discount = (subtotal * 90) // 100`. Ngược lại `after_discount = subtotal`.
3. Cộng thuế VAT 10%: `final_amount = (after_discount * 110) // 100`.
In ra số nguyên `final_amount`.
""",
        starter_code={
            "python": (
                "import sys\n\n"
                "def calculate_order_invoice(unit_price: int, quantity: int) -> int:\n"
                "    # BÀI TẬP CỦNG CỐ CNTT1188 CHƯƠNG 3, 4 & 5 (MỨC 5 - TỰ THIẾT KẾ HÀM BACKEND):\n"
                "    # TODO: Thực hiện 3 bước tính subtotal, chiết khấu mua sỉ (>= 10 sp) và thuế VAT 10%\n"
                "    return 0\n\n"
                "if __name__ == '__main__':\n"
                "    parts = sys.stdin.read().split()\n"
                "    if len(parts) >= 2:\n"
                "        p, q = int(parts[0]), int(parts[1])\n"
                "        print(calculate_order_invoice(p, q))\n"
            ),
            "cpp": (
                "#include <iostream>\nusing namespace std;\n\n"
                "int main() {\n"
                "    long long p, q;\n"
                "    if (cin >> p >> q) {\n"
                "        // TODO: Tính tổng tiền sau chiết khấu và thuế VAT 10%\n"
                "        cout << 0 << endl;\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
        },
    )

    db.session.add_all([ex1, ex2, ex3, ex4, ex5, ex6])
    db.session.flush()

    test_cases = [
        # Bài 1: HTML5 H1 Tag
        TestCase(exercise_id=ex1.id, input_data="Xin chao Lap trinh Web\n", expected_output="<h1>Xin chao Lap trinh Web</h1>\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex1.id, input_data="Khoa CNTT Dai hoc Kinh te Quoc dan\n", expected_output="<h1>Khoa CNTT Dai hoc Kinh te Quoc dan</h1>\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex1.id, input_data="CNTT1165 Thiet ke Web\n", expected_output="<h1>CNTT1165 Thiet ke Web</h1>\n", is_sample=False, order_index=3),
        # Bài 2: CSS Flexbox Width
        TestCase(exercise_id=ex2.id, input_data="1200 3 30\n", expected_output="380px\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex2.id, input_data="1000 4 20\n", expected_output="235px\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex2.id, input_data="960 2 40\n", expected_output="460px\n", is_sample=False, order_index=3),
        # Bài 3: Shopping Cart
        TestCase(exercise_id=ex3.id, input_data="3\n200 150 250\n", expected_output="550\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex3.id, input_data="2\n120 180\n", expected_output="300\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex3.id, input_data="4\n100 100 150 150\n", expected_output="450\n", is_sample=False, order_index=3),
        # Bài 4: Email Form Validation
        TestCase(exercise_id=ex4.id, input_data="sv.cntt@neu.edu.vn\n", expected_output="VALID\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex4.id, input_data=" @invalid.com\n", expected_output="INVALID\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex4.id, input_data="user@domain\n", expected_output="INVALID\n", is_sample=False, order_index=3),
        TestCase(exercise_id=ex4.id, input_data="admin@neu.edu.vn\n", expected_output="VALID\n", is_sample=False, order_index=4),
        # Bài 5: HTTP Status Code Classification
        TestCase(exercise_id=ex5.id, input_data="200\n", expected_output="SUCCESS\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex5.id, input_data="404\n", expected_output="CLIENT_ERROR\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex5.id, input_data="500\n", expected_output="SERVER_ERROR\n", is_sample=False, order_index=3),
        TestCase(exercise_id=ex5.id, input_data="302\n", expected_output="REDIRECT\n", is_sample=False, order_index=4),
        # Bài 6: Backend Order Invoice (Subtotal -> 10% Wholesale Discount -> 10% VAT)
        TestCase(exercise_id=ex6.id, input_data="100 5\n", expected_output="550\n", is_sample=True, order_index=1),
        TestCase(exercise_id=ex6.id, input_data="100 10\n", expected_output="990\n", is_sample=True, order_index=2),
        TestCase(exercise_id=ex6.id, input_data="200 20\n", expected_output="3960\n", is_sample=False, order_index=3),
    ]
    db.session.add_all(test_cases)

    # 8. Lộ trình Học tập Chuẩn Đề cương Khoa CNTT - Đại học Kinh tế Quốc dân (NEU)
    roadmap = Roadmap(
        title="Lộ trình Chuẩn Đề cương Học phần: Thiết kế Web (CNTT1165) & Lập trình Web (CNTT1188) - NEU",
        slug="lo-trinh-cntt1165-cntt1188-neu",
        target_role="Khoa Công nghệ Thông tin • Trường Đại học Kinh tế Quốc dân (NEU)",
        description="Phương pháp học tập chủ động: Bước 1 Đọc Bài giảng Lý thuyết theo từng Chương -> Bước 2 Thực hành viết code củng cố ngay trên Web.",
    )
    db.session.add(roadmap)
    db.session.flush()

    rm_nodes = [
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_html.id, step_order=1, branch_name="CNTT1165 • Chương 1 & 2"),
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_css.id, step_order=2, branch_name="CNTT1165 • Chương 3 & 4"),
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_js.id, step_order=3, branch_name="CNTT1165 • Chương 5"),
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_dom.id, step_order=4, branch_name="CNTT1165 • Chương 6"),
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_async.id, step_order=5, branch_name="CNTT1188 • Chương 1 & 2"),
        RoadmapNode(roadmap_id=roadmap.id, skill_id=s_flask.id, step_order=6, branch_name="CNTT1188 • Chương 3, 4 & 5"),
    ]
    db.session.add_all(rm_nodes)
    db.session.commit()

    sync_user_skill_tree(learner.id)
    sync_user_skill_tree(mentor.id)
    sync_user_skill_tree(admin.id)


def seed_buddy_demo() -> None:
    """Hồ sơ bạn học mẫu cho M12. Chạy nhiều lần không lỗi."""
    if BuddyProfile.query.first() is not None:
        return
    roadmap = Roadmap.query.order_by(Roadmap.id).first()
    if roadmap is None:
        return
    peers = User.query.filter(
        User.username.in_(["minh_anh_k65", "tuan_kiet_k65", "lan_huong_k64"])
    ).all()
    for user, level in zip(peers, [1, 2, 1]):
        db.session.add(BuddyProfile(user_id=user.id, roadmap_id=roadmap.id, level=level, available=True))
    db.session.commit()


def seed_m16_data() -> None:
    """Khởi tạo huy hiệu theo mốc XP/Streak, sổ cái XP và chuỗi ngày học mẫu cho M16."""
    from datetime import date
    from app.services.m16_service import check_and_award_badges

    # 1. Bổ sung 4 Huy hiệu theo mốc XP & Streak của Module M16
    m16_badges = [
        ("first_xp", "Khởi đầu Năng lực Số", "Nhận điểm XP đầu tiên trên hệ thống.", "fa-seedling", "emerald", 1, 0),
        ("xp_100", "Sinh viên Chăm chỉ", "Tích lũy đạt mốc 100 XP.", "fa-star", "amber", 100, 0),
        ("streak_3", "Kiên trì 3 Ngày", "Duy trì chuỗi học tập 3 ngày liên tiếp.", "fa-fire", "amber", 0, 3),
        ("streak_7", "Bền bỉ 7 Ngày", "Duy trì chuỗi học tập 7 ngày liên tiếp.", "fa-trophy", "indigo", 0, 7),
    ]
    for code, name, desc, icon, color, req_xp, req_streak in m16_badges:
        if not Badge.query.filter_by(code=code).first():
            db.session.add(
                Badge(
                    code=code,
                    name=name,
                    description=desc,
                    icon=icon,
                    color=color,
                    required_xp=req_xp,
                    required_streak=req_streak,
                )
            )
    db.session.flush()

    # 2. Cập nhật chủ đề (topic) cho các câu hỏi Test đầu vào nếu chưa có
    topics_by_tier = {1: "HTML5", 2: "CSS3 & JS", 3: "DOM & Events", 4: "HTTP & Backend"}
    for q in PlacementQuestion.query.all():
        if not q.topic or q.topic == "HTML":
            q.topic = topics_by_tier.get(q.difficulty_tier, "Web")

    # 3. Khởi tạo UserStreak và XpEvent mẫu cho các tài khoản học viên
    today = date.today()
    for u in User.query.all():
        if not db.session.get(UserStreak, u.id):
            db.session.add(
                UserStreak(
                    user_id=u.id,
                    current_streak=u.current_streak,
                    longest_streak=max(u.current_streak, 5),
                    last_study_date=today,
                )
            )
        if u.total_xp > 0 and not XpEvent.query.filter_by(user_id=u.id).first():
            db.session.add(
                XpEvent(
                    user_id=u.id,
                    event_key="init:welcome_xp",
                    reason="Điểm kinh nghiệm khởi tạo lộ trình NEU WebPath",
                    xp=u.total_xp,
                )
            )
    db.session.commit()

    for u in User.query.all():
        check_and_award_badges(u.id)
