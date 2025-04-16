from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class JSONEncodedDict(db.TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = db.Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return json.loads(value)

class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    resume_path = db.Column(db.String(255))
    
    # Extracted information
    skills = db.Column(JSONEncodedDict)
    experience = db.Column(JSONEncodedDict)
    education = db.Column(JSONEncodedDict)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('Application', backref='candidate', lazy=True)

class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50))
    location = db.Column(db.String(100))
    description = db.Column(db.Text)
    requirements = db.Column(JSONEncodedDict)  # Required skills, experience, etc.
    salary_range = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('Application', backref='job_posting', lazy=True)

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    job_posting_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    match_score = db.Column(db.Float)  # AI-generated match score
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, shortlisted, rejected
    ai_feedback = db.Column(JSONEncodedDict)  # AI-generated feedback and analysis
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnalyticsReport(db.Model):
    __tablename__ = 'analytics_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(50))  # hiring_trends, skills_distribution, etc.
    data = db.Column(JSONEncodedDict)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)