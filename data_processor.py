import csv
import json
from typing import List, Dict, Any
from ai_processor import JobMatcher
import time
import os

class DataProcessor:
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.job_matcher = JobMatcher()
        self._cached_jobs = None
        self._last_cache_time = 0
        self._cache_duration = 300  # Cache for 5 minutes
        
    def _get_cached_jobs(self) -> List[Dict[str, Any]]:
        """Get cached jobs or load from CSV if cache is expired."""
        current_time = time.time()
        if (self._cached_jobs is None or 
            current_time - self._last_cache_time > self._cache_duration):
            self._cached_jobs = self._load_jobs_from_csv()
            self._last_cache_time = current_time
        return self._cached_jobs
    
    def _load_jobs_from_csv(self) -> List[Dict[str, Any]]:
        """Load job data from CSV file."""
        try:
            print(f"\nAttempting to load jobs from: {self.csv_file_path}")
            print(f"File exists: {os.path.exists(self.csv_file_path)}")
            print(f"File size: {os.path.getsize(self.csv_file_path)} bytes")
            
            jobs = []
            with open(self.csv_file_path, 'r', encoding='utf-8', errors='replace') as f:
                # Read first few lines for debugging
                print("\nFirst few lines of the file:")
                for i, line in enumerate(f):
                    if i < 5:  # Print first 5 lines
                        print(f"Line {i+1}: {line.strip()}")
                    else:
                        break
                f.seek(0)  # Reset file pointer to beginning
                
                try:
                    reader = csv.DictReader(f)
                    print(f"\nCSV headers: {reader.fieldnames}")
                    
                    for i, row in enumerate(reader):
                        if i >= 100:  # Limit to 100 entries
                            print(f"Reached limit of 100 entries. Stopping.")
                            break
                            
                        try:
                            if not row:
                                print(f"Empty row at index {i}")
                                continue
                                
                            # Print raw row data for debugging
                            print(f"\nProcessing row {i+1}:")
                            print(f"Raw row data: {row}")
                            
                            # Parse job title and role
                            job_title = row.get('Job Title', '').strip()
                            role = row.get('Role', '').strip()
                            
                            if not job_title:
                                print(f"Skipping row {i+1}: Missing job title")
                                continue
                            
                            print(f"Title: {job_title}")
                            print(f"Role: {role}")
                            
                            # Parse job description
                            description = row.get('Description', '').strip()
                            
                            # Parse qualifications
                            qualifications = row.get('Qualifications', '').strip()
                            
                            # Parse skills (from the correct column)
                            skills_text = row.get('skills', '').strip()
                            skills = []
                            if skills_text:
                                # Split by commas and clean up each skill
                                skills = [skill.strip() for skill in skills_text.split(',')]
                                # Further clean up by removing any nested quotes or brackets
                                skills = [skill.strip('" []').strip() for skill in skills]
                                print(f"Parsed skills: {skills}")
                            
                            # Create job object
                            job = {
                                'title': job_title,
                                'job_title': job_title,
                                'role': role,
                                'description': description,
                                'qualifications': qualifications,
                                'company': row.get('Company', 'Not specified'),
                                'salary_range': row.get('Salary Range', 'Not specified'),
                                'work_type': row.get('Work Type', 'Not specified'),
                                'requirements': {
                                    'skills': skills,
                                    'experience': self._parse_experience(qualifications),
                                    'education': self._parse_qualifications(qualifications)
                                }
                            }
                            jobs.append(job)
                            
                        except Exception as e:
                            print(f"Error parsing row {i}: {str(e)}")
                            print(f"Row data: {row}")
                            continue
                            
                except csv.Error as e:
                    print(f"CSV parsing error: {str(e)}")
                    return []
            
            print(f"\nSuccessfully loaded {len(jobs)} jobs")
            if len(jobs) == 0:
                print("Warning: No jobs were loaded from the CSV file")
            return jobs
            
        except Exception as e:
            print(f"Error loading jobs from CSV: {str(e)}")
            print(f"File path: {self.csv_file_path}")
            print(f"Error details: {str(e)}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return []

    def _parse_qualifications(self, qualifications: str) -> List[str]:
        """Parse qualifications text to extract education requirements."""
        education_keywords = ['bachelor', 'master', 'phd', 'degree', 'diploma', 'certification']
        education_levels = []
        
        for line in qualifications.split('\n'):
            line_lower = line.lower()
            for keyword in education_keywords:
                if keyword in line_lower:
                    education_levels.append(line.strip())
                    break
                    
        return education_levels

    def _parse_experience(self, qualifications: str) -> Dict[str, Any]:
        """Parse qualifications text to extract experience requirements."""
        experience = {
            'minimum_years': 0,
            'description': []
        }
        
        for line in qualifications.split('\n'):
            line_lower = line.lower()
            if 'experience' in line_lower or 'years' in line_lower:
                experience['description'].append(line.strip())
                # Try to extract years of experience
                words = line_lower.split()
                for i, word in enumerate(words):
                    if word.isdigit() and i > 0 and words[i-1] in ['minimum', 'at least', 'more than']:
                        experience['minimum_years'] = int(word)
                        break
                        
        return experience

    def _pre_filter_jobs(self, jobs: List[Dict[str, Any]], 
                        candidate_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pre-filter jobs based on basic criteria to reduce processing time."""
        filtered_jobs = []
        candidate_skills = {skill.lower().strip() for skill in candidate_data.get('skills', [])}
        print(f"\nPre-filtering jobs:")
        print(f"Candidate skills: {candidate_skills}")
        
        # Define relevant job categories for tech roles (more inclusive)
        tech_keywords = {
            'developer', 'engineer', 'programmer', 'software', 'web', 'full stack',
            'backend', 'frontend', 'data scientist', 'devops', 'qa', 'test',
            'analyst', 'architect', 'specialist', 'consultant', 'manager',
            'developer', 'tech', 'it', 'information', 'system', 'application',
            'cloud', 'security', 'network', 'support', 'administrator', 'lead',
            'head', 'chief', 'director', 'coordinator', 'designer', 'marketing',
            'digital', 'content', 'social media', 'data'
        }
        
        for i, job in enumerate(jobs):
            print(f"\nChecking job {i+1}:")
            # Get job details
            job_title_lower = job.get('title', '').lower()
            role_lower = job.get('role', '').lower()
            print(f"Title: {job_title_lower}")
            print(f"Role: {role_lower}")
            
            # More lenient tech job check
            is_tech_job = (
                any(keyword in job_title_lower for keyword in tech_keywords) or
                any(keyword in role_lower for keyword in tech_keywords) or
                any(tech_word in job_title_lower for tech_word in ['tech', 'it', 'software', 'data', 'digital', 'marketing', 'social']) or
                any(tech_word in role_lower for tech_word in ['tech', 'it', 'software', 'data', 'digital', 'marketing', 'social'])
            )
            
            print(f"Is tech job: {is_tech_job}")
            
            if not is_tech_job:
                print("Skipping: Not a tech job")
                continue
            
            # Get job skills (more lenient parsing)
            job_skills = set()
            requirements = job.get('requirements', {})
            if isinstance(requirements, dict):
                skills_list = requirements.get('skills', [])
                if isinstance(skills_list, list):
                    # Clean and normalize skills
                    job_skills = {skill.lower().strip().strip('"[]') for skill in skills_list}
                elif isinstance(skills_list, str):
                    # Handle string format
                    job_skills = {skill.lower().strip().strip('"[]') for skill in skills_list.split(',')}
            
            print(f"Job skills: {job_skills}")
            
            # Calculate skill match (more lenient)
            if job_skills:
                common_skills = candidate_skills.intersection(job_skills)
                skill_score = len(common_skills) / len(job_skills) if job_skills else 0
                print(f"Common skills: {common_skills}")
                print(f"Skill score: {skill_score}")
                
                # Include job if there's any skill match or few required skills
                if skill_score > 0 or len(job_skills) <= 5:
                    print("Job accepted: Has matching skills or few requirements")
                    job['preliminary_score'] = skill_score * 100
                    filtered_jobs.append(job)
            else:
                # Include jobs with no specific skill requirements
                print("Job accepted: No specific skill requirements")
                job['preliminary_score'] = 50  # Neutral score for jobs without specific requirements
                filtered_jobs.append(job)
        
        # Sort by preliminary score
        filtered_jobs.sort(key=lambda x: x['preliminary_score'], reverse=True)
        print(f"\nTotal jobs after filtering: {len(filtered_jobs)}")
        
        # Take top matches
        result = filtered_jobs[:50]  # Increase limit to 50 matches
        print(f"Returning top {len(result)} matches")
        
        # Print top matches
        if result:
            print("\nTop matches:")
            for i, job in enumerate(result[:5]):  # Show top 5 for debugging
                print(f"{i+1}. {job.get('title')} (Score: {job.get('preliminary_score')})")
                print(f"   Skills: {job.get('requirements', {}).get('skills', [])}")
        
        return result

    def match_candidate_with_jobs(self, candidate_data: Dict[str, Any], 
                                page: int = 1, 
                                per_page: int = 10,
                                use_ai: bool = True) -> Dict[str, Any]:
        """Match a candidate with jobs from the CSV data with pagination."""
        try:
            print("\nStarting job matching process:")
            print(f"Candidate skills: {candidate_data.get('skills', [])}")
            
            jobs = self._get_cached_jobs()
            print(f"Total jobs loaded: {len(jobs)}")
            
            # Get pre-filtered jobs
            filtered_jobs = self._pre_filter_jobs(jobs, candidate_data)
            print(f"Jobs after pre-filtering: {len(filtered_jobs)}")
            
            if not filtered_jobs:
                print("No jobs passed pre-filtering stage")
            
            # Calculate total pages
            total_jobs = len(filtered_jobs)
            total_pages = (total_jobs + per_page - 1) // per_page
            
            # Get jobs for current page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_jobs = filtered_jobs[start_idx:end_idx]
            
            matches = []
            for job in page_jobs:
                try:
                    print(f"\nCalculating match score for job: {job.get('title')}")
                    print(f"Job skills: {job.get('requirements', {}).get('skills', [])}")
                    
                    # Calculate match score
                    match_score = self.job_matcher.calculate_match_score_sync(
                        candidate_data,
                        job['requirements']
                    )
                    print(f"Match score: {match_score['total_score']}")
                    
                    # Create match object with all required fields
                    match_obj = {
                        'job': {
                            'title': job.get('title', ''),
                            'company': job.get('company', 'Not specified'),
                            'role': job.get('role', ''),
                            'salary_range': job.get('salary_range', 'Not specified'),
                            'work_type': job.get('work_type', 'Not specified'),
                            'requirements': job.get('requirements', {})
                        },
                        'match_score': match_score['total_score'],
                        'skill_match': match_score['skill_match'],
                        'experience_match': match_score['experience_match'],
                        'education_match': match_score.get('education_match', 0),
                        'ai_analysis': match_score['ai_analysis']
                    }
                    matches.append(match_obj)
                except Exception as e:
                    print(f"Error processing job match: {e}")
                    continue
            
            print(f"\nTotal matches found: {len(matches)}")
            return {
                'matches': matches,
                'pagination': {
                    'total': total_jobs,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages
                }
            }
        except Exception as e:
            print(f"Error in match_candidate_with_jobs: {e}")
            return {
                'matches': [],
                'pagination': {
                    'total': 0,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': 0
                }
            }

    def get_job_categories(self) -> List[str]:
        """Get unique job categories from the CSV data."""
        jobs = self._get_cached_jobs()
        categories = set()
        
        for job in jobs:
            categories.add(job['role'])
            
        return sorted(list(categories))

    def get_skills_distribution(self) -> Dict[str, int]:
        """Get distribution of required skills across all jobs."""
        jobs = self._get_cached_jobs()
        skills_count = {}
        
        for job in jobs:
            for skill in job['requirements']['skills']:
                skills_count[skill] = skills_count.get(skill, 0) + 1
                
        return dict(sorted(skills_count.items(), key=lambda x: x[1], reverse=True)) 