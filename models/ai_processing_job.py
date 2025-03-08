"""
AI processing job model for tracking AI processing operations
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

def create_indexes(db):
    """Create indexes for the ai_processing_jobs collection"""
    db.ai_processing_jobs.create_index([('college_id', ASCENDING)])
    db.ai_processing_jobs.create_index([('raw_content_id', ASCENDING)])
    db.ai_processing_jobs.create_index([('status', ASCENDING)])
    db.ai_processing_jobs.create_index([('content_type', ASCENDING)])
    db.ai_processing_jobs.create_index([('timestamps.started', DESCENDING)])

def get_ai_processing_jobs_collection(db):
    """Get the ai_processing_jobs collection"""
    return db.ai_processing_jobs

def create_ai_processing_job(db, college_id, raw_content_id, content_type):
    """
    Create a new AI processing job
    
    Args:
        db: Database connection
        college_id: ID of the college
        raw_content_id: ID of the raw content to process
        content_type: Type of content (admission/placement/internship)
        
    Returns:
        Inserted job document ID
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure IDs are ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    if isinstance(raw_content_id, str):
        raw_content_id = ObjectId(raw_content_id)
    
    job_doc = {
        'college_id': college_id,
        'raw_content_id': raw_content_id,
        'content_type': content_type,
        'status': 'queued',
        'timestamps': {
            'created': datetime.utcnow(),
            'started': None,
            'completed': None
        },
        'duration_seconds': None,
        'model_used': None,
        'confidence_score': None,
        'errors': [],
        'result_document_id': None,
        'prompt_used': None,
        'ai_response': None
    }
    
    result = collection.insert_one(job_doc)
    return result.inserted_id

def update_ai_processing_job_status(db, job_id, status, error=None):
    """
    Update the status of an AI processing job
    
    Args:
        db: Database connection
        job_id: ID of the AI processing job
        status: New status (queued/running/completed/failed)
        error: Error message if job failed
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    # Build update data
    update_data = {'status': status}
    
    # Update timestamps based on status
    if status == 'running':
        update_data['timestamps.started'] = datetime.utcnow()
    elif status in ['completed', 'failed']:
        now = datetime.utcnow()
        update_data['timestamps.completed'] = now
        
        # Calculate duration if started timestamp exists
        job = collection.find_one({'_id': job_id})
        if job and job.get('timestamps', {}).get('started'):
            started = job['timestamps']['started']
            update_data['duration_seconds'] = (now - started).total_seconds()
    
    # Add error if provided
    if error:
        update_data['$push'] = {'errors': {
            'message': error,
            'timestamp': datetime.utcnow()
        }}
    
    # Update document
    result = collection.update_one(
        {'_id': job_id},
        {'$set': {k: v for k, v in update_data.items() if not k.startswith('$')}}
    )
    
    # If we have a $push operation, do it separately
    if '$push' in update_data:
        collection.update_one(
            {'_id': job_id},
            {'$push': update_data['$push']}
        )
    
    return result.modified_count > 0

def update_ai_processing_job_result(db, job_id, model_used, confidence_score, 
                                  result_document_id, prompt_used=None, ai_response=None):
    """
    Update the result of an AI processing job
    
    Args:
        db: Database connection
        job_id: ID of the AI processing job
        model_used: Name of the AI model used
        confidence_score: Confidence score of the result
        result_document_id: ID of the resulting document (in admission/placement/internship collection)
        prompt_used: The prompt used for the AI model
        ai_response: The raw response from the AI model
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure job_id and result_document_id are ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    if isinstance(result_document_id, str):
        result_document_id = ObjectId(result_document_id)
    
    # Build update data
    update_data = {
        'model_used': model_used,
        'confidence_score': confidence_score,
        'result_document_id': result_document_id
    }
    
    if prompt_used:
        update_data['prompt_used'] = prompt_used
    
    if ai_response:
        update_data['ai_response'] = ai_response
    
    result = collection.update_one(
        {'_id': job_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def get_ai_processing_job_by_id(db, job_id):
    """
    Get an AI processing job by ID
    
    Args:
        db: Database connection
        job_id: ID of the AI processing job
        
    Returns:
        AI processing job document or None
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        try:
            job_id = ObjectId(job_id)
        except:
            return None
    
    return collection.find_one({'_id': job_id})

def get_ai_processing_job_by_raw_content(db, raw_content_id):
    """
    Get AI processing job for a specific raw content
    
    Args:
        db: Database connection
        raw_content_id: ID of the raw content
        
    Returns:
        AI processing job document or None
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure raw_content_id is ObjectId
    if isinstance(raw_content_id, str):
        raw_content_id = ObjectId(raw_content_id)
    
    return collection.find_one({'raw_content_id': raw_content_id})

def get_queued_ai_processing_jobs(db, content_type=None, limit=10):
    """
    Get queued AI processing jobs
    
    Args:
        db: Database connection
        content_type: Filter by content type (optional)
        limit: Maximum number of jobs to return
        
    Returns:
        List of AI processing job documents
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Build query
    query = {'status': 'queued'}
    if content_type:
        query['content_type'] = content_type
    
    # Sort by created timestamp (oldest first)
    cursor = collection.find(query).sort(
        [('timestamps.created', ASCENDING)]
    ).limit(limit)
    
    return list(cursor)

def get_ai_processing_jobs_for_college(db, college_id, status=None, skip=0, limit=20):
    """
    Get AI processing jobs for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        status: Filter by status (optional)
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of AI processing job documents
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    if status:
        query['status'] = status
    
    # Sort by created timestamp (newest first)
    cursor = collection.find(query).sort(
        [('timestamps.created', DESCENDING)]
    ).skip(skip).limit(limit)
    
    return list(cursor)

def count_ai_processing_jobs(db, status=None, content_type=None, college_id=None):
    """
    Count AI processing jobs with optional filters
    
    Args:
        db: Database connection
        status: Filter by status (optional)
        content_type: Filter by content type (optional)
        college_id: Filter by college ID (optional)
        
    Returns:
        Count of matching AI processing jobs
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Build query
    query = {}
    
    if status:
        query['status'] = status
    
    if content_type:
        query['content_type'] = content_type
    
    if college_id:
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            college_id = ObjectId(college_id)
        query['college_id'] = college_id
    
    return collection.count_documents(query)

def delete_ai_processing_job(db, job_id):
    """
    Delete an AI processing job
    
    Args:
        db: Database connection
        job_id: ID of the AI processing job
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    result = collection.delete_one({'_id': job_id})
    return result.deleted_count > 0

def get_ai_processing_stats(db):
    """
    Get statistics about AI processing jobs
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Count jobs by status
    queued_jobs = collection.count_documents({'status': 'queued'})
    running_jobs = collection.count_documents({'status': 'running'})
    completed_jobs = collection.count_documents({'status': 'completed'})
    failed_jobs = collection.count_documents({'status': 'failed'})
    
    # Count jobs by content type
    admission_jobs = collection.count_documents({'content_type': 'admission'})
    placement_jobs = collection.count_documents({'content_type': 'placement'})
    internship_jobs = collection.count_documents({'content_type': 'internship'})
    
    # Get average duration of completed jobs
    pipeline = [
        {'$match': {'status': 'completed', 'duration_seconds': {'$ne': None}}},
        {'$group': {'_id': None, 'avg_duration': {'$avg': '$duration_seconds'}}}
    ]
    duration_result = list(collection.aggregate(pipeline))
    avg_duration = duration_result[0]['avg_duration'] if duration_result else None
    
    # Get average confidence score
    pipeline = [
        {'$match': {'status': 'completed', 'confidence_score': {'$ne': None}}},
        {'$group': {'_id': None, 'avg_confidence': {'$avg': '$confidence_score'}}}
    ]
    confidence_result = list(collection.aggregate(pipeline))
    avg_confidence = confidence_result[0]['avg_confidence'] if confidence_result else None
    
    return {
        'queued_jobs': queued_jobs,
        'running_jobs': running_jobs,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'admission_jobs': admission_jobs,
        'placement_jobs': placement_jobs,
        'internship_jobs': internship_jobs,
        'avg_duration_seconds': avg_duration,
        'avg_confidence_score': avg_confidence
    }

def clear_stalled_jobs(db, stall_threshold_minutes=30):
    """
    Clear jobs that appear to be stalled (running for too long)
    
    Args:
        db: Database connection
        stall_threshold_minutes: Threshold in minutes
        
    Returns:
        Number of jobs cleared
    """
    collection = get_ai_processing_jobs_collection(db)
    
    # Calculate threshold timestamp
    threshold_time = datetime.utcnow() - datetime.timedelta(minutes=stall_threshold_minutes)
    
    # Find running jobs started before threshold
    stalled_jobs = collection.find({
        'status': 'running',
        'timestamps.started': {'$lt': threshold_time}
    })
    
    count = 0
    for job in stalled_jobs:
        # Update job status to failed
        update_ai_processing_job_status(
            db, 
            job['_id'], 
            'failed', 
            error=f"Job stalled (no updates for {stall_threshold_minutes} minutes)"
        )
        count += 1
    
    return count