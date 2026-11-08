"""Authentication logic for StyleMate AI using secure password hashing and SQLite."""
import hashlib
import re
import secrets
from database import get_user_by_email, create_user_with_credentials, update_user_password


def _safe_str(val) -> str:
    """Safely convert input values to string and handle None or unexpected types."""
    if val is None:
        return ""
    if not isinstance(val, str):
        return str(val)
    return val


def hash_password(password: str) -> str:
    """Hash a password using a secure random salt and PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verify a provided password against the stored salt$hash string."""
    try:
        salt, pwd_hash = stored_password_hash.split('$')
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            provided_password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        return secrets.compare_digest(computed_hash, pwd_hash)
    except Exception:
        return False


def validate_email(email: str) -> bool:
    """Validate email format using regular expressions safely."""
    email_str = _safe_str(email).strip()
    if not email_str:
        return False
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email_str))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets security complexity requirements."""
    pwd_str = _safe_str(password)
    if len(pwd_str) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in pwd_str):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in pwd_str):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in pwd_str):
        return False, "Password must contain at least one digit."
    return True, ""


def register_user(full_name: str, email: str, password: str, confirm_password: str) -> tuple[bool, str, int | None]:
    """Register a new user with validation: Full Name, Email, Password, Confirm Password."""
    name_str = _safe_str(full_name).strip()
    email_str = _safe_str(email).strip().lower()
    pwd_str = _safe_str(password)
    confirm_pwd_str = _safe_str(confirm_password)
    
    if not name_str:
        return False, "Please enter your full name.", None
    if not email_str:
        return False, "Please enter your email address.", None
    if not validate_email(email_str):
        return False, "Please enter a valid email address.", None
    if not pwd_str:
        return False, "Please enter your password.", None
    if not confirm_pwd_str:
        return False, "Please confirm your password.", None
        
    is_valid_pwd, pwd_msg = validate_password_strength(pwd_str)
    if not is_valid_pwd:
        return False, pwd_msg, None
        
    if pwd_str != confirm_pwd_str:
        return False, "Passwords do not match.", None
    
    try:
        existing = get_user_by_email(email_str)
        if existing:
            return False, "An account with this email already exists. Please log in.", None
        
        pwd_hash = hash_password(pwd_str)
        user_id = create_user_with_credentials(email_str, pwd_hash, name_str)
        return True, "Account created successfully!", user_id
    except Exception:
        return False, "An unexpected error occurred during registration. Please try again later.", None


def authenticate_user(email: str, password: str) -> tuple[bool, str, int | None]:
    """Authenticate an existing user by email and password with specific error messaging."""
    email_str = _safe_str(email).strip().lower()
    pwd_str = _safe_str(password)

    if not email_str:
        return False, "Please enter your email address.", None
    if not validate_email(email_str):
        return False, "Please enter a valid email address.", None
    if not pwd_str:
        return False, "Please enter your password.", None
    
    try:
        user = get_user_by_email(email_str)
        if not user or not user.get("password_hash"):
            return False, "No account exists with this email address. Please sign up first.", None
        
        if verify_password(user["password_hash"], pwd_str):
            return True, "Login successful!", int(user["id"])
        else:
            return False, "Incorrect password. Please try again.", None
    except Exception:
        return False, "An unexpected error occurred during login. Please try again later.", None


def reset_password(email: str, new_password: str, confirm_password: str) -> tuple[bool, str]:
    """Reset password securely for a verified email account."""
    email_str = _safe_str(email).strip().lower()
    new_pwd_str = _safe_str(new_password)
    confirm_pwd_str = _safe_str(confirm_password)

    if not email_str:
        return False, "Please enter your email address."
    if not validate_email(email_str):
        return False, "Please enter a valid email address."
    if not new_pwd_str:
        return False, "Please enter your new password."
    if not confirm_pwd_str:
        return False, "Please confirm your new password."
        
    is_valid_pwd, pwd_msg = validate_password_strength(new_pwd_str)
    if not is_valid_pwd:
        return False, pwd_msg
        
    if new_pwd_str != confirm_pwd_str:
        return False, "New passwords do not match."
        
    try:
        user = get_user_by_email(email_str)
        if not user:
            return False, "No account exists with this email address."
            
        pwd_hash = hash_password(new_pwd_str)
        update_user_password(email_str, pwd_hash)
        return True, "Password updated successfully! You can now log in with your new password."
    except Exception:
        return False, "An unexpected error occurred during password reset. Please try again later."