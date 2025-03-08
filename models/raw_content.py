"""
Raw content model for storing extracted HTML content from college websites
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, TEXT, DESCENDING

def create_indexes(db):
    """Create indexes for the raw_content collection"""
    db.raw_content.create_index([('college_id', ASCENDING)])
    db.raw_content.create_index([('content_type', ASCENDING)])
    db.raw_content.create_index([('url', ASCENDING)])
    db.raw_content.create_index([('processed', ASCENDING)])
    db.raw_content.create_index([('extraction_date', DESCENDING)])

def get_raw_content_collection(db):
    """Get the raw_content collection"""
    return db.raw_content

def store_raw_content(db, college_id, url, content_type, content, content_format='html'):
    """
    Store raw content extracted from a college website
    
    Args:
        db: Database connection
        college_id: ID of the college
        url: URL where content was extracted from
        content_type: Type of content (admission/placement/internship)
        content: The extracted content
        content_format: Format of the content (html/text/pdf)
        
    Returns:
        Inserted document ID
    """
    collection = get_raw_content_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    content_doc = {
        "college_id": college_id,
        "url": url,
        "content_type": content_type,
        "content": content,
        "content_format": content_format,
        "extraction_date": datetime.utcnow(),
        "processed": False,
        "processing_attempts": 0,
        "last_processing_attempt": None,
        "processing_error": None
    }
    
    result = collection.insert_one(content_doc)
    return result.inserted_id

def update_raw_content_processing_status(db, content_id, processed=True, error=None):
    """
    Update the processing status of raw content
    
    Args:
        db: Database connection
        content_id: ID of the content document
        processed: Whether the content has been processed
        error: Error message if processing failed
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_raw_content_collection(db)
    
    # Ensure content_id is ObjectId
    if isinstance(content_id, str):
        content_id = ObjectId(content_id)
    
    update_data = {
        'processed': processed,
        'last_processing_attempt': datetime.utcnow(),
        '$inc': {'processing_attempts': 1}
    }
    
    if error:
        update_data['processing_error'] = error
    
    result = collection.update_one(
        {'_id': content_id},
        {'$set': {k: v for k, v in update_data.items() if k != '$inc'}, 
         '$inc': update_data.get('$inc', {})}
    )
    
    return result.modified_count > 0

def get_raw_content_by_id(db, content_id):
    """
    Get raw content by ID
    
    Args:
        db: Database connection
        content_id: ID of the content document
        
    Returns:
        Content document or None
    """
    collection = get_raw_content_collection(db)
    
    # Ensure content_id is ObjectId
    if isinstance(content_id, str):
        content_id = ObjectId(content_id)
    
    return collection.find_one({'_id': content_id})

def get_raw_content_by_url(db, url):
    """
    Get raw content by URL
    
    Args:
        db: Database connection
        url: URL where content was extracted from
        
    Returns:
        Content document or None
    """
    collection = get_raw_content_collection(db)
    return collection.find_one({'url': url})

def get_unprocessed_content(db, limit=10, max_attempts=3, content_type=None):
    """
    Get unprocessed raw content for AI processing
    
    Args:
        db: Database connection
        limit: Maximum number of documents to return
        max_attempts: Maximum number of processing attempts
        content_type: Filter by content type (optional)
        
    Returns:
        List of unprocessed content documents
    """
    collection = get_raw_content_collection(db)
    
    # Build query
    query = {
        'processed': False,
        'processing_attempts': {'$lt': max_attempts}
    }
    
    if content_type:
        query['content_type'] = content_type
    
    # Sort by extraction date (oldest first)
    cursor = collection.find(query).sort([('extraction_date', ASCENDING)]).limit(limit)
    
    return list(cursor)

def get_raw_content_for_college(db, college_id, content_type=None, processed=None, skip=0, limit=20):
    """
    Get raw content for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        content_type: Filter by content type (optional)
        processed: Filter by processed status (optional)
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of content documents
    """
    collection = get_raw_content_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    
    if content_type:
        query['content_type'] = content_type
    
    if processed is not None:
        query['processed'] = processed
    
    # Sort by extraction date (newest first)
    cursor = collection.find(query).sort([('extraction_date', DESCENDING)]).skip(skip).limit(limit)
    
    return list(cursor)

def count_raw_content_for_college(db, college_id, content_type=None, processed=None):
    """
    Count raw content documents for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        content_type: Filter by content type (optional)
        processed: Filter by processed status (optional)
        
    Returns:
        Count of content documents
    """
    collection = get_raw_content_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    
    if content_type:
        query['content_type'] = content_type
    
    if processed is not None:
        query['processed'] = processed
    
    return collection.count_documents(query)

def delete_raw_content(db, content_id):
    """
    Delete raw content document
    
    Args:
        db: Database connection
        content_id: ID of the content document
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_raw_content_collection(db)
    
    # Ensure content_id is ObjectId
    if isinstance(content_id, str):
        content_id = ObjectId(content_id)
    
    result = collection.delete_one({'_id': content_id})
    return result.deleted_count > 0

def delete_raw_content_for_college(db, college_id):
    """
    Delete all raw content for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        Number of documents deleted
    """
    collection = get_raw_content_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    result = collection.delete_many({'college_id': college_id})
    return result.deleted_count

def get_raw_content_stats(db):
    """
    Get statistics about raw content
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    collection = get_raw_content_collection(db)
    
    # Total content
    total_content = collection.count_documents({})
    
    # Content by type
    admission_content = collection.count_documents({'content_type': 'admission'})
    placement_content = collection.count_documents({'content_type': 'placement'})
    internship_content = collection.count_documents({'content_type': 'internship'})
    
    # Processed vs unprocessed
    processed_content = collection.count_documents({'processed': True})
    unprocessed_content = collection.count_documents({'processed': False})
    
    # Processing errors
    with_errors = collection.count_documents({'processing_error': {'$ne': None}})
    
    return {
        'total_content': total_content,
        'admission_content': admission_content,
        'placement_content': placement_content,
        'internship_content': internship_content,
        'processed_content': processed_content,
        'unprocessed_content': unprocessed_content,
        'with_errors': with_errors
    }