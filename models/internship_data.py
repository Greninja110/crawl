"""
Internship data model for storing structured internship information
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, TEXT

def create_indexes(db):
    """Create indexes for the internship_data collection"""
    db.internship_data.create_index([('college_id', ASCENDING)])
    db.internship_data.create_index([('academic_year', ASCENDING)])
    db.internship_data.create_index([('last_updated', DESCENDING)])
    db.internship_data.create_index([('internship_companies.name', TEXT)])

def get_internship_data_collection(db):
    """Get the internship_data collection"""
    return db.internship_data

def store_internship_data(db, college_id, source_urls, academic_year, overall_statistics=None,
                         department_statistics=None, internship_companies=None):
    """
    Store structured internship data
    
    Args:
        db: Database connection
        college_id: ID of the college
        source_urls: List of URLs from which data was extracted
        academic_year: Academic year of the internship data
        overall_statistics: Dictionary with overall internship statistics
        department_statistics: List of department-wise statistics
        internship_companies: List of company information
        
    Returns:
        Inserted document ID
    """
    collection = get_internship_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Check if internship data already exists for this college and academic year
    existing_data = collection.find_one({
        'college_id': college_id,
        'academic_year': academic_year
    })
    
    if existing_data:
        # Update existing document
        update_data = {
            'source_urls': list(set(existing_data.get('source_urls', []) + source_urls)),
            'last_updated': datetime.utcnow()
        }
        
        # Update overall statistics if provided
        if overall_statistics:
            # Merge with existing statistics
            existing_stats = existing_data.get('overall_statistics', {})
            merged_stats = existing_stats.copy()
            merged_stats.update(overall_statistics)
            update_data['overall_statistics'] = merged_stats
        
        # Update department statistics if provided
        if department_statistics:
            # Create a dictionary of department stats by department name
            existing_depts = existing_data.get('department_statistics', [])
            dept_dict = {
                dept.get('department', ''): dept 
                for dept in existing_depts 
                if dept.get('department')
            }
            
            for dept in department_statistics:
                dept_name = dept.get('department', '')
                if dept_name in dept_dict:
                    # Update existing department stats
                    merged_dept = dept_dict[dept_name].copy()
                    merged_dept.update({k: v for k, v in dept.items() if v})
                    dept_dict[dept_name] = merged_dept
                else:
                    # Add new department stats
                    dept_dict[dept_name] = dept
            
            update_data['department_statistics'] = list(dept_dict.values())
        
        # Update internship companies if provided
        if internship_companies:
            # Create a dictionary of companies by name
            existing_companies = existing_data.get('internship_companies', [])
            company_dict = {
                company.get('name', ''): company 
                for company in existing_companies 
                if company.get('name')
            }
            
            for company in internship_companies:
                company_name = company.get('name', '')
                if company_name in company_dict:
                    # Update existing company info
                    merged_company = company_dict[company_name].copy()
                    merged_company.update({k: v for k, v in company.items() if v})
                    company_dict[company_name] = merged_company
                else:
                    # Add new company
                    company_dict[company_name] = company
            
            update_data['internship_companies'] = list(company_dict.values())
        
        # Update document
        collection.update_one(
            {'_id': existing_data['_id']},
            {'$set': update_data}
        )
        
        return existing_data['_id']
    else:
        # Create new document
        internship_doc = {
            'college_id': college_id,
            'source_urls': source_urls,
            'academic_year': academic_year,
            'overall_statistics': overall_statistics or {},
            'department_statistics': department_statistics or [],
            'internship_companies': internship_companies or [],
            'created_at': datetime.utcnow(),
            'last_updated': datetime.utcnow()
        }
        
        result = collection.insert_one(internship_doc)
        return result.inserted_id

def get_internship_data_by_college(db, college_id, academic_year=None):
    """
    Get internship data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        academic_year: Academic year (optional)
        
    Returns:
        List of internship data documents or single document if academic_year specified
    """
    collection = get_internship_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    if academic_year:
        query['academic_year'] = academic_year
        return collection.find_one(query)
    
    # Sort by academic year (newest first)
    cursor = collection.find(query).sort([('academic_year', DESCENDING)])
    return list(cursor)

def get_internship_data_by_id(db, internship_id):
    """
    Get internship data by ID
    
    Args:
        db: Database connection
        internship_id: ID of the internship data document
        
    Returns:
        Internship data document or None
    """
    collection = get_internship_data_collection(db)
    
    # Ensure internship_id is ObjectId
    if isinstance(internship_id, str):
        internship_id = ObjectId(internship_id)
    
    return collection.find_one({'_id': internship_id})

def update_internship_data(db, internship_id, update_data):
    """
    Update internship data
    
    Args:
        db: Database connection
        internship_id: ID of the internship data document
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_internship_data_collection(db)
    
    # Ensure internship_id is ObjectId
    if isinstance(internship_id, str):
        internship_id = ObjectId(internship_id)
    
    # Set updated timestamp
    update_data['last_updated'] = datetime.utcnow()
    
    result = collection.update_one(
        {'_id': internship_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def delete_internship_data(db, internship_id):
    """
    Delete internship data document
    
    Args:
        db: Database connection
        internship_id: ID of the internship data document
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_internship_data_collection(db)
    
    # Ensure internship_id is ObjectId
    if isinstance(internship_id, str):
        internship_id = ObjectId(internship_id)
    
    result = collection.delete_one({'_id': internship_id})
    return result.deleted_count > 0

def delete_internship_data_for_college(db, college_id, academic_year=None):
    """
    Delete internship data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        academic_year: Academic year (optional)
        
    Returns:
        Number of documents deleted
    """
    collection = get_internship_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    if academic_year:
        query['academic_year'] = academic_year
    
    result = collection.delete_many(query)
    return result.deleted_count

def search_company_internships(db, company_name, skip=0, limit=20):
    """
    Search for colleges where a specific company offered internships
    
    Args:
        db: Database connection
        company_name: Name of the company
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of internship data documents
    """
    collection = get_internship_data_collection(db)
    
    # Use text search on company name
    cursor = collection.find(
        {'$text': {'$search': company_name}},
        {'score': {'$meta': 'textScore'}}
    ).sort([('score', {'$meta': 'textScore'})]).skip(skip).limit(limit)
    
    return list(cursor)

def get_colleges_with_internship_data(db, skip=0, limit=20):
    """
    Get colleges for which internship data is available
    
    Args:
        db: Database connection
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of college IDs with internship data
    """
    collection = get_internship_data_collection(db)
    
    # Get distinct college IDs
    pipeline = [
        {'$group': {'_id': '$college_id'}},
        {'$skip': skip},
        {'$limit': limit}
    ]
    
    result = collection.aggregate(pipeline)
    return [doc['_id'] for doc in result]

def count_colleges_with_internship_data(db):
    """
    Count colleges with internship data
    
    Args:
        db: Database connection
        
    Returns:
        Count of colleges with internship data
    """
    collection = get_internship_data_collection(db)
    
    # Count distinct college IDs
    pipeline = [
        {'$group': {'_id': '$college_id'}},
        {'$count': 'count'}
    ]
    
    result = list(collection.aggregate(pipeline))
    return result[0]['count'] if result else 0

def get_internship_stats_by_year(db, academic_years=None, top_n=5):
    """
    Get internship statistics grouped by academic year
    
    Args:
        db: Database connection
        academic_years: List of academic years to include (optional)
        top_n: Number of top companies to include
        
    Returns:
        Dictionary with internship statistics by year
    """
    collection = get_internship_data_collection(db)
    
    # Build match stage
    match_stage = {}
    if academic_years:
        match_stage['academic_year'] = {'$in': academic_years}
    
    # Aggregate pipeline
    pipeline = [
        {'$match': match_stage} if match_stage else {'$match': {}},
        {'$group': {
            '_id': '$academic_year',
            'avg_internship_participation': {'$avg': '$overall_statistics.participation'},
            'avg_stipend': {'$avg': '$overall_statistics.avg_stipend'},
            'college_count': {'$sum': 1},
            'companies': {'$push': '$internship_companies'}
        }},
        {'$sort': {'_id': 1}}
    ]
    
    result = collection.aggregate(pipeline)
    
    # Process results
    stats_by_year = {}
    for item in result:
        year = item['_id']
        
        # Flatten companies lists
        all_companies = []
        for company_list in item['companies']:
            all_companies.extend(company_list)
        
        # Count companies by name
        company_counts = {}
        for company in all_companies:
            name = company.get('name', '')
            if name:
                company_counts[name] = company_counts.get(name, 0) + 1
        
        # Get top N companies
        top_companies = sorted(
            [{'name': name, 'count': count} for name, count in company_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:top_n]
        
        stats_by_year[year] = {
            'avg_internship_participation': item['avg_internship_participation'],
            'avg_stipend': item['avg_stipend'],
            'college_count': item['college_count'],
            'top_companies': top_companies
        }
    
    return stats_by_year

def get_top_internship_companies(db, limit=20):
    """
    Get the most frequently occurring internship companies
    
    Args:
        db: Database connection
        limit: Maximum number of companies to return
        
    Returns:
        List of company names with occurrence count
    """
    collection = get_internship_data_collection(db)
    
    # Aggregate pipeline
    pipeline = [
        {'$unwind': '$internship_companies'},
        {'$group': {
            '_id': '$internship_companies.name',
            'count': {'$sum': 1},
            'avg_stipend': {'$avg': '$internship_companies.stipend'}
        }},
        {'$match': {'_id': {'$ne': None, '$ne': ''}}},
        {'$sort': {'count': -1}},
        {'$limit': limit}
    ]
    
    result = collection.aggregate(pipeline)
    
    return [{'name': item['_id'], 'count': item['count'], 'avg_stipend': item['avg_stipend']} 
            for item in result]

def get_department_internship_performance(db):
    """
    Get internship performance by department
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with department statistics
    """
    collection = get_internship_data_collection(db)
    
    # Aggregate pipeline
    pipeline = [
        {'$unwind': '$department_statistics'},
        {'$group': {
            '_id': '$department_statistics.department',
            'avg_participation': {'$avg': '$department_statistics.participation'},
            'avg_stipend': {'$avg': '$department_statistics.avg_stipend'},
            'college_count': {'$sum': 1}
        }},
        {'$match': {'_id': {'$ne': None, '$ne': ''}}},
        {'$sort': {'avg_participation': -1}}
    ]
    
    result = collection.aggregate(pipeline)
    
    return {item['_id']: {
        'avg_participation': item['avg_participation'],
        'avg_stipend': item['avg_stipend'],
        'college_count': item['college_count']
    } for item in result}