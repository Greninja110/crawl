"""
Crawl job model for tracking web crawling operations
"""
from datetime import datetime
import logging
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_indexes(db):
    """Create indexes for the crawl_jobs collection"""
    try:
        logger.info("Creating indexes for crawl_jobs collection")
        db.crawl_jobs.create_index([('college_id', ASCENDING)])
        db.crawl_jobs.create_index([('status', ASCENDING)])
        db.crawl_jobs.create_index([('timestamps.started', DESCENDING)])
        logger.info("Successfully created indexes for crawl_jobs collection")
    except Exception as e:
        logger.error(f"Error creating indexes for crawl_jobs: {str(e)}")

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
    try:
        logger.info(f"Creating new crawl job for college_id: {college_id}, job_type: {job_type}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            logger.debug(f"Converting college_id string to ObjectId: {college_id}")
            college_id = ObjectId(college_id)
        
        # Ensure triggered_by is ObjectId if not 'system'
        if triggered_by and triggered_by != 'system' and isinstance(triggered_by, str):
            logger.debug(f"Converting triggered_by string to ObjectId: {triggered_by}")
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
        job_id = result.inserted_id
        logger.info(f"Successfully created crawl job with ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Error creating crawl job: {str(e)}", exc_info=True)
        return None

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
    try:
        logger.info(f"Updating crawl job status: job_id={job_id}, new_status={status}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure job_id is ObjectId
        if isinstance(job_id, str):
            logger.debug(f"Converting job_id string to ObjectId: {job_id}")
            job_id = ObjectId(job_id)
        
        # Build update data
        update_data = {'status': status}
        
        if current_url:
            update_data['current_url'] = current_url
            logger.debug(f"Setting current_url to: {current_url}")
        
        # Update timestamps based on status
        if status == 'running':
            update_data['timestamps.started'] = datetime.utcnow()
            logger.debug(f"Job {job_id} is now running, setting start timestamp")
        elif status in ['completed', 'failed']:
            now = datetime.utcnow()
            update_data['timestamps.completed'] = now
            logger.debug(f"Job {job_id} is now {status}, setting completion timestamp")
            
            # Calculate duration if started timestamp exists
            job = collection.find_one({'_id': job_id})
            if job and job.get('timestamps', {}).get('started'):
                started = job['timestamps']['started']
                duration = (now - started).total_seconds()
                update_data['duration_seconds'] = duration
                logger.debug(f"Job duration: {duration} seconds")
        
        # Add error if provided
        if error:
            logger.warning(f"Job {job_id} error: {error}")
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
        
        success = result.modified_count > 0
        if success:
            logger.info(f"Successfully updated job {job_id} status to {status}")
        else:
            logger.warning(f"Failed to update job {job_id} status. Job may not exist.")
        
        return success
    except Exception as e:
        logger.error(f"Error updating crawl job status: {str(e)}", exc_info=True)
        return False

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
    try:
        logger.debug(f"Updating crawl job progress: job_id={job_id}, pages_crawled={pages_crawled}, progress={progress_percentage}%")
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
            success = result.modified_count > 0
            if not success:
                logger.warning(f"Failed to update job {job_id} progress. Job may not exist.")
            return success
        
        return False
    except Exception as e:
        logger.error(f"Error updating crawl job progress: {str(e)}", exc_info=True)
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
    try:
        logger.debug(f"Getting crawl job by ID: {job_id}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure job_id is ObjectId
        if isinstance(job_id, str):
            try:
                job_id = ObjectId(job_id)
            except Exception as e:
                logger.error(f"Invalid job_id format: {job_id}, error: {str(e)}")
                return None
        
        job = collection.find_one({'_id': job_id})
        if job:
            logger.debug(f"Found job {job_id} with status: {job.get('status')}")
        else:
            logger.warning(f"No job found with ID: {job_id}")
        return job
    except Exception as e:
        logger.error(f"Error getting crawl job: {str(e)}", exc_info=True)
        return None

def get_active_crawl_job_for_college(db, college_id):
    """
    Get an active (queued or running) crawl job for a college
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        Crawl job document or None
    """
    try:
        logger.debug(f"Getting active crawl job for college: {college_id}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            college_id = ObjectId(college_id)
        
        job = collection.find_one({
            'college_id': college_id,
            'status': {'$in': ['queued', 'running']}
        })
        
        if job:
            logger.debug(f"Found active job {job['_id']} for college {college_id}, status: {job['status']}")
        else:
            logger.debug(f"No active job found for college {college_id}")
        
        return job
    except Exception as e:
        logger.error(f"Error getting active crawl job: {str(e)}", exc_info=True)
        return None

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
    try:
        logger.debug(f"Getting crawl jobs for college: {college_id}, skip={skip}, limit={limit}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            college_id = ObjectId(college_id)
        
        # Sort by started timestamp (newest first)
        cursor = collection.find(
            {'college_id': college_id}
        ).sort([('timestamps.started', DESCENDING)]).skip(skip).limit(limit)
        
        jobs = list(cursor)
        logger.debug(f"Found {len(jobs)} crawl jobs for college {college_id}")
        return jobs
    except Exception as e:
        logger.error(f"Error getting crawl jobs for college: {str(e)}", exc_info=True)
        return []

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
    try:
        if status:
            logger.debug(f"Getting recent crawl jobs with status: {status}, skip={skip}, limit={limit}")
        else:
            logger.debug(f"Getting recent crawl jobs, skip={skip}, limit={limit}")
        
        collection = get_crawl_jobs_collection(db)
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        
        # Sort by created timestamp (newest first)
        cursor = collection.find(query).sort(
            [('timestamps.created', DESCENDING)]
        ).skip(skip).limit(limit)
        
        jobs = list(cursor)
        logger.debug(f"Found {len(jobs)} recent crawl jobs")
        return jobs
    except Exception as e:
        logger.error(f"Error getting recent crawl jobs: {str(e)}", exc_info=True)
        return []

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
    try:
        logger.debug(f"Counting crawl jobs, status filter: {status}, college_id filter: {college_id}")
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
        
        count = collection.count_documents(query)
        logger.debug(f"Count result: {count} jobs")
        return count
    except Exception as e:
        logger.error(f"Error counting crawl jobs: {str(e)}", exc_info=True)
        return 0

def delete_crawl_job(db, job_id):
    """
    Delete a crawl job
    
    Args:
        db: Database connection
        job_id: ID of the crawl job
        
    Returns:
        True if deletion successful, False otherwise
    """
    try:
        logger.info(f"Deleting crawl job: {job_id}")
        collection = get_crawl_jobs_collection(db)
        
        # Ensure job_id is ObjectId
        if isinstance(job_id, str):
            job_id = ObjectId(job_id)
        
        result = collection.delete_one({'_id': job_id})
        success = result.deleted_count > 0
        
        if success:
            logger.info(f"Successfully deleted crawl job {job_id}")
        else:
            logger.warning(f"Failed to delete crawl job {job_id}. Job may not exist.")
        
        return success
    except Exception as e:
        logger.error(f"Error deleting crawl job: {str(e)}", exc_info=True)
        return False

def get_crawl_job_stats(db):
    """
    Get statistics about crawl jobs
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    try:
        logger.debug("Getting crawl job statistics")
        collection = get_crawl_jobs_collection(db)
        
        # Count jobs by status
        queued_jobs = collection.count_documents({'status': 'queued'})
        running_jobs = collection.count_documents({'status': 'running'})
        completed_jobs = collection.count_documents({'status': 'completed'})
        failed_jobs = collection.count_documents({'status': 'failed'})
        
        logger.debug(f"Job counts - Queued: {queued_jobs}, Running: {running_jobs}, " +
                   f"Completed: {completed_jobs}, Failed: {failed_jobs}")
        
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
        
        stats = {
            'queued_jobs': queued_jobs,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'avg_duration_seconds': avg_duration,
            'avg_pages_per_job': avg_pages
        }
        
        logger.debug(f"Crawl job statistics: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error getting crawl job stats: {str(e)}", exc_info=True)
        return {
            'queued_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'avg_duration_seconds': None,
            'avg_pages_per_job': None
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
    try:
        logger.info(f"Checking for stalled jobs (threshold: {stall_threshold_minutes} minutes)")
        collection = get_crawl_jobs_collection(db)
        
        # Calculate threshold timestamp
        import datetime as dt
        threshold_time = datetime.utcnow() - dt.timedelta(minutes=stall_threshold_minutes)
        
        # Find running jobs started before threshold
        stalled_jobs = collection.find({
            'status': 'running',
            'timestamps.started': {'$lt': threshold_time}
        })
        
        count = 0
        for job in stalled_jobs:
            # Update job status to failed
            logger.warning(f"Found stalled job {job['_id']}, started at {job['timestamps']['started']}")
            update_crawl_job_status(
                db, 
                job['_id'], 
                'failed', 
                error=f"Job stalled (no updates for {stall_threshold_minutes} minutes)"
            )
            count += 1
        
        logger.info(f"Cleared {count} stalled jobs")
        return count
    except Exception as e:
        logger.error(f"Error clearing stalled jobs: {str(e)}", exc_info=True)
        return 0