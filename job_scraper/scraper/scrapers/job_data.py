from scraper.models import JobData as JobDataModel, Skill, Benefit

class JobData:
    """Class for saving job data to the database"""
    
    def save_job(self, job_data):
        """Save job data to the database"""
        # Check if job already exists (by URL)
        link = job_data.get('link', '')
        
        if not link or not job_data.get('jobTitle'):
            print("Job data missing required fields (link or title)")
            return False
        
        # Check if this job already exists
        existing_job = JobDataModel.objects.filter(link=link).first()
        if existing_job:
            print(f"Job already exists in database: {job_data.get('jobTitle')}")
            return False
        
        try:
            # Create skill record if skills are present
            skill_obj = None
            if 'skills' in job_data and job_data['skills']:
                skill_data = {}
                for i, skill in enumerate(job_data['skills'][:14], 1):
                    skill_data[f'skill_{i}'] = skill
                
                skill_obj = Skill.objects.create(**skill_data)
            
            # Create benefit record if benefits are present
            benefit_obj = None
            if 'benefits' in job_data and job_data['benefits']:
                benefit_data = {}
                for i, benefit in enumerate(job_data['benefits'][:14], 1):
                    benefit_data[f'benefit_{i}'] = benefit
                
                benefit_obj = Benefit.objects.create(**benefit_data)
            
            # Prepare job data for database
            db_job_data = {
                'jobTitle': job_data.get('jobTitle', ''),
                'jobCategory': job_data.get('jobCategory', ''),
                'jobIndustry': job_data.get('jobIndustry', ''),
                'company': job_data.get('company', ''),
                'vacancy': job_data.get('vacancy', ''),
                'education': job_data.get('education', ''),
                'experience': job_data.get('experience', ''),
                'jobLocation': job_data.get('jobLocation', ''),
                'jobType': job_data.get('jobType', ''),
                'deadline': job_data.get('deadline', ''),
                'salary': job_data.get('salary', ''),
                'link': link,
                'skill': skill_obj,
                'benefit': benefit_obj
            }
            
            # Create job record
            job = JobDataModel.objects.create(**db_job_data)
            
            return True
        
        except Exception as e:
            print(f"Error saving job data: {str(e)}")
            return False