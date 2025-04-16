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
                            'matches': matches
                        })
                    
                    flash('Resume uploaded and analyzed successfully', 'success')
                    return redirect(url_for('resume_results', candidate_id=candidate.id))
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

# Add after the upload route:

@app.route('/resume-results/<int:candidate_id>')
def resume_results(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    
    # Get the candidate's applications and related job postings
    applications = db.session.query(
        Application, JobPosting
    ).join(
        JobPosting
    ).filter(
        Application.candidate_id == candidate_id
    ).order_by(
        Application.match_score.desc()
    ).all()
    
    # Format experience and education for display
    experience_data = candidate.experience if candidate.experience else []
    education_data = candidate.education if candidate.education else []
    
    return render_template('resume_results.html', 
                          candidate=candidate,
                          applications=applications,
                          experience=experience_data,
                          education=education_data)