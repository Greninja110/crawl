"""
Crawl job model for tracking web crawling operations
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

def create_indexes(db):
    """Create indexes for the crawl_jobs collection"""
    db.crawl_jobs.create_index([('college_id', ASCENDING)])
    db.crawl_jobs.create_index([('status', ASCENDING)])
    db.crawl_jobs.create_index([('timestamps.started', DESCENDING)])

def get_crawl_jobs_collection(db):
    """Get the crawl_jobs collection"""
    return db.crawl_jobs

def create_crawl_job(db, college_id, job_type="full_crawl", triggered_by=None):
    """
    Create a new crawl job
    
    Args:
        db: Database connection
        college_id: ID of the college to crawl
        job_type: Type of crawl job (full_crawl/update)
        triggered_by: User ID or 'system' indicating who triggered the job
        
    Returns:
        Inserted job document ID
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Ensure triggered_by is ObjectId if not 'system'
    if triggered_by and triggered_by != 'system' and isinstance(triggered_by, str):
        triggered_by = ObjectId(triggered_by)
    
    job_doc = {
        'college_id': college_id,
        'job_type': job_type,
        'status': 'queued',
        'timestamps': {
            'created': datetime.utcnow(),
            'started': None,
            'completed': None
        },
        'duration_seconds': None,
        'pages_crawled': 0,
        'pages_processed': 0,
        'progress_percentage': 0,
        'current_url': None,
        'errors': [],
        'crawling_stats': {
            'admission_pages': 0,
            'placement_pages': 0,
            'internship_pages': 0,
            'other_pages': 0
        },
        'triggered_by': triggered_by
    }
    
    result = collection.insert_one(job_doc)
    return result.inserted_id

def update_crawl_job_status(db, job_id, status, current_url=None, error=None):
    """
    Update the status of a crawl job
    
    Args:
        db: Database connection
        job_id: ID of the crawl job
        status: New status (queued/running/completed/failed)
        current_url: URL currently being processed
        error: Error message if job failed
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    # Build update data
    update_data = {'status': status}
    
    if current_url:
        update_data['current_url'] = current_url
    
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

def update_crawl_job_progress(db, job_id, pages_crawled=None, pages_processed=None, 
                             progress_percentage=None, current_url=None, 
                             admission_pages=None, placement_pages=None, 
                             internship_pages=None, other_pages=None):
    """
    Update the progress of a crawl job
    
    Args:
        db: Database connection
        job_id: ID of the crawl job
        pages_crawled: Number of pages crawled
        pages_processed: Number of pages processed
        progress_percentage: Overall progress percentage
        current_url: URL currently being processed
        admission_pages: Number of admission pages found
        placement_pages: Number of placement pages found
        internship_pages: Number of internship pages found
        other_pages: Number of other pages found
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    # Build update data
    update_data = {}
    
    if pages_crawled is not None:
        update_data['pages_crawled'] = pages_crawled
    
    if pages_processed is not None:
        update_data['pages_processed'] = pages_processed
    
    if progress_percentage is not None:
        update_data['progress_percentage'] = progress_percentage
    
    if current_url is not None:
        update_data['current_url'] = current_url
    
    # Update crawling stats
    if admission_pages is not None:
        update_data['crawling_stats.admission_pages'] = admission_pages
    
    if placement_pages is not None:
        update_data['crawling_stats.placement_pages'] = placement_pages
    
    if internship_pages is not None:
        update_data['crawling_stats.internship_pages'] = internship_pages
    
    if other_pages is not None:
        update_data['crawling_stats.other_pages'] = other_pages
    
    # Only update if we have fields to update
    if update_data:
        result = collection.update_one(
            {'_id': job_id},
            {'$set': update_data}
        )
        return result.modified_count > 0
    
    return False

def get_crawl_job_by_id(db, job_id):
    """
    Get a crawl job by ID
    
    Args:
        db: Database connection
        job_id: ID of the crawl job
        
    Returns:
        Crawl job document or None
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        try:
            job_id = ObjectId(job_id)
        except:
            return None
    
    return collection.find_one({'_id': job_id})

def get_active_crawl_job_for_college(db, college_id):
    """
    Get an active (queued or running) crawl job for a college
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        Crawl job document or None
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    return collection.find_one({
        'college_id': college_id,
        'status': {'$in': ['queued', 'running']}
    })

def get_crawl_jobs_for_college(db, college_id, skip=0, limit=20):
    """
    Get crawl jobs for a specific college with pagination
    
    Args:
        db: Database connection
        college_id: ID of the college
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of crawl job documents
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Sort by started timestamp (newest first)
    cursor = collection.find(
        {'college_id': college_id}
    ).sort([('timestamps.started', DESCENDING)]).skip(skip).limit(limit)
    
    return list(cursor)

def get_recent_crawl_jobs(db, status=None, skip=0, limit=20):
    """
    Get recent crawl jobs with optional status filter
    
    Args:
        db: Database connection
        status: Filter by status (optional)
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of crawl job documents
    """
    collection = get_crawl_jobs_collection(db)
    
    # Build query
    query = {}
    if status:
        query['status'] = status
    
    # Sort by created timestamp (newest first)
    cursor = collection.find(query).sort(
        [('timestamps.created', DESCENDING)]
    ).skip(skip).limit(limit)
    
    return list(cursor)

def count_crawl_jobs(db, status=None, college_id=None):
    """
    Count crawl jobs with optional filters
    
    Args:
        db: Database connection
        status: Filter by status (optional)
        college_id: Filter by college ID (optional)
        
    Returns:
        Count of matching crawl jobs
    """
    collection = get_crawl_jobs_collection(db)
    
    # Build query
    query = {}
    
    if status:
        query['status'] = status
    
    if college_id:
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            college_id = ObjectId(college_id)
        query['college_id'] = college_id
    
    return collection.count_documents(query)

def delete_crawl_job(db, job_id):
    """
    Delete a crawl job
    
    Args:
        db: Database connection
        job_id: ID of the crawl job
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_crawl_jobs_collection(db)
    
    # Ensure job_id is ObjectId
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)
    
    result = collection.delete_one({'_id': job_id})
    return result.deleted_count > 0

def get_crawl_job_stats(db):
    """
    Get statistics about crawl jobs
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    collection = get_crawl_jobs_collection(db)
    
    # Count jobs by status
    queued_jobs = collection.count_documents({'status': 'queued'})
    running_jobs = collection.count_documents({'status': 'running'})
    completed_jobs = collection.count_documents({'status': 'completed'})
    failed_jobs = collection.count_documents({'status': 'failed'})
    
    # Get average duration of completed jobs
    pipeline = [
        {'$match': {'status': 'completed', 'duration_seconds': {'$ne': None}}},
        {'$group': {'_id': None, 'avg_duration': {'$avg': '$duration_seconds'}}}
    ]
    duration_result = list(collection.aggregate(pipeline))
    avg_duration = duration_result[0]['avg_duration'] if duration_result else None
    
    # Get average number of pages per job
    pipeline = [
        {'$match': {'status': 'completed'}},
        {'$group': {'_id': None, 'avg_pages': {'$avg': '$pages_crawled'}}}
    ]
    pages_result = list(collection.aggregate(pipeline))
    avg_pages = pages_result[0]['avg_pages'] if pages_result else None
    
    return {
        'queued_jobs': queued_jobs,
        'running_jobs': running_jobs,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'avg_duration_seconds': avg_duration,
        'avg_pages_per_job': avg_pages
    }

def clear_stalled_jobs(db, stall_threshold_minutes=60):
    """
    Clear jobs that appear to be stalled (running for too long)
    
    Args:
        db: Database connection
        stall_threshold_minutes: Threshold in minutes
        
    Returns:
        Number of jobs cleared
    """
    collection = get_crawl_jobs_collection(db)
    
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
        update_crawl_job_status(
            db, 
            job['_id'], 
            'failed', 
            error=f"Job stalled (no updates for {stall_threshold_minutes} minutes)"
        )
        count += 1
    
    return count