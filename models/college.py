"""
College model representing educational institutions
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, TEXT

def create_indexes(db):
    """Create indexes for the colleges collection"""
    db.colleges.create_index([('name', TEXT), ('website', TEXT)])
    db.colleges.create_index([('type', ASCENDING)])
    db.colleges.create_index([('state', ASCENDING)])
    db.colleges.create_index([('status', ASCENDING)])
    db.colleges.create_index([('last_crawled', ASCENDING)])

def get_colleges_collection(db):
    """Get the colleges collection"""
    return db.colleges

def create_college(db, name, website, college_type, state, location=None, contact_info=None, 
                   established_year=None, affiliations=None, accreditations=None, status="active"):
    """
    Create a new college record
    
    Args:
        db: Database connection
        name: College name
        website: College website URL
        college_type: Type of college (Engineering/Medical)
        state: State where college is located
        location: Dictionary with city, address, coordinates
        contact_info: Dictionary with phone, email
        established_year: Year the college was established
        affiliations: List of affiliations
        accreditations: List of accreditations
        status: College status (active/inactive)
        
    Returns:
        Inserted college document ID
    """
    collection = get_colleges_collection(db)
    
    # Normalize website - ensure it has http/https
    if website and not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    college_doc = {
        "name": name,
        "website": website,
        "type": college_type,
        "state": state,
        "location": location or {},
        "contact_info": contact_info or {},
        "established_year": established_year,
        "affiliations": affiliations or [],
        "accreditations": accreditations or [],
        "last_crawled": None,
        "status": status,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = collection.insert_one(college_doc)
    return result.inserted_id

def update_college(db, college_id, update_data):
    """
    Update an existing college record
    
    Args:
        db: Database connection
        college_id: ID of the college to update
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_colleges_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Set updated timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update college document
    result = collection.update_one(
        {'_id': college_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def get_college_by_id(db, college_id):
    """
    Get a college by ID
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        College document or None
    """
    collection = get_colleges_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    return collection.find_one({'_id': college_id})

def get_college_by_website(db, website):
    """
    Get a college by website URL
    
    Args:
        db: Database connection
        website: College website URL
        
    Returns:
        College document or None
    """
    collection = get_colleges_collection(db)
    
    # Normalize website - ensure it has http/https
    if website and not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    return collection.find_one({'website': website})

def get_colleges(db, filters=None, skip=0, limit=20, sort_by='name', sort_order=1):
    """
    Get colleges with filtering, sorting and pagination
    
    Args:
        db: Database connection
        filters: Dictionary of filter conditions
        skip: Number of records to skip
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_order: Sort order (1 for ascending, -1 for descending)
        
    Returns:
        List of college documents
    """
    collection = get_colleges_collection(db)
    
    # Build query filters
    query = {}
    if filters:
        for key, value in filters.items():
            if value:
                if key == 'search':
                    # Text search on name and website
                    query['$text'] = {'$search': value}
                elif key in ['type', 'state', 'status']:
                    query[key] = value
    
    # Sort criteria
    sort_criteria = [(sort_by, sort_order)]
    
    # Execute query with pagination
    cursor = collection.find(query).sort(sort_criteria).skip(skip).limit(limit)
    
    return list(cursor)

def count_colleges(db, filters=None):
    """
    Count colleges matching the filters
    
    Args:
        db: Database connection
        filters: Dictionary of filter conditions
        
    Returns:
        Count of matching colleges
    """
    collection = get_colleges_collection(db)
    
    # Build query filters
    query = {}
    if filters:
        for key, value in filters.items():
            if value:
                if key == 'search':
                    # Text search on name and website
                    query['$text'] = {'$search': value}
                elif key in ['type', 'state', 'status']:
                    query[key] = value
    
    return collection.count_documents(query)

def update_college_crawl_status(db, college_id, last_crawled=None):
    """
    Update the last crawled timestamp for a college
    
    Args:
        db: Database connection
        college_id: ID of the college
        last_crawled: Timestamp of last crawl (defaults to now)
        
    Returns:
        True if update successful, False otherwise
    """
    if last_crawled is None:
        last_crawled = datetime.utcnow()
    
    return update_college(db, college_id, {'last_crawled': last_crawled})

def delete_college(db, college_id):
    """
    Delete a college record
    
    Args:
        db: Database connection
        college_id: ID of the college to delete
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_colleges_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    result = collection.delete_one({'_id': college_id})
    return result.deleted_count > 0

def bulk_import_colleges(db, colleges_data):
    """
    Import multiple colleges at once
    
    Args:
        db: Database connection
        colleges_data: List of college dictionaries
        
    Returns:
        Number of colleges imported
    """
    collection = get_colleges_collection(db)
    
    # Prepare documents for insertion
    docs_to_insert = []
    current_time = datetime.utcnow()
    
    for college in colleges_data:
        # Normalize website - ensure it has http/https
        website = college.get('website', '')
        if website and not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        
        college_doc = {
            "name": college.get('name', ''),
            "website": website,
            "type": college.get('type', 'Engineering'),
            "state": college.get('state', ''),
            "location": college.get('location', {}),
            "contact_info": college.get('contact_info', {}),
            "established_year": college.get('established_year'),
            "affiliations": college.get('affiliations', []),
            "accreditations": college.get('accreditations', []),
            "last_crawled": None,
            "status": college.get('status', 'active'),
            "created_at": current_time,
            "updated_at": current_time
        }
        docs_to_insert.append(college_doc)
    
    if docs_to_insert:
        result = collection.insert_many(docs_to_insert)
        return len(result.inserted_ids)
    return 0

# Helper functions
def get_states_list(db):
    """
    Get a list of states from the colleges collection
    
    Args:
        db: Database connection
        
    Returns:
        List of distinct states
    """
    collection = get_colleges_collection(db)
    return collection.distinct('state')

def get_summary_stats(db):
    """
    Get summary statistics about colleges
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    collection = get_colleges_collection(db)
    
    # Total colleges
    total_colleges = collection.count_documents({})
    
    # Colleges by type
    engineering_colleges = collection.count_documents({'type': 'Engineering'})
    medical_colleges = collection.count_documents({'type': 'Medical'})
    
    # Colleges with data
    colleges_with_data = collection.count_documents({'last_crawled': {'$ne': None}})
    
    # Colleges by status
    active_colleges = collection.count_documents({'status': 'active'})
    inactive_colleges = collection.count_documents({'status': 'inactive'})
    
    return {
        'total_colleges': total_colleges,
        'engineering_colleges': engineering_colleges,
        'medical_colleges': medical_colleges,
        'colleges_with_data': colleges_with_data,
        'active_colleges': active_colleges,
        'inactive_colleges': inactive_colleges
    }