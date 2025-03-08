"""
Placement data model for storing structured placement information
"""
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, TEXT

def create_indexes(db):
    """Create indexes for the placement_data collection"""
    db.placement_data.create_index([('college_id', ASCENDING)])
    db.placement_data.create_index([('academic_year', ASCENDING)])
    db.placement_data.create_index([('last_updated', DESCENDING)])
    db.placement_data.create_index([('recruiting_companies.name', TEXT)])

def get_placement_data_collection(db):
    """Get the placement_data collection"""
    return db.placement_data

def store_placement_data(db, college_id, source_urls, academic_year, overall_statistics=None,
                        department_statistics=None, recruiting_companies=None, placement_charts=None):
    """
    Store structured placement data
    
    Args:
        db: Database connection
        college_id: ID of the college
        source_urls: List of URLs from which data was extracted
        academic_year: Academic year of the placement data
        overall_statistics: Dictionary with overall placement statistics
        department_statistics: List of department-wise statistics
        recruiting_companies: List of company information
        placement_charts: List of charts data
        
    Returns:
        Inserted document ID
    """
    collection = get_placement_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Check if placement data already exists for this college and academic year
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
        
        # Update recruiting companies if provided
        if recruiting_companies:
            # Create a dictionary of companies by name
            existing_companies = existing_data.get('recruiting_companies', [])
            company_dict = {
                company.get('name', ''): company 
                for company in existing_companies 
                if company.get('name')
            }
            
            for company in recruiting_companies:
                company_name = company.get('name', '')
                if company_name in company_dict:
                    # Update existing company info
                    merged_company = company_dict[company_name].copy()
                    merged_company.update({k: v for k, v in company.items() if v})
                    company_dict[company_name] = merged_company
                else:
                    # Add new company
                    company_dict[company_name] = company
            
            update_data['recruiting_companies'] = list(company_dict.values())
        
        # Update placement charts if provided
        if placement_charts:
            update_data['placement_charts'] = placement_charts
        
        # Update document
        collection.update_one(
            {'_id': existing_data['_id']},
            {'$set': update_data}
        )
        
        return existing_data['_id']
    else:
        # Create new document
        placement_doc = {
            'college_id': college_id,
            'source_urls': source_urls,
            'academic_year': academic_year,
            'overall_statistics': overall_statistics or {},
            'department_statistics': department_statistics or [],
            'recruiting_companies': recruiting_companies or [],
            'placement_charts': placement_charts or [],
            'created_at': datetime.utcnow(),
            'last_updated': datetime.utcnow()
        }
        
        result = collection.insert_one(placement_doc)
        return result.inserted_id

def get_placement_data_by_college(db, college_id, academic_year=None):
    """
    Get placement data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        academic_year: Academic year (optional)
        
    Returns:
        List of placement data documents or single document if academic_year specified
    """
    collection = get_placement_data_collection(db)
    
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

def get_placement_data_by_id(db, placement_id):
    """
    Get placement data by ID
    
    Args:
        db: Database connection
        placement_id: ID of the placement data document
        
    Returns:
        Placement data document or None
    """
    collection = get_placement_data_collection(db)
    
    # Ensure placement_id is ObjectId
    if isinstance(placement_id, str):
        placement_id = ObjectId(placement_id)
    
    return collection.find_one({'_id': placement_id})

def update_placement_data(db, placement_id, update_data):
    """
    Update placement data
    
    Args:
        db: Database connection
        placement_id: ID of the placement data document
        update_data: Dictionary of fields to update
        
    Returns:
        True if update successful, False otherwise
    """
    collection = get_placement_data_collection(db)
    
    # Ensure placement_id is ObjectId
    if isinstance(placement_id, str):
        placement_id = ObjectId(placement_id)
    
    # Set updated timestamp
    update_data['last_updated'] = datetime.utcnow()
    
    result = collection.update_one(
        {'_id': placement_id},
        {'$set': update_data}
    )
    
    return result.modified_count > 0

def delete_placement_data(db, placement_id):
    """
    Delete placement data document
    
    Args:
        db: Database connection
        placement_id: ID of the placement data document
        
    Returns:
        True if deletion successful, False otherwise
    """
    collection = get_placement_data_collection(db)
    
    # Ensure placement_id is ObjectId
    if isinstance(placement_id, str):
        placement_id = ObjectId(placement_id)
    
    result = collection.delete_one({'_id': placement_id})
    return result.deleted_count > 0

def delete_placement_data_for_college(db, college_id, academic_year=None):
    """
    Delete placement data for a specific college
    
    Args:
        db: Database connection
        college_id: ID of the college
        academic_year: Academic year (optional)
        
    Returns:
        Number of documents deleted
    """
    collection = get_placement_data_collection(db)
    
    # Ensure college_id is ObjectId
    if isinstance(college_id, str):
        college_id = ObjectId(college_id)
    
    # Build query
    query = {'college_id': college_id}
    if academic_year:
        query['academic_year'] = academic_year
    
    result = collection.delete_many(query)
    return result.deleted_count

def search_company_placements(db, company_name, skip=0, limit=20):
    """
    Search for colleges where a specific company recruited
    
    Args:
        db: Database connection
        company_name: Name of the company
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of placement data documents
    """
    collection = get_placement_data_collection(db)
    
    # Use text search on company name
    cursor = collection.find(
        {'$text': {'$search': company_name}},
        {'score': {'$meta': 'textScore'}}
    ).sort([('score', {'$meta': 'textScore'})]).skip(skip).limit(limit)
    
    return list(cursor)

def get_colleges_with_placement_data(db, skip=0, limit=20):
    """
    Get colleges for which placement data is available
    
    Args:
        db: Database connection
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of college IDs with placement data
    """
    collection = get_placement_data_collection(db)
    
    # Get distinct college IDs
    pipeline = [
        {'$group': {'_id': '$college_id'}},
        {'$skip': skip},
        {'$limit': limit}
    ]
    
    result = collection.aggregate(pipeline)
    return [doc['_id'] for doc in result]

def count_colleges_with_placement_data(db):
    """
    Count colleges with placement data
    
    Args:
        db: Database connection
        
    Returns:
        Count of colleges with placement data
    """
    collection = get_placement_data_collection(db)
    
    # Count distinct college IDs
    pipeline = [
        {'$group': {'_id': '$college_id'}},
        {'$count': 'count'}
    ]
    
    result = list(collection.aggregate(pipeline))
    return result[0]['count'] if result else 0

def get_placement_stats_by_year(db, academic_years=None, top_n=5):
    """
    Get placement statistics grouped by academic year
    
    Args:
        db: Database connection
        academic_years: List of academic years to include (optional)
        top_n: Number of top companies to include
        
    Returns:
        Dictionary with placement statistics by year
    """
    collection = get_placement_data_collection(db)
    
    # Build match stage
    match_stage = {}
    if academic_years:
        match_stage['academic_year'] = {'$in': academic_years}
    
    # Aggregate pipeline
    pipeline = [
        {'$match': match_stage} if match_stage else {'$match': {}},
        {'$group': {
            '_id': '$academic_year',
            'avg_placement_percentage': {'$avg': '$overall_statistics.placement_percentage'},
            'avg_package': {'$avg': '$overall_statistics.avg_package'},
            'college_count': {'$sum': 1},
            'companies': {'$push': '$recruiting_companies'}
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
            'avg_placement_percentage': item['avg_placement_percentage'],
            'avg_package': item['avg_package'],
            'college_count': item['college_count'],
            'top_companies': top_companies
        }
    
    return stats_by_year

def get_top_companies(db, limit=20):
    """
    Get the most frequently occurring recruiting companies
    
    Args:
        db: Database connection
        limit: Maximum number of companies to return
        
    Returns:
        List of company names with occurrence count
    """
    collection = get_placement_data_collection(db)
    
    # Aggregate pipeline
    pipeline = [
        {'$unwind': '$recruiting_companies'},
        {'$group': {
            '_id': '$recruiting_companies.name',
            'count': {'$sum': 1},
            'avg_package': {'$avg': '$recruiting_companies.package_offered'}
        }},
        {'$match': {'_id': {'$ne': None, '$ne': ''}}},
        {'$sort': {'count': -1}},
        {'$limit': limit}
    ]
    
    result = collection.aggregate(pipeline)
    
    return [{'name': item['_id'], 'count': item['count'], 'avg_package': item['avg_package']} 
            for item in result]

def get_department_performance(db):
    """
    Get placement performance by department
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with department statistics
    """
    collection = get_placement_data_collection(db)
    
    # Aggregate pipeline
    pipeline = [
        {'$unwind': '$department_statistics'},
        {'$group': {
            '_id': '$department_statistics.department',
            'avg_placement_percentage': {'$avg': '$department_statistics.statistics.placement_percentage'},
            'avg_package': {'$avg': '$department_statistics.statistics.avg_package'},
            'college_count': {'$sum': 1}
        }},
        {'$match': {'_id': {'$ne': None, '$ne': ''}}},
        {'$sort': {'avg_placement_percentage': -1}}
    ]
    
    result = collection.aggregate(pipeline)
    
    return {item['_id']: {
        'avg_placement_percentage': item['avg_placement_percentage'],
        'avg_package': item['avg_package'],
        'college_count': item['college_count']
    } for item in result}