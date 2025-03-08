"""
College Data Crawler - Flask Web Application

This application provides an admin interface for managing the web crawler
that extracts structured data from college websites.
"""
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from bson import ObjectId, json_util
from models import init_db, close_db_connection
from services.auth_service import User, init_auth, login, register_user, create_admin_if_none_exists
from services.database_service import (
    get_colleges_paginated, import_colleges_from_file, export_colleges_to_file,
    get_database_statistics, get_college_filter_options, backup_database
)
from services.crawler_service import start_college_crawl, get_crawl_status, get_crawl_progress
from services.ai_service import get_model_status, load_ai_model, unload_ai_model
from workers import crawler_worker, ai_worker
from config import get_config

# Initialize Flask app
app = Flask(__name__)
# Add a context processor to make 'now' available to all templates

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Load configuration
config = get_config()
app.config.from_object(config)

# Initialize database
db = init_db(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message_category = 'info'

# Initialize authentication
init_auth(login_manager)

# Custom JSON encoder for MongoDB objects
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json_util.default(obj)

app.json_encoder = MongoJSONEncoder

# Initialize workers
# Initialize workers function
def init_workers():
    # Initialize crawler workers
    crawler_worker.init_workers()
    
    # Initialize AI workers
    ai_worker.init_workers()
    
    # Create admin if none exists
    create_admin_if_none_exists()

# Call the initialization function before running the app
with app.app_context():
    init_workers()

@app.teardown_appcontext
def teardown_db(exception):
    close_db_connection()

# ===== Authentication Routes =====

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email_or_username = request.form.get('email_or_username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = login(email_or_username, password)
        
        if user:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Login failed. Please check your credentials.', 'danger')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name', username)
        
        user = register_user(username, email, password, name)
        
        if user:
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Registration failed. Username or email already exists.', 'danger')
    
    return render_template('auth/register.html')

# ===== Main Routes =====

@app.route('/')
@login_required
def index():
    # Get dashboard statistics
    stats = get_database_statistics()
    
    # Get recent crawl jobs
    from models.crawl_job import get_recent_crawl_jobs
    recent_jobs = get_recent_crawl_jobs(db, skip=0, limit=5)
    
    # Get worker statuses
    crawler_status = crawler_worker.get_queue_status()
    ai_status = ai_worker.get_queue_status()
    
    return render_template(
        'dashboard/index.html',
        stats=stats,
        recent_jobs=recent_jobs,
        crawler_status=crawler_status,
        ai_status=ai_status
    )

# ===== College Management Routes =====

@app.route('/colleges')
@login_required
def colleges():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get filter parameters
    college_type = request.args.get('type')
    state = request.args.get('state')
    search = request.args.get('search')
    
    # Build filters
    filters = {}
    if college_type:
        filters['type'] = college_type
    if state:
        filters['state'] = state
    if search:
        filters['search'] = search
    
    # Get sort parameters
    sort_by = request.args.get('sort', 'name')
    sort_order = int(request.args.get('order', 1))
    
    # Get colleges
    result = get_colleges_paginated(page, per_page, filters, sort_by, sort_order)
    
    # Get filter options
    filter_options = get_college_filter_options()
    
    return render_template(
        'colleges/list.html',
        colleges=result['colleges'],
        pagination=result['pagination'],
        filters={
            'type': college_type,
            'state': state,
            'search': search
        },
        filter_options=filter_options,
        sort={'by': sort_by, 'order': sort_order}
    )

# @app.route('/colleges/add', methods=['GET', 'POST'])
# @login_required
# def add_college():
#     if not current_user.has_permission('add_college'):
#         flash('You do not have permission to add colleges.', 'danger')
#         return redirect(url_for('colleges'))
    
#     if request.method == 'POST':
#         # Get form data
#         name = request.form.get('name')
#         website = request.form.get('website')
#         college_type = request.form.get('type')
#         state = request.form.get('state')
        
#         # Validate required fields
#         if not name or not website:
#             flash('Name and website are required fields.', 'danger')
#             return redirect(url_for('add_college'))
        
#         # Add college to database
#         from models.college import create_college
#         college_id = create_college(db, name, website, college_type, state)
        
#         flash(f'College "{name}" added successfully.', 'success')
#         return redirect(url_for('college_details', college_id=college_id))
    
#     # Get filter options for dropdown
#     filter_options = get_college_filter_options()
    
#     return render_template(
#         'colleges/add.html',
#         filter_options=filter_options
#     )

@app.route('/colleges/<college_id>')
@login_required
def college_details(college_id):
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, college_id)
    
    if not college:
        flash('College not found.', 'danger')
        return redirect(url_for('colleges'))
    
    # Get crawl jobs for this college
    from models.crawl_job import get_crawl_jobs_for_college
    crawl_jobs = get_crawl_jobs_for_college(db, college_id, skip=0, limit=5)
    
    # Get extracted data details
    from models.admission_data import get_admission_data_by_college
    from models.placement_data import get_placement_data_by_college
    from models.internship_data import get_internship_data_by_college
    from models.raw_content import count_raw_content_for_college
    
    admission_data = get_admission_data_by_college(db, college_id)
    placement_data = get_placement_data_by_college(db, college_id)
    internship_data = get_internship_data_by_college(db, college_id)
    
    # Count raw content by type
    raw_content_counts = {
        'total': count_raw_content_for_college(db, college_id),
        'admission': count_raw_content_for_college(db, college_id, 'admission'),
        'placement': count_raw_content_for_college(db, college_id, 'placement'),
        'internship': count_raw_content_for_college(db, college_id, 'internship')
    }
    
    # Check if there's an active crawl job
    from models.crawl_job import get_active_crawl_job_for_college
    active_job = get_active_crawl_job_for_college(db, college_id)
    
    return render_template(
        'colleges/details.html',
        college=college,
        crawl_jobs=crawl_jobs,
        active_job=active_job,
        admission_data=admission_data,
        placement_data=placement_data,
        internship_data=internship_data,
        raw_content_counts=raw_content_counts
    )

@app.route('/colleges/<college_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_college(college_id):
    if not current_user.has_permission('edit_college'):
        flash('You do not have permission to edit colleges.', 'danger')
        return redirect(url_for('college_details', college_id=college_id))
    
    # Get college details
    from models.college import get_college_by_id, update_college
    college = get_college_by_id(db, college_id)
    
    if not college:
        flash('College not found.', 'danger')
        return redirect(url_for('colleges'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        website = request.form.get('website')
        college_type = request.form.get('type')
        state = request.form.get('state')
        status = request.form.get('status')
        
        # Validate required fields
        if not name or not website:
            flash('Name and website are required fields.', 'danger')
            return redirect(url_for('edit_college', college_id=college_id))
        
        # Update college
        update_data = {
            'name': name,
            'website': website,
            'type': college_type,
            'state': state,
            'status': status
        }
        
        # Update location if provided
        location = {}
        city = request.form.get('city')
        address = request.form.get('address')
        if city:
            location['city'] = city
        if address:
            location['address'] = address
        
        if location:
            update_data['location'] = location
        
        # Update contact info if provided
        contact_info = {}
        phone = request.form.get('phone')
        email = request.form.get('email')
        if phone:
            contact_info['phone'] = phone
        if email:
            contact_info['email'] = email
        
        if contact_info:
            update_data['contact_info'] = contact_info
        
        # Update college
        success = update_college(db, college_id, update_data)
        
        if success:
            flash('College updated successfully.', 'success')
        else:
            flash('Failed to update college.', 'danger')
        
        return redirect(url_for('college_details', college_id=college_id))
    
    # Get filter options for dropdown
    filter_options = get_college_filter_options()
    
    return render_template(
        'colleges/edit.html',
        college=college,
        filter_options=filter_options
    )

@app.route('/colleges/<college_id>/delete', methods=['POST'])
@login_required
def delete_college(college_id):
    if not current_user.has_permission('delete_college'):
        flash('You do not have permission to delete colleges.', 'danger')
        return redirect(url_for('college_details', college_id=college_id))
    
    # Delete college
    from models.college import delete_college
    success = delete_college(db, college_id)
    
    if success:
        # Also delete associated data
        from models.raw_content import delete_raw_content_for_college
        from models.admission_data import delete_admission_data_for_college
        from models.placement_data import delete_placement_data_for_college
        from models.internship_data import delete_internship_data_for_college
        
        delete_raw_content_for_college(db, college_id)
        delete_admission_data_for_college(db, college_id)
        delete_placement_data_for_college(db, college_id)
        delete_internship_data_for_college(db, college_id)
        
        flash('College and all associated data deleted successfully.', 'success')
    else:
        flash('Failed to delete college.', 'danger')
    
    return redirect(url_for('colleges'))

@app.route('/colleges/import', methods=['GET', 'POST'])
@login_required
def import_colleges():
    if not current_user.has_permission('add_college'):
        flash('You do not have permission to import colleges.', 'danger')
        return redirect(url_for('colleges'))
    
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected.', 'danger')
            return redirect(url_for('import_colleges'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('import_colleges'))
        
        # Check file extension
        allowed_extensions = config.ALLOWED_EXTENSIONS
        if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
            flash(f'Invalid file format. Allowed formats: {", ".join(allowed_extensions)}', 'danger')
            return redirect(url_for('import_colleges'))
        
        try:
            # Save file temporarily
            filename = secure_filename(file.filename)
            file_path = os.path.join(config.UPLOAD_FOLDER, filename)
            os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
            file.save(file_path)
            
            # Get default college type if provided
            college_type = request.form.get('type')
            
            # Import colleges
            success, message, count = import_colleges_from_file(file_path, college_type)
            
            # Delete temporary file
            os.remove(file_path)
            
            if success:
                flash(f'{message} ({count} colleges)', 'success')
            else:
                flash(message, 'danger')
            
            return redirect(url_for('colleges'))
            
        except Exception as e:
            flash(f'Error importing colleges: {str(e)}', 'danger')
            return redirect(url_for('import_colleges'))
    
    # Get filter options for dropdown
    filter_options = get_college_filter_options()
    
    return render_template(
        'colleges/import.html',
        filter_options=filter_options
    )

@app.route('/colleges/export', methods=['GET', 'POST'])
@login_required
def export_colleges():
    if request.method == 'POST':
        # Get format
        export_format = request.form.get('format', 'json')
        
        # Get selected colleges (if any)
        college_ids = request.form.getlist('college_ids')
        
        if not college_ids:
            flash('No colleges selected for export.', 'warning')
            return redirect(url_for('colleges'))
        
        # Create export directory
        export_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'colleges_export_{timestamp}.{export_format}'
        file_path = os.path.join(export_dir, filename)
        
        # Export colleges
        success, message, count = export_colleges_to_file(file_path, college_ids)
        
        if success:
            # Prepare file for download
            # TODO: Implement file download
            flash(f'{message}', 'success')
        else:
            flash(message, 'danger')
        
        return redirect(url_for('colleges'))
    
    # Get colleges for selection
    result = get_colleges_paginated(1, 1000)  # Get all colleges for selection
    
    return render_template(
        'colleges/export.html',
        colleges=result['colleges']
    )

# ===== Crawling Routes =====

@app.route('/start_crawl/<college_id>', methods=['POST'])
@login_required
def start_crawl(college_id):
    if not current_user.has_permission('start_crawl'):
        return jsonify({'status': 'error', 'message': 'You do not have permission to start crawls.'})
    
    # Check if there's already an active crawl job
    from models.crawl_job import get_active_crawl_job_for_college
    active_job = get_active_crawl_job_for_college(db, college_id)
    
    if active_job:
        return jsonify({
            'status': 'error',
            'message': f'A crawl job is already in progress for this college. Job ID: {active_job["_id"]}'
        })
    
    # Start crawl job
    job_id, message = start_college_crawl(college_id, current_user.id)
    
    # Enqueue job for processing
    crawler_worker.enqueue_job(job_id, college_id)
    
    return jsonify({
        'status': 'success',
        'message': message,
        'job_id': str(job_id)
    })

@app.route('/crawl_status/<job_id>')
@login_required
def crawl_status_route(job_id):
    # Get crawl job status
    job = get_crawl_status(job_id)
    
    if not job:
        return jsonify({'status': 'error', 'message': 'Job not found'})
    
    # Convert job to dictionary with string IDs
    job_dict = json_util.loads(json_util.dumps(job))
    
    # Add progress info for running jobs
    if job.get('status') == 'running':
        job_dict['progress'] = get_crawl_progress(job_id)
    
    return jsonify(job_dict)

@app.route('/crawl_jobs')
@login_required
def crawl_jobs():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get filter parameters
    status = request.args.get('status')
    
    # Get crawl jobs
    from models.crawl_job import get_recent_crawl_jobs, count_crawl_jobs
    
    jobs = get_recent_crawl_jobs(db, status, (page - 1) * per_page, per_page)
    total = count_crawl_jobs(db, status)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Get college details for each job
    from models.college import get_college_by_id
    
    for job in jobs:
        job['college'] = get_college_by_id(db, job['college_id'])
    
    return render_template(
        'crawling/jobs.html',
        jobs=jobs,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        },
        status_filter=status
    )

@app.route('/crawl_jobs/<job_id>')
@login_required
def crawl_job_details(job_id):
    # Get crawl job details
    job = get_crawl_status(job_id)
    
    if not job:
        flash('Crawl job not found.', 'danger')
        return redirect(url_for('crawl_jobs'))
    
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, job['college_id'])
    
    # Get extracted content
    from models.raw_content import get_raw_content_for_college
    raw_content = get_raw_content_for_college(
        db, job['college_id'], processed=None, skip=0, limit=100
    )
    
    # Group content by type
    content_by_type = {
        'admission': [],
        'placement': [],
        'internship': [],
        'general': []
    }
    
    for content in raw_content:
        content_type = content.get('content_type', 'general')
        content_by_type[content_type].append(content)
    
    return render_template(
        'crawling/job_details.html',
        job=job,
        college=college,
        content_by_type=content_by_type
    )

# ===== AI Processing Routes =====

@app.route('/ai/status')
@login_required
def ai_status():
    # Get AI model status
    model_status = get_model_status()
    
    # Get AI processing jobs
    from models.ai_processing_job import count_ai_processing_jobs, get_ai_processing_stats
    
    queued_jobs = count_ai_processing_jobs(db, 'queued')
    running_jobs = count_ai_processing_jobs(db, 'running')
    completed_jobs = count_ai_processing_jobs(db, 'completed')
    failed_jobs = count_ai_processing_jobs(db, 'failed')
    
    # Get AI queue status
    queue_status = ai_worker.get_queue_status()
    
    # Get AI processing stats
    stats = get_ai_processing_stats(db)
    
    return render_template(
        'ai/status.html',
        model_status=model_status,
        job_counts={
            'queued': queued_jobs,
            'running': running_jobs,
            'completed': completed_jobs,
            'failed': failed_jobs
        },
        queue_status=queue_status,
        stats=stats
    )

@app.route('/ai/load_model', methods=['POST'])
@login_required
def load_model():
    if not current_user.has_permission('configure_ai'):
        return jsonify({'status': 'error', 'message': 'You do not have permission to configure AI.'})
    
    # Load AI model
    success, message = load_ai_model()
    
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@app.route('/ai/unload_model', methods=['POST'])
@login_required
def unload_model():
    if not current_user.has_permission('configure_ai'):
        return jsonify({'status': 'error', 'message': 'You do not have permission to configure AI.'})
    
    # Unload AI model
    success, message = unload_ai_model()
    
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@app.route('/ai/jobs')
@login_required
def ai_jobs():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get filter parameters
    status = request.args.get('status')
    content_type = request.args.get('content_type')
    
    # Get AI jobs
    from models.ai_processing_job import get_queued_ai_processing_jobs, count_ai_processing_jobs
    
    # For simplicity, use the same function but limit the results
    jobs = get_queued_ai_processing_jobs(db, content_type, 100)
    
    # Filter by status if provided
    if status:
        jobs = [job for job in jobs if job['status'] == status]
    
    # Apply pagination
    total = len(jobs)
    start = (page - 1) * per_page
    end = start + per_page
    jobs = jobs[start:end]
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Get college details for each job
    from models.college import get_college_by_id
    
    for job in jobs:
        job['college'] = get_college_by_id(db, job['college_id'])
    
    return render_template(
        'ai/jobs.html',
        jobs=jobs,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        },
        status_filter=status,
        content_type_filter=content_type
    )

# ===== Data Exploration Routes =====

@app.route('/explore/admission')
@login_required
def explore_admission():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get colleges with admission data
    from models.admission_data import get_colleges_with_admission_data, count_colleges_with_admission_data
    
    college_ids = get_colleges_with_admission_data(db, (page - 1) * per_page, per_page)
    total = count_colleges_with_admission_data(db)
    
    # Get college details for each ID
    from models.college import get_college_by_id
    
    colleges = []
    for college_id in college_ids:
        college = get_college_by_id(db, college_id)
        if college:
            colleges.append(college)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return render_template(
        'explore/admission.html',
        colleges=colleges,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    )

@app.route('/explore/admission/<college_id>')
@login_required
def explore_admission_details(college_id):
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, college_id)
    
    if not college:
        flash('College not found.', 'danger')
        return redirect(url_for('explore_admission'))
    
    # Get admission data
    from models.admission_data import get_admission_data_by_college
    admission_data = get_admission_data_by_college(db, college_id)
    
    if not admission_data:
        flash('No admission data found for this college.', 'warning')
        return redirect(url_for('explore_admission'))
    
    return render_template(
        'explore/admission_details.html',
        college=college,
        admission_data=admission_data
    )

@app.route('/explore/placement')
@login_required
def explore_placement():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get colleges with placement data
    from models.placement_data import get_colleges_with_placement_data, count_colleges_with_placement_data
    
    college_ids = get_colleges_with_placement_data(db, (page - 1) * per_page, per_page)
    total = count_colleges_with_placement_data(db)
    
    # Get college details for each ID
    from models.college import get_college_by_id
    
    colleges = []
    for college_id in college_ids:
        college = get_college_by_id(db, college_id)
        if college:
            colleges.append(college)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return render_template(
        'explore/placement.html',
        colleges=colleges,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    )

@app.route('/explore/placement/<college_id>')
@login_required
def explore_placement_details(college_id):
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, college_id)
    
    if not college:
        flash('College not found.', 'danger')
        return redirect(url_for('explore_placement'))
    
    # Get placement data
    from models.placement_data import get_placement_data_by_college
    placement_data = get_placement_data_by_college(db, college_id)
    
    if not placement_data:
        flash('No placement data found for this college.', 'warning')
        return redirect(url_for('explore_placement'))
    
    return render_template(
        'explore/placement_details.html',
        college=college,
        placement_data=placement_data
    )

@app.route('/explore/internship')
@login_required
def explore_internship():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get colleges with internship data
    from models.internship_data import get_colleges_with_internship_data, count_colleges_with_internship_data
    
    college_ids = get_colleges_with_internship_data(db, (page - 1) * per_page, per_page)
    total = count_colleges_with_internship_data(db)
    
    # Get college details for each ID
    from models.college import get_college_by_id
    
    colleges = []
    for college_id in college_ids:
        college = get_college_by_id(db, college_id)
        if college:
            colleges.append(college)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return render_template(
        'explore/internship.html',
        colleges=colleges,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    )

@app.route('/explore/internship/<college_id>')
@login_required
def explore_internship_details(college_id):
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, college_id)
    
    if not college:
        flash('College not found.', 'danger')
        return redirect(url_for('explore_internship'))
    
    # Get internship data
    from models.internship_data import get_internship_data_by_college
    internship_data = get_internship_data_by_college(db, college_id)
    
    if not internship_data:
        flash('No internship data found for this college.', 'warning')
        return redirect(url_for('explore_internship'))
    
    return render_template(
        'explore/internship_details.html',
        college=college,
        internship_data=internship_data
    )

# ===== Admin Routes =====

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.has_permission('manage_users'):
        flash('You do not have permission to manage users.', 'danger')
        return redirect(url_for('index'))
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get users
    from services.auth_service import get_all_users
    users, total = get_all_users(page, per_page)
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    return render_template(
        'admin/users.html',
        users=users,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    )

@app.route('/admin/users/<user_id>/toggle_status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if not current_user.has_permission('manage_users'):
        return jsonify({'status': 'error', 'message': 'You do not have permission to manage users.'})
    
    # Get active status from form
    active = request.form.get('active') == 'true'
    
    # Toggle user status
    from services.auth_service import toggle_user_status
    success = toggle_user_status(current_user, user_id, active)
    
    if success:
        return jsonify({'status': 'success', 'message': f'User {"activated" if active else "deactivated"} successfully.'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update user status.'})

@app.route('/admin/users/<user_id>/change_role', methods=['POST'])
@login_required
def change_user_role(user_id):
    if not current_user.has_permission('manage_users'):
        return jsonify({'status': 'error', 'message': 'You do not have permission to manage users.'})
    
    # Get new role from form
    new_role = request.form.get('role')
    
    # Change user role
    from services.auth_service import change_user_role
    success = change_user_role(current_user, user_id, new_role)
    
    if success:
        return jsonify({'status': 'success', 'message': f'User role changed to {new_role} successfully.'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to change user role.'})

@app.route('/admin/backup', methods=['GET', 'POST'])
@login_required
def admin_backup():
    if not current_user.has_permission('manage_users'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Get backup directory from form
        backup_dir = request.form.get('backup_dir', 'backups')
        
        # Create backup
        success, message = backup_database(backup_dir)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        
        return redirect(url_for('admin_backup'))
    
    # Get database stats
    from services.database_service import get_database_collection_stats
    db_stats = get_database_collection_stats()
    
    return render_template(
        'admin/backup.html',
        db_stats=db_stats
    )

# ===== API Routes =====

@app.route('/api/colleges')
@login_required
def api_colleges():
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Get filter parameters
    college_type = request.args.get('type')
    state = request.args.get('state')
    search = request.args.get('search')
    
    # Build filters
    filters = {}
    if college_type:
        filters['type'] = college_type
    if state:
        filters['state'] = state
    if search:
        filters['search'] = search
    
    # Get sort parameters
    sort_by = request.args.get('sort', 'name')
    sort_order = int(request.args.get('order', 1))
    
    # Get colleges
    result = get_colleges_paginated(page, per_page, filters, sort_by, sort_order)
    
    return jsonify(result)

@app.route('/api/college/<college_id>')
@login_required
def api_college_details(college_id):
    # Get college details
    from models.college import get_college_by_id
    college = get_college_by_id(db, college_id)
    
    if not college:
        return jsonify({'status': 'error', 'message': 'College not found'})
    
    # Convert to dictionary with string IDs
    college_dict = json_util.loads(json_util.dumps(college))
    
    return jsonify(college_dict)

@app.route('/api/crawl_status/<college_id>')
@login_required
def api_crawl_status(college_id):
    # Get active crawl job for college
    from models.crawl_job import get_active_crawl_job_for_college
    job = get_active_crawl_job_for_college(db, college_id)
    
    if not job:
        return jsonify({'status': 'not_started'})
    
    # Get job status
    status = job['status']
    
    # Get progress for running jobs
    progress = None
    if status == 'running':
        progress = get_crawl_progress(job['_id'])
    
    return jsonify({
        'status': status,
        'job_id': str(job['_id']),
        'progress': progress
    })

@app.route('/api/stats')
@login_required
def api_stats():
    # Get database statistics
    stats = get_database_statistics()
    
    return jsonify(stats)

# ===== Utility Routes =====

@app.template_filter('format_date')
def format_date(value, format='%Y-%m-%d %H:%M:%S'):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    
    if value:
        return value.strftime(format)
    return ''

@app.template_filter('format_duration')
def format_duration(seconds):
    if seconds is None:
        return ''
    
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f'{int(hours)}h {int(minutes)}m {int(seconds)}s'
    elif minutes > 0:
        return f'{int(minutes)}m {int(seconds)}s'
    else:
        return f'{int(seconds)}s'


@app.route('/colleges/add', methods=['GET'])
@login_required
def add_college():
    # List of all Indian states and UTs
    states = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", 
        "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", 
        "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
        "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
        "Uttarakhand", "West Bengal",
        # Union Territories
        "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", 
        "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
    ]
    
    # College types
    college_types = ["Engineering", "Medical", "Arts & Science", "Law", "Business", "Pharmacy", 
                    "Agriculture", "Architecture", "Dental", "Nursing", "Education", "Other"]
    
    filter_options = {
        'states': states,
        'types': college_types
    }
    
    return render_template('colleges/add.html', filter_options=filter_options)


@app.route('/colleges/add', methods=['POST'])
@login_required
def add_college_submit():
    # Get form data
    name = request.form.get('name')
    website = request.form.get('website')
    college_type = request.form.get('type')
    state = request.form.get('state')
    city = request.form.get('city', '')
    address = request.form.get('address', '')
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    
    # Validate required fields
    if not all([name, website, college_type, state]):
        flash('Please fill all required fields', 'danger')
        return redirect(url_for('add_college'))
    
    # Create college document
    college = {
        'name': name,
        'website': website,
        'type': college_type,
        'state': state,
        'location': {
            'city': city,
            'address': address
        },
        'contact_info': {
            'phone': phone,
            'email': email
        },
        'status': 'active',
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }
    
    # Insert into database
    result = db.colleges.insert_one(college)
    
    if result.inserted_id:
        flash('College added successfully', 'success')
        return redirect(url_for('college_details', college_id=result.inserted_id))
    else:
        flash('Failed to add college', 'danger')
        return redirect(url_for('add_college'))





# Run the application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)