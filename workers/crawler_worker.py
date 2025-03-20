"""
Background worker for processing crawl jobs
"""
import time
import logging
import threading
import queue
from datetime import datetime, timedelta
from models import get_db, init_db
from models.crawl_job import get_crawl_job_by_id, update_crawl_job_status, count_crawl_jobs
from services.crawler_service import CollegeCrawler
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Job queue
job_queue = queue.Queue()

# Active jobs
active_jobs = {}

# Worker threads
worker_threads = []

# Stop event for worker threads
stop_event = threading.Event()

def start_worker_thread(worker_id, config):
    """
    Start a worker thread
    
    Args:
        worker_id: ID of the worker
        config: Configuration object
    """
    thread = threading.Thread(target=worker_function, args=(worker_id, config))
    thread.daemon = True
    thread.start()
    return thread

def worker_function(worker_id, config):
    """
    Worker thread function for processing crawl jobs
    
    Args:
        worker_id: ID of the worker
        config: Configuration object
    """
    logger.info(f"Worker {worker_id} started")
    
    while not stop_event.is_set():
        try:
            # Try to get a job with a timeout
            try:
                job = job_queue.get(timeout=5)
            except queue.Empty:
                # No jobs in queue, check for new jobs from database
                poll_for_jobs()
                continue
            
            logger.info(f"Worker {worker_id} processing job {job['job_id']} for college {job['college_id']}")
            
            # Add to active jobs
            active_jobs[job['job_id']] = {
                'worker_id': worker_id,
                'job_id': job['job_id'],
                'college_id': job['college_id'],
                'start_time': datetime.utcnow()
            }
            
            try:
                # Create crawler
                crawler = CollegeCrawler(job['college_id'], job['job_id'], config)
                
                # Start crawling
                success, message = crawler.start_crawl()
                
                logger.info(f"Worker {worker_id} completed job {job['job_id']}: {message}")
                
            except Exception as e:
                logger.error(f"Worker {worker_id} failed job {job['job_id']}: {str(e)}", exc_info=True)
                
                try:
                    # Get a fresh DB connection for updating status
                    db = get_db()
                    update_crawl_job_status(db, job['job_id'], 'failed', str(e))
                except Exception as db_error:
                    logger.error(f"Failed to update job status: {str(db_error)}")
            
            # Remove from active jobs
            active_jobs.pop(job['job_id'], None)
            
            # Mark job as done
            job_queue.task_done()
            
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}", exc_info=True)
            time.sleep(5)  # Wait before retrying

def poll_for_jobs():
    """
    Poll the database for new crawl jobs
    """
    try:
        logger.info("Polling for new crawl jobs...")
        
        # Always get a fresh database connection for polling
        db = init_db()  # Use init_db instead of get_db to ensure a fresh connection
        
        # Get jobs with 'queued' status
        from models.crawl_job import get_recent_crawl_jobs
        
        try:
            queued_jobs = get_recent_crawl_jobs(db, 'queued', 0, 10)
            
            if queued_jobs:
                logger.info(f"Found {len(queued_jobs)} new crawl jobs")
                
                # Add jobs to queue
                for job in queued_jobs:
                    # Skip if already in queue or active
                    if str(job['_id']) in active_jobs:
                        logger.info(f"Job {job['_id']} already in active jobs, skipping")
                        continue
                    
                    # Add to queue
                    logger.info(f"Adding job {job['_id']} to queue for college {job['college_id']}")
                    job_queue.put({
                        'job_id': job['_id'],
                        'college_id': job['college_id']
                    })
                    
                    logger.info(f"Added job {job['_id']} to queue for college {job['college_id']}")
            else:
                logger.debug("No queued jobs found")
        except Exception as query_error:
            logger.error(f"Error querying for jobs: {str(query_error)}")
            # Don't re-raise to keep the worker running
    
    except Exception as e:
        logger.error(f"Error polling for jobs: {str(e)}")
        time.sleep(5)  # Wait before retrying

def start_workers(num_workers=2):
    """
    Start worker threads
    
    Args:
        num_workers: Number of worker threads to start
    """
    config = get_config()
    
    global worker_threads
    global stop_event
    
    # Reset stop event
    stop_event.clear()
    
    # Start workers
    for i in range(num_workers):
        thread = start_worker_thread(i, config)
        worker_threads.append(thread)
    
    logger.info(f"Started {num_workers} worker threads")

def stop_workers():
    """
    Stop all worker threads
    """
    global stop_event
    global worker_threads
    
    # Set stop event
    stop_event.set()
    
    # Wait for threads to finish
    for thread in worker_threads:
        thread.join(timeout=10)
    
    # Clear thread list
    worker_threads = []
    
    logger.info("All worker threads stopped")

def enqueue_job(job_id, college_id):
    """
    Enqueue a job for processing
    
    Args:
        job_id: ID of the crawl job
        college_id: ID of the college
    """
    job_queue.put({
        'job_id': job_id,
        'college_id': college_id
    })
    
    logger.info(f"Enqueued job {job_id} for college {college_id}")

def get_queue_status():
    """
    Get the status of the job queue
    
    Returns:
        Dictionary with queue status
    """
    return {
        'queue_size': job_queue.qsize(),
        'active_jobs': len(active_jobs),
        'active_job_details': [
            {
                'job_id': str(job_id),
                'worker_id': details['worker_id'],
                'college_id': str(details['college_id']),
                'running_time': (datetime.utcnow() - details['start_time']).total_seconds() // 60  # minutes
            }
            for job_id, details in active_jobs.items()
        ],
        'worker_count': len(worker_threads)
    }

def check_stalled_jobs():
    """
    Check for jobs that appear to be stalled
    
    Returns:
        Number of cleared stalled jobs
    """
    global active_jobs
    
    now = datetime.utcnow()
    stalled_jobs = []
    
    # Find jobs running for more than 30 minutes
    for job_id, details in active_jobs.items():
        running_time = now - details['start_time']
        if running_time > timedelta(minutes=30):
            stalled_jobs.append(job_id)
    
    # Clear stalled jobs
    count = 0
    
    try:
        # Get a fresh DB connection
        db = get_db()
        
        for job_id in stalled_jobs:
            logger.warning(f"Clearing stalled job {job_id}")
            try:
                update_crawl_job_status(db, job_id, 'failed', "Job stalled (running for too long)")
                active_jobs.pop(job_id, None)
                count += 1
            except Exception as e:
                logger.error(f"Error clearing stalled job {job_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting database connection: {str(e)}")
    
    return count

# Initialize workers when the module is imported
def init_workers():
    try:
        config = get_config()
        num_workers = config.CRAWLER_WORKERS
        start_workers(num_workers)
    except Exception as e:
        logger.error(f"Failed to initialize workers: {str(e)}")