"""
Web crawler service for extracting data from college websites
"""
import time
import re
import requests
import logging
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from models import get_db
from models.college import get_college_by_id, update_college_crawl_status
from models.crawl_job import (
    create_crawl_job, update_crawl_job_status, 
    update_crawl_job_progress, get_crawl_job_by_id
)
from models.raw_content import store_raw_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CollegeCrawler:
    """
    Web crawler for extracting data from college websites
    """
    def __init__(self, college_id, job_id, config):
        """
        Initialize the crawler
        
        Args:
            college_id: ID of the college to crawl
            job_id: ID of the crawl job
            config: Configuration object
        """
        self.db = get_db()
        self.college_id = college_id
        self.job_id = job_id
        self.config = config
        
        # Get college information
        self.college = get_college_by_id(self.db, college_id)
        if not self.college:
            raise ValueError(f"College with ID {college_id} not found")
        
        # Set up college-specific data
        self.website = self.college['website']
        self.domain = urlparse(self.website).netloc
        
        # Initialize crawling data structures
        self.visited_urls = set()
        self.queue = []
        self.crawled_pages = 0
        
        # Category counts
        self.admission_pages = 0
        self.placement_pages = 0
        self.internship_pages = 0
        self.other_pages = 0
        
        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; CollegeDataCrawler/1.0; +http://collegedatacrawler.example.com)',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9'
        })
    
    def start_crawl(self):
        """
        Start the crawling process
        
        Returns:
            Success status and message
        """
        try:
            # Update job status to running
            update_crawl_job_status(self.db, self.job_id, 'running')
            
            # Add the main URL to the queue
            self.queue.append((self.website, 0))  # (url, depth)
            
            # Crawl until queue is empty or maximum pages reached
            while self.queue and self.crawled_pages < self.config.MAX_PAGES_PER_COLLEGE:
                # Get next URL to process
                url, depth = self.queue.pop(0)
                
                # Skip if already visited
                if url in self.visited_urls:
                    continue
                
                # Mark as visited
                self.visited_urls.add(url)
                
                # Update job progress
                update_crawl_job_progress(
                    self.db,
                    self.job_id,
                    pages_crawled=self.crawled_pages,
                    progress_percentage=int((self.crawled_pages / self.config.MAX_PAGES_PER_COLLEGE) * 100),
                    current_url=url,
                    admission_pages=self.admission_pages,
                    placement_pages=self.placement_pages,
                    internship_pages=self.internship_pages,
                    other_pages=len(self.visited_urls) - (self.admission_pages + self.placement_pages + self.internship_pages)
                )
                
                # Process the URL
                self.process_url(url, depth)
                
                # Add delay between requests
                time.sleep(self.config.CRAWL_DELAY)
            
            # Update college's last crawl time
            update_college_crawl_status(self.db, self.college_id)
            
            # Update job status to completed
            update_crawl_job_status(self.db, self.job_id, 'completed')
            
            # Final update of job progress
            update_crawl_job_progress(
                self.db,
                self.job_id,
                pages_crawled=self.crawled_pages,
                progress_percentage=100,
                admission_pages=self.admission_pages,
                placement_pages=self.placement_pages,
                internship_pages=self.internship_pages,
                other_pages=len(self.visited_urls) - (self.admission_pages + self.placement_pages + self.internship_pages)
            )
            
            return True, f"Crawl completed: {self.crawled_pages} pages processed"
            
        except Exception as e:
            # Update job status to failed
            update_crawl_job_status(self.db, self.job_id, 'failed', str(e))
            logger.error(f"Crawl failed: {str(e)}", exc_info=True)
            return False, f"Crawl failed: {str(e)}"
    
    def process_url(self, url, depth):
        """
        Process a single URL
        
        Args:
            url: URL to process
            depth: Current crawl depth
        """
        try:
            # Fetch the content
            html_content, success = self.fetch_url(url)
            if not success:
                return
            
            # Increment crawled pages counter
            self.crawled_pages += 1
            
            # Determine the type of content
            content_type = self.categorize_content(url, html_content)
            
            # Store the content in the database
            store_raw_content(self.db, self.college_id, url, content_type, html_content)
            
            # Update category counts
            if content_type == 'admission':
                self.admission_pages += 1
            elif content_type == 'placement':
                self.placement_pages += 1
            elif content_type == 'internship':
                self.internship_pages += 1
            
            # If we're not at max depth, extract and queue links
            if depth < self.config.MAX_CRAWL_DEPTH:
                links = self.extract_links(url, html_content)
                
                # Add links to queue
                for link in links:
                    if link not in self.visited_urls:
                        self.queue.append((link, depth + 1))
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            # Don't re-raise the exception to allow the crawler to continue
    
    def fetch_url(self, url):
        """
        Fetch content from a URL
        
        Args:
            url: URL to fetch
            
        Returns:
            Tuple of (content, success)
        """
        try:
            response = self.session.get(
                url, 
                timeout=self.config.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            # Check if request was successful
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None, False
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                logger.info(f"Skipping non-HTML content at {url}: {content_type}")
                return None, False
            
            return response.text, True
            
        except requests.RequestException as e:
            logger.warning(f"Request error for {url}: {str(e)}")
            return None, False
    
    def extract_links(self, base_url, html_content):
        """
        Extract links from HTML content
        
        Args:
            base_url: Base URL for resolving relative links
            html_content: HTML content to extract links from
            
        Returns:
            List of absolute URLs
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Find all anchor tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip empty links, fragments, and non-HTTP protocols
            if not href or href.startswith('#') or href.startswith(('javascript:', 'mailto:', 'tel:')):
                continue
            
            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)
            
            # Parse the URL
            parsed_url = urlparse(absolute_url)
            
            # Only keep links to the same domain
            if parsed_url.netloc == self.domain:
                # Remove fragments
                clean_url = absolute_url.split('#')[0]
                
                # Skip common file types we don't want to process
                if not clean_url.endswith(('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif')):
                    links.append(clean_url)
        
        return links
    
    def categorize_content(self, url, html_content):
        """
        Categorize content based on URL and content analysis
        
        Args:
            url: URL of the content
            html_content: HTML content
            
        Returns:
            Content type (admission/placement/internship/general)
        """
        # First, check URL patterns
        url_lower = url.lower()
        
        # Check URL for obvious category indicators
        if any(term in url_lower for term in ['admission', 'apply', 'enroll', 'course', 'program', 'fee']):
            return 'admission'
        
        if any(term in url_lower for term in ['placement', 'recruit', 'career', 'company', 'job']):
            return 'placement'
        
        if any(term in url_lower for term in ['intern', 'training', 'apprentice']):
            return 'internship'
        
        # If URL doesn't give a clear indication, analyze content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.extract()
        
        # Get text content
        text = soup.get_text()
        text_lower = text.lower()
        
        # Define category keywords
        admission_keywords = [
            'admission', 'eligibility', 'criteria', 'fee', 'application', 
            'entrance exam', 'scholarship', 'hostel', 'course', 'program', 
            'bachelor', 'master', 'degree', 'diploma', 'eligibility'
        ]
        
        placement_keywords = [
            'placement', 'placed', 'recruited', 'companies visited', 'recruiter', 
            'job offer', 'placement record', 'salary package', 'campus interview',
            'placement cell', 'career'
        ]
        
        internship_keywords = [
            'internship', 'intern', 'summer training', 'industrial training',
            'practical training', 'apprentice', 'stipend'
        ]
        
        # Count keyword occurrences
        admission_score = sum(1 for keyword in admission_keywords if keyword in text_lower)
        placement_score = sum(1 for keyword in placement_keywords if keyword in text_lower)
        internship_score = sum(1 for keyword in internship_keywords if keyword in text_lower)
        
        # Get page headings for more context
        headings = ' '.join([h.get_text() for h in soup.find_all(['h1', 'h2', 'h3'])])
        headings_lower = headings.lower()
        
        # Add weight for keywords in headings
        admission_score += sum(3 for keyword in admission_keywords if keyword in headings_lower)
        placement_score += sum(3 for keyword in placement_keywords if keyword in headings_lower)
        internship_score += sum(3 for keyword in internship_keywords if keyword in headings_lower)
        
        # Determine category based on highest score
        if admission_score > placement_score and admission_score > internship_score:
            if admission_score >= 3:  # Threshold to avoid miscategorization
                return 'admission'
        
        if placement_score > admission_score and placement_score > internship_score:
            if placement_score >= 3:
                return 'placement'
        
        if internship_score > admission_score and internship_score > placement_score:
            if internship_score >= 3:
                return 'internship'
        
        # Default to general if no strong match
        return 'general'

def start_college_crawl(college_id, triggered_by=None):
    """
    Start a crawl job for a college
    
    Args:
        college_id: ID of the college to crawl
        triggered_by: User ID or 'system' indicating who triggered the job
        
    Returns:
        Tuple of (job_id, message)
    """
    db = get_db()
    
    # Create a new crawl job
    job_id = create_crawl_job(db, college_id, "full_crawl", triggered_by)
    
    # The actual crawling will be done by the worker process
    
    return job_id, "Crawl job created and queued"

def get_crawl_status(job_id):
    """
    Get the status of a crawl job
    
    Args:
        job_id: ID of the crawl job
        
    Returns:
        Crawl job status information
    """
    db = get_db()
    return get_crawl_job_by_id(db, job_id)

def get_crawl_progress(job_id):
    """
    Get the progress of a crawl job
    
    Args:
        job_id: ID of the crawl job
        
    Returns:
        Dictionary with progress information
    """
    job = get_crawl_status(job_id)
    
    if not job:
        return None
    
    return {
        'status': job.get('status'),
        'progress_percentage': job.get('progress_percentage', 0),
        'pages_crawled': job.get('pages_crawled', 0),
        'current_url': job.get('current_url'),
        'admission_pages': job.get('crawling_stats', {}).get('admission_pages', 0),
        'placement_pages': job.get('crawling_stats', {}).get('placement_pages', 0),
        'internship_pages': job.get('crawling_stats', {}).get('internship_pages', 0),
        'other_pages': job.get('crawling_stats', {}).get('other_pages', 0),
    }