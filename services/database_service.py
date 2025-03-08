"""
Database service for managing college data and imports/exports
"""
import json
import csv
import os
import logging
from datetime import datetime
from bson import ObjectId
from models import get_db
from models.college import (
    bulk_import_colleges, get_colleges, count_colleges,
    get_summary_stats as get_college_summary_stats,
    get_states_list
)
from models.raw_content import get_raw_content_stats
from models.admission_data import get_admission_data_stats
from models.placement_data import get_placement_stats_by_year
from models.crawl_job import get_crawl_job_stats
from models.ai_processing_job import get_ai_processing_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_colleges_paginated(page=1, per_page=20, filters=None, sort_by='name', sort_order=1):
    """
    Get paginated list of colleges with optional filtering and sorting
    
    Args:
        page: Page number (1-based)
        per_page: Number of colleges per page
        filters: Dictionary of filter conditions
        sort_by: Field to sort by
        sort_order: Sort order (1 for ascending, -1 for descending)
        
    Returns:
        Dictionary with colleges list and pagination info
    """
    db = get_db()
    skip = (page - 1) * per_page
    
    # Get colleges
    colleges = get_colleges(db, filters, skip, per_page, sort_by, sort_order)
    
    # Count total matching colleges
    total = count_colleges(db, filters)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return {
        'colleges': colleges,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    }

def import_colleges_from_file(file_path, college_type=None):
    """
    Import colleges from a JSON or CSV file
    
    Args:
        file_path: Path to the file
        college_type: Default college type if not specified in file
        
    Returns:
        Tuple of (success status, message, count of imported colleges)
    """
    db = get_db()
    
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.json':
            # Import from JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if not isinstance(data, list):
                return False, "JSON file must contain a list of colleges", 0
            
            # Process data
            colleges_data = []
            for item in data:
                if not isinstance(item, dict) or 'name' not in item or 'website' not in item:
                    continue
                
                # Set default type if not specified
                if 'type' not in item and college_type:
                    item['type'] = college_type
                
                colleges_data.append(item)
            
        elif file_ext in ['.csv', '.txt']:
            # Import from CSV
            colleges_data = []
            with open(file_path, 'r', encoding='utf-8') as f:
                # Try to detect the dialect
                dialect = csv.Sniffer().sniff(f.read(1024))
                f.seek(0)
                
                # Read CSV
                reader = csv.DictReader(f, dialect=dialect)
                
                for row in reader:
                    # Check required fields
                    if 'name' not in row or 'website' not in row:
                        continue
                    
                    # Set default type if not specified
                    if ('type' not in row or not row['type']) and college_type:
                        row['type'] = college_type
                    
                    colleges_data.append(row)
        else:
            return False, f"Unsupported file format: {file_ext}", 0
        
        if not colleges_data:
            return False, "No valid college data found in file", 0
        
        # Import colleges to database
        count = bulk_import_colleges(db, colleges_data)
        
        return True, f"Successfully imported {count} colleges", count
        
    except Exception as e:
        logger.error(f"Error importing colleges: {str(e)}", exc_info=True)
        return False, f"Error importing colleges: {str(e)}", 0

def export_colleges_to_file(file_path, college_ids=None):
    """
    Export colleges to a JSON or CSV file
    
    Args:
        file_path: Path to the output file
        college_ids: List of college IDs to export (None for all)
        
    Returns:
        Tuple of (success status, message, count of exported colleges)
    """
    db = get_db()
    
    try:
        # Get colleges
        filters = None
        if college_ids:
            # Convert string IDs to ObjectId
            object_ids = [ObjectId(id) if isinstance(id, str) else id for id in college_ids]
            filters = {'_id': {'$in': object_ids}}
        
        colleges = get_colleges(db, filters, 0, 0)  # No pagination
        
        if not colleges:
            return False, "No colleges found to export", 0
        
        # Process colleges for export (convert ObjectId to string)
        export_data = []
        for college in colleges:
            college_dict = dict(college)
            college_dict['_id'] = str(college_dict['_id'])
            export_data.append(college_dict)
        
        # Determine export format from file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.json':
            # Export to JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        elif file_ext in ['.csv', '.txt']:
            # Export to CSV
            # Determine fields to export
            fields = set()
            for college in export_data:
                fields.update(college.keys())
            
            fields = sorted(list(fields))
            
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(export_data)
        else:
            return False, f"Unsupported file format: {file_ext}", 0
        
        return True, f"Successfully exported {len(export_data)} colleges to {file_path}", len(export_data)
        
    except Exception as e:
        logger.error(f"Error exporting colleges: {str(e)}", exc_info=True)
        return False, f"Error exporting colleges: {str(e)}", 0

def get_database_statistics():
    """
    Get statistics about the database
    
    Returns:
        Dictionary with database statistics
    """
    db = get_db()
    
    stats = {
        'colleges': get_college_summary_stats(db),
        'content': get_raw_content_stats(db),
        'admission': get_admission_data_stats(db),
        'placement': {
            'recent_years': get_placement_stats_by_year(db, top_n=5)
        },
        'jobs': {
            'crawl': get_crawl_job_stats(db),
            'ai_processing': get_ai_processing_stats(db)
        },
        'states': get_states_list(db),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return stats

def get_college_filter_options():
    """
    Get options for college filters
    
    Returns:
        Dictionary with filter options
    """
    db = get_db()
    
    states = get_states_list(db)
    types = ["Engineering", "Medical"]
    
    return {
        'states': states,
        'types': types
    }

def backup_database(backup_dir):
    """
    Create a backup of the database
    
    Args:
        backup_dir: Directory to store the backup
        
    Returns:
        Tuple of (success status, message)
    """
    try:
        # Ensure backup directory exists
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate timestamp for backup files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Get database
        db = get_db()
        
        # Get collections to backup
        collections = [
            'colleges', 'raw_content', 'admission_data', 'placement_data', 
            'internship_data', 'crawl_jobs', 'ai_processing_jobs', 'users'
        ]
        
        for collection_name in collections:
            # Get collection data
            collection = db[collection_name]
            data = list(collection.find())
            
            # Convert ObjectId to string for JSON serialization
            for item in data:
                item['_id'] = str(item['_id'])
                
                # Also convert other ObjectId fields
                for key, value in item.items():
                    if isinstance(value, ObjectId):
                        item[key] = str(value)
                    
                    # Check for ObjectId in nested dictionaries
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            if isinstance(v, ObjectId):
                                value[k] = str(v)
            
            # Write to backup file
            file_path = os.path.join(backup_dir, f"{collection_name}_{timestamp}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Backed up {len(data)} documents from {collection_name} to {file_path}")
        
        return True, f"Successfully backed up database to {backup_dir}"
        
    except Exception as e:
        logger.error(f"Error backing up database: {str(e)}", exc_info=True)
        return False, f"Error backing up database: {str(e)}"

def get_database_collection_stats():
    """
    Get statistics about database collections
    
    Returns:
        Dictionary with collection statistics
    """
    db = get_db()
    
    collections = [
        'colleges', 'raw_content', 'admission_data', 'placement_data', 
        'internship_data', 'crawl_jobs', 'ai_processing_jobs', 'users'
    ]
    
    stats = {}
    for collection_name in collections:
        collection = db[collection_name]
        stats[collection_name] = {
            'count': collection.count_documents({}),
            'indexes': list(collection.index_information().keys()),
            'size': collection.estimated_document_count()  # Approximate size
        }
    
    return stats