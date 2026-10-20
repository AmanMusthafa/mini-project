"""
Authentication & Authorization Service
Provides password hashing, session validation, role enforcement, and security decorators.
"""
from functools import wraps
from flask import session, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

def login_required(f):
    """Ensure user has an active authenticated session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'username' not in session:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in to access this resource."
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    """Enforce role-based access control (e.g. admin only)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({
                    "success": False,
                    "error": "Authentication required."
                }), 401
            user_role = session.get('role', 'viewer')
            if user_role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Permission denied. Required role in: {allowed_roles}"
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def verify_credentials(db_conn, username, password):
    """Authenticate username and password against hashed database records."""
    if not username or not password:
        return None
    c = db_conn.cursor()
    c.execute(
        "SELECT id, username, password_hash, name, email, department, phone, role FROM users WHERE username = ?",
        (username.strip(),)
    )
    user_row = c.fetchone()
    if not user_row:
        return None
    
    # Check hashed password
    if check_password_hash(user_row['password_hash'], password):
        return {
            "id": user_row['id'],
            "username": user_row['username'],
            "name": user_row['name'],
            "email": user_row['email'],
            "department": user_row['department'],
            "phone": user_row['phone'],
            "role": user_row['role']
        }
    return None
