"""
Models package initialization
"""
from pymongo import MongoClient
from config import get_config
import threading
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Thread-local storage for MongoDB connections
_thread_local = threading.local()

def init_db(app=None):
    """Initialize database connection"""
    config = get_config()
    if app:
        mongo_uri = app.config.get('MONGO_URI', config.MONGO_URI)
        db_name = app.config.get('DATABASE_NAME', config.DATABASE_NAME)
    else:
        mongo_uri = config.MONGO_URI
        db_name = config.DATABASE_NAME
    
    # Create MongoDB client
    try:
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection by pinging the server
        mongo_client.admin.command('ping')
        
        db = mongo_client[db_name]
        
        # Store connection in thread-local storage
        _thread_local.mongo_client = mongo_client
        _thread_local.db = db
        
        # Initialize collection indexes
        from .college import create_indexes as create_college_indexes
        from .user import create_indexes as create_user_indexes
        from .raw_content import create_indexes as create_raw_content_indexes
        from .admission_data import create_indexes as create_admission_indexes
        from .placement_data import create_indexes as create_placement_indexes
        from .internship_data import create_indexes as create_internship_indexes
        from .crawl_job import create_indexes as create_crawl_job_indexes
        from .ai_processing_job import create_indexes as create_ai_job_indexes
        
        # Create all indexes
        create_college_indexes(db)
        create_user_indexes(db)
        create_raw_content_indexes(db)
        create_admission_indexes(db)
        create_placement_indexes(db)
        create_internship_indexes(db)
        create_crawl_job_indexes(db)
        create_ai_job_indexes(db)
        
        return db
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB connection: {str(e)}")
        raise

def get_db():
    """Get database connection (thread-safe)"""
    # If this thread doesn't have a connection or the connection was closed
    if not hasattr(_thread_local, 'db') or not hasattr(_thread_local, 'mongo_client'):
        return init_db()
        
    # Try to use existing connection
    try:
        # Simple ping to check connection is still alive
        _thread_local.mongo_client.admin.command('ping')
        return _thread_local.db
    except Exception:
        # If any error, create a new connection
        logger.info("MongoDB connection lost, creating a new one")
        return init_db()

# Close MongoDB connection when application stops
def close_db_connection():
    """Close the thread's MongoDB connection if it exists"""
    if hasattr(_thread_local, 'mongo_client') and _thread_local.mongo_client is not None:
        _thread_local.mongo_client.close()
        _thread_local.mongo_client = None
        _thread_local.db = None