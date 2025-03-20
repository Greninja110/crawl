"""
Configuration settings for the College Data Crawler application
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_in_production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
    
    # MongoDB configuration
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/college_data_crawler')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'college_data_crawler')
    
    # Redis for Celery and SocketIO
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # File storage
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    ALLOWED_EXTENSIONS = {'json', 'csv', 'xlsx'}
    
    # AI model configuration
    AI_MODEL_PATH = os.getenv('AI_MODEL_PATH', None)
    AI_MODEL_NAME = os.getenv('AI_MODEL_NAME', 'TinyLlama/TinyLlama-1.1B-Chat-v1.0')
    AI_MODEL_DEVICE = os.getenv('AI_MODEL_DEVICE', 'cpu')
    
    # Crawler configuration
    MAX_PAGES_PER_COLLEGE = int(os.getenv('MAX_PAGES_PER_COLLEGE', '30'))
    MAX_CRAWL_DEPTH = int(os.getenv('MAX_CRAWL_DEPTH', '3'))
    CRAWL_DELAY = float(os.getenv('CRAWL_DELAY', '1.0'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    
    # Worker configuration
    CRAWLER_WORKERS = int(os.getenv('CRAWLER_WORKERS', '2'))
    AI_PROCESSING_WORKERS = int(os.getenv('AI_PROCESSING_WORKERS', '1'))

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    MONGO_URI = os.getenv('TEST_MONGO_URI', 'mongodb://localhost:27017/college_data_crawler_test')
    DATABASE_NAME = 'college_data_crawler_test'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, ensure SECRET_KEY is set in environment
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # SSL configuration for production
    SSL_REDIRECT = True if os.getenv('SSL_REDIRECT', 'False') == 'True' else False

# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Get config by name
def get_config(config_name=None):
    if not config_name:
        config_name = os.getenv('FLASK_CONFIG', 'default')
    return config_dict.get(config_name, config_dict['default'])