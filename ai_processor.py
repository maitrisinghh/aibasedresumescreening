import os
import google.generativeai as genai
import PyPDF2
import docx
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json

# Download required NLTK data
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')

class ResumeProcessor:
    def __init__(self):
        # Initialize Gemini API
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.stop_words = set(stopwords.words('english'))
        self.vectorizer = TfidfVectorizer()

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF file."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ''
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None

    def extract_text_from_docx(self, docx_path):
        """Extract text from DOCX file."""
        try:
            doc = docx.Document(docx_path)
            text = ''
            for paragraph in doc.paragraphs:
                text += paragraph.text + '\n'
            return text
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return None

    def analyze_resume_sync(self, file_path):
        """Analyze resume using Gemini API."""
        # Extract text based on file type
        if file_path.endswith('.pdf'):
            text = self.extract_text_from_pdf(file_path)
        elif file_path.endswith('.docx'):
            text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError("Unsupported file format")

        if not text:
            raise ValueError("Failed to extract text from resume")

        try:
            # Use Gemini to extract structured information
            prompt = f"""
            Analyze this resume and extract key information in the following JSON format:
            {{
                "skills": ["list of technical and soft skills"],
                "experience": [
                    {{
                        "title": "job title",
                        "company": "company name",
                        "period": "duration",
                        "responsibilities": ["key responsibilities"]
                    }}
                ],
                "education": [
                    {{
                        "degree": "degree name",
                        "institution": "institution name",
                        "year": "completion year"
                    }}
                ]
            }}

            Resume text:
            {text}
            """

            response = self.model.generate_content(prompt)
            
            # Parse the response
            try:
                analysis = json.loads(response.text)
            except json.JSONDecodeError:
                # Fallback to manual extraction if JSON parsing fails
                analysis = {
                    'skills': self.extract_skills(text),
                    'experience': self.extract_experience(text),
                    'education': self.extract_education(text)
                }

            # Enhance with NLP-based extraction
            analysis['skills'] = list(set(analysis.get('skills', []) + self.extract_skills(text)))
            
            return analysis

        except Exception as e:
            print(f"Error analyzing resume with Gemini: {e}")
            return None

    def extract_skills(self, text):
        """Extract skills using NLP."""
        tokens = word_tokenize(text.lower())
        # Remove stop words and punctuation
        words = [word for word in tokens if word.isalnum() and word not in self.stop_words]
        
        # Common technical and soft skills
        common_skills = [
            'python', 'java', 'javascript', 'react', 'node.js', 'sql', 'aws',
            'leadership', 'communication', 'teamwork', 'problem-solving',
            'agile', 'scrum', 'project management', 'analytics', 'machine learning',
            'data science', 'cloud computing', 'devops', 'ci/cd'
        ]
        
        skills = [word for word in words if word in common_skills]
        return list(set(skills))

    def extract_experience(self, text):
        """Extract work experience using NLP."""
        experience = []
        lines = text.split('\n')
        
        current_exp = {}
        for line in lines:
            # Look for date patterns and job titles
            if any(year in line for year in [str(y) for y in range(1990, 2025)]):
                if current_exp:
                    experience.append(current_exp)
                current_exp = {'period': line}
            elif any(title in line.lower() for title in ['engineer', 'developer', 'manager', 'analyst', 'consultant']):
                if 'title' not in current_exp:
                    current_exp['title'] = line
            elif current_exp:
                if 'description' not in current_exp:
                    current_exp['description'] = line
                else:
                    current_exp['description'] += ' ' + line

        if current_exp:
            experience.append(current_exp)
            
        return experience

    def extract_education(self, text):
        """Extract education information using NLP."""
        education = []
        edu_keywords = ['bachelor', 'master', 'phd', 'degree', 'university', 'college']
        
        lines = text.split('\n')
        current_edu = {}
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in edu_keywords):
                if current_edu:
                    education.append(current_edu)
                current_edu = {
                    'degree': line,
                    'year': next((y for y in range(1990, 2025) if str(y) in line), None)
                }
            elif current_edu and 'institution' not in current_edu:
                current_edu['institution'] = line

        if current_edu:
            education.append(current_edu)
            
        return education

class JobMatcher:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Global job categories and their typical requirements
        self.global_job_categories = {
            'Software Development': {
                'skills': ['programming', 'software development', 'coding', 'algorithms', 'data structures', 
                         'version control', 'testing', 'debugging', 'problem solving'],
                'departments': ['Engineering', 'Technology', 'IT', 'Research & Development'],
                'experience_levels': ['Entry Level', 'Mid Level', 'Senior', 'Lead', 'Architect'],
                'education': ['Computer Science', 'Software Engineering', 'Information Technology']
            },
            'Data Science': {
                'skills': ['data analysis', 'machine learning', 'statistics', 'python', 'r', 'sql',
                         'data visualization', 'big data', 'predictive modeling'],
                'departments': ['Data Science', 'Analytics', 'Research', 'Technology'],
                'experience_levels': ['Entry Level', 'Mid Level', 'Senior', 'Lead', 'Principal'],
                'education': ['Data Science', 'Computer Science', 'Statistics', 'Mathematics']
            },
            'Business Analysis': {
                'skills': ['business analysis', 'requirements gathering', 'process improvement', 'project management',
                         'data analysis', 'communication', 'documentation', 'stakeholder management'],
                'departments': ['Business', 'Operations', 'Strategy', 'Consulting'],
                'experience_levels': ['Entry Level', 'Mid Level', 'Senior', 'Lead', 'Manager'],
                'education': ['Business Administration', 'Management', 'Economics', 'Finance']
            },
            'Marketing': {
                'skills': ['digital marketing', 'social media', 'content creation', 'analytics', 'seo',
                         'campaign management', 'brand management', 'market research'],
                'departments': ['Marketing', 'Digital', 'Communications', 'Brand'],
                'experience_levels': ['Entry Level', 'Mid Level', 'Senior', 'Lead', 'Director'],
                'education': ['Marketing', 'Communications', 'Business', 'Media Studies']
            }
        }

    def calculate_match_score_sync(self, candidate_data, job_requirements):
        """Calculate match score between candidate and job using AI."""
        try:
            # Debug print the input data
            print("Candidate Data:", json.dumps(candidate_data, indent=2))
            print("Job Requirements:", json.dumps(job_requirements, indent=2))

            # Ensure job_requirements is properly structured
            if not isinstance(job_requirements, dict):
                print("Warning: job_requirements is not a dictionary")
                job_requirements = {
                    'skills': [],
                    'experience': [],
                    'education': []
                }
            
            # Extract skills, ensuring they're in a list format
            required_skills = job_requirements.get('skills', [])
            if isinstance(required_skills, str):
                required_skills = [skill.strip() for skill in required_skills.split(',')]
            
            # Extract candidate skills
            candidate_skills = candidate_data.get('skills', [])
            
            # Calculate direct skill matches
            required_skills_lower = {skill.lower() for skill in required_skills}
            candidate_skills_lower = {skill.lower() for skill in candidate_skills}
            matching_skills = required_skills_lower.intersection(candidate_skills_lower)
            missing_skills = required_skills_lower - candidate_skills_lower
            
            # Calculate base match score from skills
            skill_match_score = len(matching_skills) / len(required_skills_lower) if required_skills_lower else 0.5
            skill_match_score = skill_match_score * 100  # Convert to percentage
            
            # Create analysis
            analysis = {
                'match_score': skill_match_score,
                'summary': f"Candidate matches {len(matching_skills)} out of {len(required_skills_lower)} required skills",
                'strengths': [
                    f"Proficient in {skill}" for skill in matching_skills
                ],
                'gaps': [
                    f"Missing skill: {skill}" for skill in missing_skills
                ],
                'recommendations': [
                    f"Consider learning {skill}" for skill in list(missing_skills)[:3]
                ] if missing_skills else ["Strong match with required skills"],
                'matching_skills': list(matching_skills),
                'missing_skills': list(missing_skills)
            }
            
            # Adjust match score based on experience if available
            exp_requirements = job_requirements.get('experience', {})
            if exp_requirements and candidate_data.get('experience'):
                min_years = exp_requirements.get('minimum_years', 0)
                candidate_years = sum(len(exp.get('period', '').split('-')) 
                                   for exp in candidate_data['experience'])
                
                if candidate_years >= min_years:
                    analysis['match_score'] = min(100, analysis['match_score'] + 10)
                    analysis['strengths'].append(f"Has {candidate_years} years of relevant experience")
                else:
                    analysis['match_score'] = max(0, analysis['match_score'] - 10)
                    analysis['gaps'].append(f"Requires {min_years} years of experience")
            
            return {
                'total_score': analysis['match_score'],
                'skill_match': skill_match_score,
                'experience_match': analysis['match_score'],
                'education_match': analysis['match_score'],
                'ai_analysis': analysis
            }

        except Exception as e:
            print(f"Error in AI match scoring: {e}")
            return {
                'total_score': 50,
                'skill_match': 50,
                'experience_match': 50,
                'education_match': 50,
                'ai_analysis': {
                    'match_score': 50,
                    'summary': 'Basic skill matching analysis',
                    'strengths': ["Has some matching skills"],
                    'gaps': ["Could not perform detailed analysis"],
                    'recommendations': ["Review complete job requirements"],
                    'matching_skills': [],
                    'missing_skills': []
                }
            }

    def generate_global_matches(self, candidate_data):
        """Generate global job matches based on candidate's profile."""
        matches = []
        
        # Extract candidate's primary skills and experience
        candidate_skills = [skill.lower() for skill in candidate_data['skills']]
        candidate_experience = candidate_data['experience']
        candidate_education = candidate_data['education']
        
        # Calculate years of experience
        years_of_experience = self.calculate_years_of_experience(candidate_experience)
        experience_level = self.determine_experience_level(years_of_experience)
        
        # Get highest education level
        education_level = self.get_highest_education_level(candidate_education)
        
        # Pre-calculate candidate skill set for faster matching
        candidate_skill_set = set(candidate_skills)
        
        # Batch process all categories at once
        all_categories_analysis = self._batch_analyze_categories(
            candidate_skills,
            experience_level,
            education_level,
            self.global_job_categories
        )
        
        # Match against each job category
        for category, requirements in self.global_job_categories.items():
            # Fast skill matching using sets
            required_skill_set = set(skill.lower() for skill in requirements['skills'])
            matching_skills = candidate_skill_set.intersection(required_skill_set)
            missing_skills = required_skill_set - candidate_skill_set
            
            # Calculate skill match score
            skill_match = len(matching_skills) / len(required_skill_set) if required_skill_set else 0.5
            
            # Calculate overall match score without AI analysis
            match_score = (
                skill_match * 0.5 +  # Skills weight: 50%
                (1.0 if experience_level in requirements['experience_levels'] else 0.5) * 0.3 +  # Experience weight: 30%
                (1.0 if any(edu.lower() in str(education_level).lower() for edu in requirements['education']) else 0.5) * 0.2  # Education weight: 20%
            ) * 100  # Convert to percentage
            
            # Get pre-calculated AI analysis
            ai_analysis = all_categories_analysis.get(category, {
                'summary': f'Quick analysis for {category} roles',
                'strengths': [
                    f'Experience level: {experience_level}',
                    f'Matching skills: {len(matching_skills)} out of {len(required_skill_set)}'
                ],
                'gaps': [],
                'recommendations': [
                    'Consider gaining more experience in this field',
                    'Look for opportunities to develop required skills'
                ],
                'matching_skills': list(matching_skills),
                'missing_skills': list(missing_skills)
            })
            
            matches.append({
                'category': category,
                'match_score': round(match_score, 2),
                'departments': requirements['departments'],
                'experience_level': experience_level,
                'required_skills': requirements['skills'],
                'ai_analysis': ai_analysis
            })
        
        # Sort matches by score
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches[:5]  # Return only top 5 matches

    def _batch_analyze_categories(self, candidate_skills, experience_level, education_level, categories):
        """Batch analyze all categories at once to reduce API calls."""
        try:
            # Create a single prompt for all categories
            categories_prompt = "\n".join([
                f"Category: {category}\nRequired Skills: {', '.join(req['skills'])}"
                for category, req in categories.items()
            ])
            
            prompt = f"""
            Analyze the candidate's fit for multiple job categories:

            Candidate Profile:
            Skills: {', '.join(candidate_skills)}
            Experience Level: {experience_level}
            Education Level: {education_level}

            Categories to analyze:
            {categories_prompt}

            Provide a brief analysis for each category in JSON format:
            {{
                "category_name": {{
                    "summary": "brief assessment",
                    "strengths": ["key strengths"],
                    "gaps": ["potential gaps"],
                    "recommendations": ["quick recommendations"]
                }},
                ...
            }}
            """

            response = self.model.generate_content(prompt)
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                return {}  # Return empty dict if parsing fails
            
        except Exception as e:
            print(f"Error in batch category analysis: {e}")
            return {}

    def calculate_years_of_experience(self, experience):
        """Calculate total years of experience."""
        total_years = 0
        for exp in experience:
            if 'period' in exp:
                # Simple calculation - can be enhanced with actual date parsing
                years = len(exp['period'].split('-'))
                total_years += years
        return total_years

    def determine_experience_level(self, years):
        """Determine experience level based on years."""
        if years < 2:
            return 'Entry Level'
        elif years < 5:
            return 'Mid Level'
        elif years < 8:
            return 'Senior'
        elif years < 12:
            return 'Lead'
        else:
            return 'Principal'

    def get_highest_education_level(self, education):
        """Get highest education level from candidate's education."""
        levels = {
            'phd': 5,
            'master': 4,
            'bachelor': 3,
            'associate': 2,
            'high school': 1
        }
        
        highest_level = 0
        for edu in education:
            degree = edu.get('degree', '').lower()
            for level, value in levels.items():
                if level in degree and value > highest_level:
                    highest_level = value
        return highest_level