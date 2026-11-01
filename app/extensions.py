from concurrent.futures import ThreadPoolExecutor
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"
socketio = SocketIO()

# Background Thread Pool nhẹ nhàng thay thế cho Celery/Redis trong bản MVP
judge_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AutoJudgeWorker")
