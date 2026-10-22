"""
Application Configuration Module
Reads settings from .env file with fallbacks and validation.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

class Config:
    BASE_DIR = BASE_DIR
    FLASK_ENV = os.getenv('FLASK_ENV', 'development').lower()
    DEBUG = FLASK_ENV == 'development'
    
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        if FLASK_ENV == 'production':
            raise RuntimeError("CRITICAL ERROR: SECRET_KEY must be set in production environment!")
        SECRET_KEY = 'dev_fallback_secret_key_antigravity_2026'

    # Database
    db_env = os.getenv('DATABASE_PATH', 'backend/database.db')
    DATABASE_PATH = str((BASE_DIR / db_env).resolve()) if not os.path.isabs(db_env) else db_env

    # Admin credentials for initial setup
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin@123')

    # File uploads - default 200 MB for video workloads
    MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', 200))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

    # YOLO Weights
    yolo_env = os.getenv('YOLO_WEIGHTS', 'backend/models/yolov8s.pt')
    YOLO_WEIGHTS = str((BASE_DIR / yolo_env).resolve()) if not os.path.isabs(yolo_env) else yolo_env

    # CORS Allowed Origins
    raw_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000')
    ALLOWED_ORIGINS = [orig.strip() for orig in raw_origins.split(',') if orig.strip()]

    # ML Model directory
    ML_MODELS_DIR = str(BASE_DIR / 'backend' / 'ml' / 'models')

    # Job / Temporary directory (lives outside watched source tree to prevent reloader restarts)
    import tempfile
    default_jobs = str(Path(tempfile.gettempdir()) / 'roadsafety_jobs')
    JOBS_DIR = os.getenv('JOBS_DIR', default_jobs)
