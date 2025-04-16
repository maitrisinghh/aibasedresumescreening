from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from models import db, Candidate, JobPosting, Application, AnalyticsReport
from ai_processor import ResumeProcessor, JobMatcher
from data_processor import DataProcessor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Add min function to template context
@app.template_filter('min')
def min_filter(a, b):
    return min(a, b)

# Add intersect filter for set operations
@app.template_filter('intersect')
def intersect_filter(a, b):
    """Return the intersection of two lists."""
    return list(set(a) & set(b))

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resume_screening.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)

# Ensure instance directory exists
os.makedirs(app.instance_path, exist_ok=True)

# Initialize AI processors
resume_processor = ResumeProcessor()
job_matcher = JobMatcher()
data_processor = DataProcessor(os.path.join(app.instance_path, 'datasheet.csv'))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Here you would typically validate the login credentials
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Get stats
    total_candidates = Candidate.query.count()
    new_applications = Application.query.filter_by(status='pending').count()
    active_jobs = JobPosting.query.filter_by(status='active').count()
    successful_matches = Application.query.filter_by(status='accepted').count()
    
    # Get recent applications with candidate and job details
    recent_applications = db.session.query(
        Application, Candidate, JobPosting
    ).join(
        Candidate
    ).join(
        JobPosting
    ).order_by(
        Application.created_at.desc()
    ).limit(5).all()
    
    # Get skills distribution
    candidates = Candidate.query.all()
    skills_count = {}
    for candidate in candidates:
        for skill in candidate.skills:
            skills_count[skill] = skills_count.get(skill, 0) + 1
    
    # Convert to percentage and sort
    total_candidates = len(candidates)
    skills_distribution = {
        skill: round((count / total_candidates) * 100, 1)
        for skill, count in skills_count.items()
    }
    top_skills = dict(sorted(skills_distribution.items(), 
                           key=lambda x: x[1], reverse=True)[:4])

    return render_template('dashboard.html',
                         stats={
                             'total_candidates': total_candidates,
                             'new_applications': new_applications,
                             'active_jobs': active_jobs,
                             'successful_matches': successful_matches
                         },
                         recent_applications=recent_applications,
                         top_skills=top_skills)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['resume']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        # Validate required fields
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        if not all([name, email, phone]):
            flash('Please fill in all required fields', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                # Save the file
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Process the resume
                analysis = resume_processor.analyze_resume_sync(filepath)
                print(analysis)
                if analysis:
                    # Create new candidate
                    candidate = Candidate(
                        name=name,
                        email=email,
                        phone=phone,
                        resume_path=filepath,
                        skills=analysis.get('skills', []),
                        experience=analysis.get('experience', []),
                        education=analysis.get('education', [])
                    )
                    print(candidate.email)
                    # Check if email already exists
                    existing_candidate = Candidate.query.filter_by(email=email).first()
                    if existing_candidate:
                        flash('A candidate with this email already exists', 'error')
                        return redirect(request.url)

                    db.session.add(candidate)
                    db.session.commit()
                    
                    # Match with active job postings
                    active_jobs = JobPosting.query.filter_by(status='active').all()
                    matches = []
                    
                    for job in active_jobs:
                        match_score = job_matcher.calculate_match_score_sync(
                            analysis,
                            json.loads(job.requirements)
                        )
                        print(match_score)
                        application = Application(
                            candidate_id=candidate.id,
                            job_posting_id=job.id,
                            match_score=match_score['total_score'],
                            ai_feedback=match_score['ai_analysis'],
                            status='pending'
                        )
                        
                        db.session.add(application)
                        matches.append({
                            'job_title': job.title,
                            'match_score': match_score['total_score'],
                            'analysis': match_score['ai_analysis']
                        })
                    
                    db.session.commit()
                    
                    # Return JSON response for AJAX handling
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({
                            'status': 'success',
                            'message': 'Resume uploaded and analyzed successfully',
                            'matches': matches,
                            'redirect_url': url_for('resume_results', email=candidate.email)
                        })
                    
                    flash('Resume uploaded and analyzed successfully', 'success')
                    
                    # Redirect to the resume results page using email
                    return redirect(url_for('resume_results', email=candidate.email))
                else:
                    flash('Failed to analyze resume', 'error')
            
            except Exception as e:
                app.logger.error(f'Error processing resume: {str(e)}')
                flash(f'Error processing resume: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload PDF or DOCX files only.', 'error')
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/resume-results/<string:email>')
def resume_results(email):
    """Display the resume analysis results for a specific candidate by email."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        use_ai = request.args.get('use_ai', '0') == '1'  # Default to quick matching
        
        # Find the candidate by email
        candidate = Candidate.query.filter_by(email=email).first_or_404()
        print(f"Found candidate: {candidate.name} ({candidate.email})")
        
        # Get candidate data for matching
        candidate_data = {
            'skills': candidate.skills if candidate.skills else [],
            'experience': candidate.experience if candidate.experience else [],
            'education': candidate.education if candidate.education else []
        }
        print(f"Candidate data: {candidate_data}")
        
        # Debug print
        print("Loading jobs from CSV...")
        jobs = data_processor._get_cached_jobs()
        print(f"Loaded {len(jobs)} jobs from CSV")
        
        # Generate matches
        matches_result = data_processor.match_candidate_with_jobs(
            candidate_data,
            page=page, 
            per_page=per_page,
            use_ai=use_ai
        )
        print(f"Generated {len(matches_result['matches'])} matches")
        
        return render_template('resume_results.html', 
                            candidate=candidate,
                            matches=matches_result['matches'],
                            page=page,
                            per_page=per_page,
                            total_matches=matches_result['pagination']['total'],
                            total_pages=matches_result['pagination']['total_pages'],
                            use_ai=use_ai)
    except Exception as e:
        print(f"Error in resume_results: {e}")
        flash('An error occurred while processing your resume. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/jobs')
def jobs():
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    department = request.args.get('department')
    status = request.args.get('status')
    
    # Build query
    query = JobPosting.query
    
    if department:
        query = query.filter_by(department=department)
    if status:
        query = query.filter_by(status=status)
    
    # Get paginated results
    jobs_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    jobs = jobs_paginated.items
    
    # Prepare job data with match counts
    job_data = []
    for job in jobs:
        applications = Application.query.filter_by(job_posting_id=job.id).all()
        match_count = len(applications)
        avg_score = sum(app.match_score for app in applications) / match_count if match_count > 0 else 0
        
        job_data.append({
            'job': job,
            'match_count': match_count,
            'avg_score': avg_score
        })
    
    # Get available departments and statuses for filters
    departments = db.session.query(JobPosting.department).distinct().all()
    departments = [d[0] for d in departments if d[0]]
    statuses = ['active', 'closed', 'draft', 'archived']
    
    return render_template('jobs.html',
                         jobs=job_data,
                         pagination=jobs_paginated,
                         departments=departments,
                         statuses=statuses,
                         current_department=department,
                         current_status=status)

@app.route('/jobs/<int:job_id>')
def view_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    applications = Application.query.filter_by(job_posting_id=job_id)\
        .order_by(Application.match_score.desc()).all()
    
    # Get candidate details for each application
    matches = []
    for app in applications:
        candidate = Candidate.query.get(app.candidate_id)
        matches.append({
            'candidate': candidate,
            'match_score': app.match_score,
            'feedback': app.ai_feedback
        })
    
    return render_template('job_details.html',
                         job=job,
                         matches=matches)

@app.route('/jobs/<int:job_id>/matches')
def job_matches(job_id):
    job = JobPosting.query.get_or_404(job_id)
    applications = Application.query.filter_by(job_posting_id=job_id)\
        .order_by(Application.match_score.desc()).all()
    
    matches = []
    for app in applications:
        candidate = Candidate.query.get(app.candidate_id)
        matches.append({
            'candidate': candidate,
            'match_score': app.match_score,
            'feedback': app.ai_feedback
        })
    
    return jsonify({
        'job': {
            'title': job.title,
            'department': job.department,
            'matches': matches
        }
    })

@app.route('/report')
def report():
    # Generate analytics report
    total_candidates = Candidate.query.count()
    total_jobs = JobPosting.query.count()
    total_applications = Application.query.count()
    
    # Skills distribution
    all_skills = []
    candidates = Candidate.query.all()
    for candidate in candidates:
        all_skills.extend(candidate.skills or [])
    
    skills_dist = {}
    for skill in all_skills:
        skills_dist[skill] = skills_dist.get(skill, 0) + 1
    
    # Department distribution
    dept_dist = {}
    jobs = JobPosting.query.all()
    for job in jobs:
        dept_dist[job.department] = dept_dist.get(job.department, 0) + 1
    
    report_data = {
        'total_candidates': total_candidates,
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'skills_distribution': skills_dist,
        'department_distribution': dept_dist
    }
    
    return render_template('report.html', report=report_data)

@app.route('/api/jobs', methods=['POST'])
def create_job():
    data = request.json
    print("Received job data:", data)  # Debug print
    
    # Validate required fields
    required_fields = ['title', 'department', 'location', 'description', 'requirements']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
    
    # Validate requirements structure
    if not isinstance(data['requirements'], dict):
        return jsonify({'error': 'Requirements must be a JSON object'}), 400
    
    required_requirement_fields = ['skills', 'experience', 'education']
    missing_req_fields = [field for field in required_requirement_fields if field not in data['requirements']]
    if missing_req_fields:
        return jsonify({'error': f'Missing required requirement fields: {", ".join(missing_req_fields)}'}), 400
    
    # Create job posting
    job = JobPosting(
        title=data['title'],
        department=data['department'],
        location=data['location'],
        description=data['description'],
        requirements=data['requirements'],
        salary_range=data.get('salary_range', ''),
        status=data.get('status', 'draft')  # Default to draft status
    )
    
    try:
        db.session.add(job)
        db.session.commit()
        print("Job created successfully with ID:", job.id)  # Debug print
        
        # Verify the job was saved
        saved_job = JobPosting.query.get(job.id)
        print("Retrieved saved job:", saved_job.title if saved_job else "Not found")  # Debug print
        
        return jsonify({
            'message': 'Job posting created successfully',
            'id': job.id,
            'status': job.status
        })
    except Exception as e:
        db.session.rollback()
        print("Error creating job:", str(e))  # Debug print
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    data = request.json
    
    # Update job fields
    job.title = data.get('title', job.title)
    job.department = data.get('department', job.department)
    job.location = data.get('location', job.location)
    job.description = data.get('description', job.description)
    job.requirements = data.get('requirements', job.requirements)
    job.salary_range = data.get('salary_range', job.salary_range)
    job.status = data.get('status', job.status)
    
    db.session.commit()
    return jsonify({'message': 'Job posting updated successfully'})

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    # Delete associated applications first
    Application.query.filter_by(job_posting_id=job_id).delete()
    
    db.session.delete(job)
    db.session.commit()
    return jsonify({'message': 'Job posting deleted successfully'})

@app.route('/api/jobs/<int:job_id>/status', methods=['PUT'])
def update_job_status(job_id):
    job = JobPosting.query.get_or_404(job_id)
    data = request.json
    
    valid_statuses = ['active', 'closed', 'draft', 'archived']
    new_status = data.get('status')
    
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    job.status = new_status
    db.session.commit()
    return jsonify({'message': f'Job status updated to {new_status}'})

@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    return jsonify({
        'id': job.id,
        'title': job.title,
        'department': job.department,
        'location': job.location,
        'description': job.description,
        'requirements': job.requirements,
        'salary_range': job.salary_range,
        'status': job.status,
        'created_at': job.created_at.isoformat(),
        'updated_at': job.updated_at.isoformat()
    })

@app.route('/jobs/create')
def create_job_page():
    return render_template('create_job.html')

@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.cli.command("init-db")
def init_db():
    """Initialize the database."""
    db.create_all()
    print('Database initialized.')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)