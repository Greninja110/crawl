"""
Authentication and authorization service for user management
"""
from flask_login import UserMixin
from models import get_db
from models.user import (
    get_user_by_email, authenticate_user, create_user, 
    update_user, get_user_by_id, verify_password,
    get_users, count_users, get_user_by_username
)
from werkzeug.security import check_password_hash

class User(UserMixin):
    """User class for Flask-Login compatibility"""
    
    def __init__(self, user_doc):
        self.id = str(user_doc['_id'])
        self.username = user_doc['username']
        self.email = user_doc['email']
        self.name = user_doc.get('name', self.username)
        self.role = user_doc.get('role', 'user')
        self.active = user_doc.get('active', True)
        self.last_login = user_doc.get('last_login')
        self.created_at = user_doc.get('created_at')
        self.is_admin = self.role == 'admin'
    
    def get_id(self):
        """Return the user ID as a string"""
        return self.id
    
    def is_active(self):
        """Return user active status"""
        return self.active
    
    @property
    def is_authenticated(self):
        """Return authentication status"""
        return True
    
    @property
    def is_anonymous(self):
        """Return anonymous status"""
        return False
        
    def has_permission(self, permission):
        """Check if user has a specific permission"""
        if self.is_admin:
            return True
            
        # Define permission checks based on roles
        permission_map = {
            'view_colleges': ['admin', 'user'],
            'add_college': ['admin'],
            'edit_college': ['admin'],
            'delete_college': ['admin'],
            'start_crawl': ['admin', 'user'],
            'view_data': ['admin', 'user'],
            'manage_users': ['admin'],
            'view_analytics': ['admin', 'user'],
            'configure_ai': ['admin']
        }
        
        return self.role in permission_map.get(permission, ['admin'])

def init_auth(login_manager):
    """Initialize authentication with Flask-Login"""
    
    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        user_doc = get_user_by_id(db, user_id)
        if user_doc:
            return User(user_doc)
        return None

def login(email_or_username, password):
    """
    Authenticate a user with email/username and password
    
    Args:
        email_or_username: Email or username
        password: Password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    db = get_db()
    user_doc = authenticate_user(db, email_or_username, password)
    
    if user_doc:
        return User(user_doc)
    return None

def register_user(username, email, password, name=None, role='user'):
    """
    Register a new user
    
    Args:
        username: Unique username
        email: User's email address
        password: Password
        name: User's full name
        role: User role (admin, user)
        
    Returns:
        User object if registration successful, None if username/email already exists
    """
    db = get_db()
    
    # Check if username or email already exists
    if get_user_by_email(db, email) or get_user_by_username(db, username):
        return None
    
    # Create new user
    user_id = create_user(db, username, email, password, role, name)
    
    if user_id:
        user_doc = get_user_by_id(db, user_id)
        return User(user_doc)
    return None

def get_user_profile(user_id):
    """
    Get a user's profile information
    
    Args:
        user_id: User's ID
        
    Returns:
        User object or None
    """
    db = get_db()
    user_doc = get_user_by_id(db, user_id)
    
    if user_doc:
        return User(user_doc)
    return None

def change_password(user_id, current_password, new_password):
    """
    Change a user's password
    
    Args:
        user_id: User's ID
        current_password: Current password
        new_password: New password
        
    Returns:
        True if password change successful, False otherwise
    """
    db = get_db()
    
    # Verify current password
    if not verify_password(db, user_id, current_password):
        return False
    
    # Update password
    return update_user(db, user_id, {'password': new_password})

def update_profile(user_id, update_data):
    """
    Update a user's profile information
    
    Args:
        user_id: User's ID
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    db = get_db()
    
    # Never allow role or active status to be updated through this function
    if 'role' in update_data:
        del update_data['role']
    if 'active' in update_data:
        del update_data['active']
    
    return update_user(db, user_id, update_data)

def get_all_users(page=1, per_page=20):
    """
    Get all users with pagination
    
    Args:
        page: Page number (1-based)
        per_page: Number of users per page
        
    Returns:
        Tuple of (users list, total count)
    """
    db = get_db()
    skip = (page - 1) * per_page
    
    user_docs = get_users(db, skip, per_page)
    total = count_users(db)
    
    users = [User(user_doc) for user_doc in user_docs]
    return users, total

def change_user_role(admin_user, user_id, new_role):
    """
    Change a user's role (admin operation)
    
    Args:
        admin_user: The admin User object making the change
        user_id: ID of the user to update
        new_role: New role for the user
        
    Returns:
        True if update successful, False otherwise
    """
    # Ensure the admin_user has permission to change roles
    if not admin_user.has_permission('manage_users'):
        return False
    
    db = get_db()
    return update_user(db, user_id, {'role': new_role})

def toggle_user_status(admin_user, user_id, active):
    """
    Activate or deactivate a user (admin operation)
    
    Args:
        admin_user: The admin User object making the change
        user_id: ID of the user to update
        active: Whether the user should be active
        
    Returns:
        True if update successful, False otherwise
    """
    # Ensure the admin_user has permission to change user status
    if not admin_user.has_permission('manage_users'):
        return False
    
    db = get_db()
    return update_user(db, user_id, {'active': active})

def create_admin_if_none_exists():
    """
    Create a default admin user if no users exist in the database
    
    Returns:
        True if admin created, False otherwise
    """
    db = get_db()
    
    # Check if any users exist
    if count_users(db) > 0:
        return False
    
    # Create admin user
    admin_id = create_user(
        db,
        username="admin",
        email="admin@example.com",
        password="adminpassword",
        role="admin",
        name="Administrator"
    )
    
    return admin_id is not None