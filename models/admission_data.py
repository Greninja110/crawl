"""
Admission data model for storing structured admission information
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, TEXT

def create_indexes(db):
    """Create indexes for the admission_data collection"""
    db.admission_data.create_index([('college_id', ASCENDING)])
    db.admission_data.create_index([('last_updated', DESCENDING)])
    # Text index on courses and eligibility for searching
    db.admission_data.create_index([
        ('courses.name', TEXT),
        ('courses.eligibility', TEXT),
        ('application_process', TEXT)
    ])

def get_admission_data_collection(db):
    """Get the admission_data collection"""
    return db.admission_data

def store_admission_data(db, college_id, source_urls, courses=None, application_process=None, 
                        important_dates=None, hostel_facilities=None, metadata=None):
    """
    Store structured admission data
    
    Args:
        db: Database connection
        college_id: ID of the college
        source_urls: List of URLs from which data was extracted
        courses: List of course dictionaries
        application_process: Description of application process
        important_dates: List of event-date dictionaries
        hostel_facilities: Dictionary with hostel information
        metadata: Additional metadata (processing_id, confidence_score, etc.)
        
    Returns:
        Inserted document ID
    """
    collection = get_admission_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Check if admission data already exists for this college
    existing_data = collection.find_one({'college_id': college_id})
    
    if existing_data:
        # Update existing document
        update_data = {
            'source_urls': list(set(existing_data.get('source_urls', []) + source_urls)),
            'last_updated': datetime.utcnow()
        }
        
        # Update courses if provided
        if courses:
            # Merge with existing courses
            existing_courses = existing_data.get('courses', [])
            # Create a dictionary of courses by name for easy lookup
            course_dict = {course.get('name', ''): course for course in existing_courses if course.get('name')}
            
            for course in courses:
                course_name = course.get('name', '')
                if course_name in course_dict:
                    # Update existing course with new information
                    merged_course = course_dict[course_name].copy()
                    merged_course.update({k: v for k, v in course.items() if v})
                    course_dict[course_name] = merged_course
                else:
                    # Add new course
                    course_dict[course_name] = course
            
            update_data['courses'] = list(course_dict.values())
        
        # Update other fields if provided
        if application_process:
            update_data['application_process'] = application_process
        
        if important_dates:
            # Merge with existing dates
            existing_dates = existing_data.get('important_dates', [])
            all_dates = existing_dates + important_dates
            # Remove duplicates by event name
            event_dict = {date.get('event', ''): date for date in all_dates if date.get('event')}
            update_data['important_dates'] = list(event_dict.values())
        
        if hostel_facilities:
            # Merge with existing hostel facilities
            existing_facilities = existing_data.get('hostel_facilities', {})
            merged_facilities = existing_facilities.copy()
            merged_facilities.update(hostel_facilities)
            update_data['hostel_facilities'] = merged_facilities
        
        if metadata:
            # Set new metadata
            update_data['metadata'] = metadata
        
        # Update document
        collection.update_one(
            {'college_id': college_id},
            {'$set': update_data}
        )
        
        return existing_data['_id']
    else:
        # Create new document
        admission_doc = {
            'college_id': college_id,
            'source_urls': source_urls,
            'courses': courses or [],
            'application_process': application_process,
            'important_dates': important_dates or [],
            'hostel_facilities': hostel_facilities or {},
            'metadata': metadata or {},
            'created_at': datetime.utcnow(),
            'last_updated': datetime.utcnow()
        }
        
        result = collection.insert_one(admission_doc)
        return result.inserted_id

def get_admission_data_by_college(db, college_id):
    """
    Get admission data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        Admission data document or None
    """
    collection = get_admission_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    return collection.find_one({'college_id': college_id})

def get_admission_data_by_id(db, admission_id):
    """
    Get admission data by ID
    
    Args:
        db: Database connection
        admission_id: ID of the admission data document
        
    Returns:
        Admission data document or None
    """
    collection = get_admission_data_collection(db)
    
    # Ensure admission_id is ObjectId
    if isinstance(admission_id, str):
        admission_id = ObjectId(admission_id)
    
    return collection.find_one({'_id': admission_id})

def update_admission_data(db, admission_id, update_data):
    """
    Update admission data
    
    Args:
        db: Database connection
        admission_id: ID of the admission data document
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_admission_data_collection(db)
    
    # Ensure admission_id is ObjectId
    if isinstance(admission_id, str):
        admission_id = ObjectId(admission_id)
    
    # Set updated timestamp
    update_data['last_updated'] = datetime.utcnow()
    
    result = collection.update_one(
        {'_id': admission_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def delete_admission_data(db, admission_id):
    """
    Delete admission data document
    
    Args:
        db: Database connection
        admission_id: ID of the admission data document
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_admission_data_collection(db)
    
    # Ensure admission_id is ObjectId
    if isinstance(admission_id, str):
        admission_id = ObjectId(admission_id)
    
    result = collection.delete_one({'_id': admission_id})
    return result.deleted_count > 0

def delete_admission_data_for_college(db, college_id):
    """
    Delete admission data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_admission_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    result = collection.delete_one({'college_id': college_id})
    return result.deleted_count > 0

def search_admission_data(db, query_text, skip=0, limit=20):
    """
    Search admission data using text search
    
    Args:
        db: Database connection
        query_text: Text to search for
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of matching admission data documents
    """
    collection = get_admission_data_collection(db)
    
    # Perform text search
    cursor = collection.find(
        {'$text': {'$search': query_text}},
        {'score': {'$meta': 'textScore'}}
    ).sort([('score', {'$meta': 'textScore'})]).skip(skip).limit(limit)
    
    return list(cursor)

def get_colleges_with_admission_data(db, skip=0, limit=20):
    """
    Get colleges for which admission data is available
    
    Args:
        db: Database connection
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of college IDs with admission data
    """
    collection = get_admission_data_collection(db)
    
    # Project only college_id field
    cursor = collection.find({}, {'college_id': 1}).skip(skip).limit(limit)
    
    return [doc['college_id'] for doc in cursor]

def count_colleges_with_admission_data(db):
    """
    Count colleges with admission data
    
    Args:
        db: Database connection
        
    Returns:
        Count of colleges with admission data
    """
    collection = get_admission_data_collection(db)
    return collection.count_documents({})

def get_admission_data_stats(db):
    """
    Get statistics about admission data
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with statistics
    """
    collection = get_admission_data_collection(db)
    
    # Count documents
    total_colleges = collection.count_documents({})
    
    # Average number of courses per college
    pipeline = [
        {'$project': {'course_count': {'$size': {'$ifNull': ['$courses', []]}}}},
        {'$group': {'_id': None, 'avg_courses': {'$avg': '$course_count'}}}
    ]
    result = list(collection.aggregate(pipeline))
    avg_courses = result[0]['avg_courses'] if result else 0
    
    # Count colleges with hostel facilities
    has_hostel = collection.count_documents({'hostel_facilities.available': True})
    
    return {
        'total_colleges': total_colleges,
        'avg_courses_per_college': avg_courses,
        'colleges_with_hostel': has_hostel
    }

def get_course_list(db, college_id=None):
    """
    Get a list of all courses across colleges or for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college (optional)
        
    Returns:
        List of course names
    """
    collection = get_admission_data_collection(db)
    
    # Build pipeline
    pipeline = [
        {'$unwind': '$courses'},
        {'$group': {'_id': '$courses.name'}}
    ]
    
    if college_id:
        # Ensure college_id is ObjectId
        if isinstance(college_id, str):
            college_id = ObjectId(college_id)
        
        # Add match stage for specific college
        pipeline.insert(0, {'$match': {'college_id': college_id}})
    
    # Execute aggregation
    result = collection.aggregate(pipeline)
    
    return [doc['_id'] for doc in result if doc['_id']]