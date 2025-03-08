"""
User model for authentication and authorization
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, TEXT
import bcrypt

def create_indexes(db):
    """Create indexes for the users collection"""
    db.users.create_index([('email', ASCENDING)], unique=True)
    db.users.create_index([('username', ASCENDING)], unique=True)

def get_users_collection(db):
    """Get the users collection"""
    return db.users

def create_user(db, username, email, password, role='user', name=None, active=True):
    """
    Create a new user
    
    Args:
        db: Database connection
        username: Unique username
        email: User's email address
        password: Plain-text password (will be hashed)
        role: User role (admin, user)
        name: User's full name
        active: Whether the user is active
        
    Returns:
        Inserted user document ID or None if email/username already exists
    """
    collection = get_users_collection(db)
    
    # Check if user with this email or username already exists
    if collection.find_one({'$or': [{'email': email}, {'username': username}]}):
        return None
    
    # Hash the password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    user_doc = {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "name": name or username,
        "role": role,
        "active": active,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login": None
    }
    
    result = collection.insert_one(user_doc)
    return result.inserted_id

def get_user_by_id(db, user_id):
    """
    Get a user by ID
    
    Args:
        db: Database connection
        user_id: User's ID
        
    Returns:
        User document or None
    """
    collection = get_users_collection(db)
    
    # Ensure user_id is ObjectId
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    
    return collection.find_one({'_id': user_id})

def get_user_by_email(db, email):
    """
    Get a user by email
    
    Args:
        db: Database connection
        email: User's email
        
    Returns:
        User document or None
    """
    collection = get_users_collection(db)
    return collection.find_one({'email': email})

def get_user_by_username(db, username):
    """
    Get a user by username
    
    Args:
        db: Database connection
        username: User's username
        
    Returns:
        User document or None
    """
    collection = get_users_collection(db)
    return collection.find_one({'username': username})

def update_user(db, user_id, update_data):
    """
    Update a user's information
    
    Args:
        db: Database connection
        user_id: User's ID
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_users_collection(db)
    
    # Ensure user_id is ObjectId
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    
    # If password is in update data, hash it
    if 'password' in update_data:
        password = update_data.pop('password')
        update_data['password_hash'] = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    # Set updated timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    result = collection.update_one(
        {'_id': user_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def verify_password(db, user_id, password):
    """
    Verify a user's password
    
    Args:
        db: Database connection
        user_id: User's ID
        password: Plain-text password to verify
        
    Returns:
        True if password is correct, False otherwise
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    stored_hash = user.get('password_hash')
    
    # Check if stored hash is bytes or string and convert if needed
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')
    
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash)

def authenticate_user(db, username_or_email, password):
    """
    Authenticate a user with username/email and password
    
    Args:
        db: Database connection
        username_or_email: Username or email
        password: Plain-text password
        
    Returns:
        User document if authentication successful, None otherwise
    """
    collection = get_users_collection(db)
    
    # Find user by username or email
    user = collection.find_one({
        '$or': [
            {'username': username_or_email},
            {'email': username_or_email}
        ]
    })
    
    if not user:
        return None
    
    # Verify password
    stored_hash = user.get('password_hash')
    
    # Check if stored hash is bytes or string and convert if needed
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')
    
    if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
        # Update last login time
        collection.update_one(
            {'_id': user['_id']},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        return user
    
    return None

def deactivate_user(db, user_id):
    """
    Deactivate a user account
    
    Args:
        db: Database connection
        user_id: User's ID
        
    Returns:
        True if deactivation successful, False otherwise
    """
    return update_user(db, user_id, {'active': False})

def activate_user(db, user_id):
    """
    Activate a user account
    
    Args:
        db: Database connection
        user_id: User's ID
        
    Returns:
        True if activation successful, False otherwise
    """
    return update_user(db, user_id, {'active': True})

def change_user_role(db, user_id, new_role):
    """
    Change a user's role
    
    Args:
        db: Database connection
        user_id: User's ID
        new_role: New role (admin, user)
        
    Returns:
        True if role change successful, False otherwise
    """
    return update_user(db, user_id, {'role': new_role})

def get_users(db, skip=0, limit=20):
    """
    Get a list of users with pagination
    
    Args:
        db: Database connection
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of user documents (without password hash)
    """
    collection = get_users_collection(db)
    
    # Projection to exclude password hash
    projection = {'password_hash': 0}
    
    cursor = collection.find({}, projection).skip(skip).limit(limit)
    return list(cursor)

def count_users(db):
    """
    Count total users
    
    Args:
        db: Database connection
        
    Returns:
        Count of users
    """
    collection = get_users_collection(db)
    return collection.count_documents({})

def delete_user(db, user_id):
    """
    Delete a user
    
    Args:
        db: Database connection
        user_id: User's ID
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_users_collection(db)
    
    # Ensure user_id is ObjectId
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    
    result = collection.delete_one({'_id': user_id})
    return result.deleted_count > 0

# Helper functions for Flask-Login compatibility
def get_user_for_flask_login(db, user_id):
    """
    Get user in a format compatible with Flask-Login
    
    Args:
        db: Database connection
        user_id: User's ID as string
        
    Returns:
        User document with _id as string, or None
    """
    try:
        user = get_user_by_id(db, user_id)
        if user:
            # Convert ObjectId to string for Flask-Login
            user['_id'] = str(user['_id'])
            return user
        return None
    except Exception:
        return None