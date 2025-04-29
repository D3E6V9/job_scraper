import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from django.conf import settings
import google.generativeai as genai
from .query_search import get_with_retry

from .job_data import JobData

class JobDescription:
    """Class for processing job description pages"""
    
    def __init__(self):
        """Initialize the job description processor"""
        # Load domain configuration from CSV
        self.domains_file = os.path.join(settings.CSV_FILE_DIR, 'domain.csv')
        try:
            self.domains_df = pd.read_csv(self.domains_file)
        except Exception as e:
            raise Exception(f"Error loading domain configuration: {str(e)}")
        
        # Initialize Gemini API
        self.setup_gemini_api()
        
        # Initialize job data storage
        self.job_data = JobData()
    
    def setup_gemini_api(self):
        """Setup the Gemini API client"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"Warning: Gemini API not configured properly. Error: {str(e)}")
            self.gemini_model = None
    
    def process_job_page(self, job_url, domain_link):
        """Process a job description page"""
        print(f"Processing job page: {job_url}")
        
        try:
            # Get the domain config for this URL
            domain_config = self.domains_df[self.domains_df['domain_link'] == domain_link].iloc[0]
            description_tags = domain_config['domain_job_description_tags']
            
            # Fetch the job page
            response = requests.get(job_url, timeout=30)
            if response.status_code != 200:
                print(f"Error: {job_url} returned status code {response.status_code}")
                return
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract job data from the page
            job_data = self._extract_job_data(soup, description_tags, job_url)
            
            # If job data was successfully extracted, save it
            if job_data:
                self.job_data.save_job(job_data)
                print(f"Job data saved for {job_data.get('jobTitle', 'Unknown job')}")
            
        except Exception as e:
            print(f"Error processing job page {job_url}: {str(e)}")
    
    def _extract_job_data(self, soup, description_tags, job_url):
        """Extract job data from the soup object"""
        job_data = {
            'link': job_url,
            'skills': [],
            'benefits': []
        }
        
        # Extract job title
        title_tag = soup.select_one('h1') or soup.select_one('title')
        if title_tag:
            job_data['jobTitle'] = title_tag.text.strip()
        else:
            # If no title found, skip this job
            return None
        
        # Find the job description content
        description_content = ""
        for tag in description_tags.split(','):
            elements = soup.select(tag.strip())
            for element in elements:
                description_content += element.text.strip() + "\n"
        
        # Extract other job details using pattern matching
        job_data['company'] = self._extract_pattern(soup, ['company', 'organization'])
        job_data['jobLocation'] = self._extract_pattern(soup, ['location', 'address', 'place'])
        job_data['jobType'] = self._extract_pattern(soup, ['job type', 'employment type', 'contract'])
        job_data['salary'] = self._extract_pattern(soup, ['salary', 'compensation', 'pay'])
        job_data['experience'] = self._extract_pattern(soup, ['experience', 'years of exp'])
        job_data['education'] = self._extract_pattern(soup, ['education', 'qualification', 'degree'])
        job_data['deadline'] = self._extract_pattern(soup, ['deadline', 'closing date', 'apply by'])
        
        # Use Gemini API to extract structured data if available
        if self.gemini_model and description_content:
            try:
                job_data = self._enhance_with_gemini(job_data, description_content)
            except Exception as e:
                print(f"Gemini API error: {str(e)}")
        
        return job_data
    
    def _extract_pattern(self, soup, keywords):
        """Extract data from soup based on pattern matching"""
        text = soup.get_text().lower()
        
        for keyword in keywords:
            pattern = rf'{keyword}\s*:?\s*([\w\s,-./]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _enhance_with_gemini(self, job_data, description_content):
        """Use Gemini API to enhance job data extraction"""
        prompt = f"""
        Extract the following information from this job description:
        1. Skills required (list up to 14)
        2. Benefits offered (list up to 14)
        3. Job category
        4. Industry
        5. Education requirements
        6. Experience requirements
        7. Job Type (full-time, part-time, contract, etc.)
        
        Return the results in a structured format like this:
        Skills: skill1, skill2, ...
        Benefits: benefit1, benefit2, ...
        Category: category
        Industry: industry
        Education: education requirement
        Experience: experience requirement
        Job Type: job type
        
        Here's the job description:{description_content}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = response.text
            
            # Parse the Gemini output
            if 'Skills:' in result:
                skills_match = re.search(r'Skills:\s*(.*?)(?:\n|$)', result)
                if skills_match:
                    skills = [s.strip() for s in skills_match.group(1).split(',')]
                    job_data['skills'] = skills[:14]  # Limit to 14 skills
            
            if 'Benefits:' in result:
                benefits_match = re.search(r'Benefits:\s*(.*?)(?:\n|$)', result)
                if benefits_match:
                    benefits = [b.strip() for b in benefits_match.group(1).split(',')]
                    job_data['benefits'] = benefits[:14]  # Limit to 14 benefits
            
            if 'Category:' in result:
                category_match = re.search(r'Category:\s*(.*?)(?:\n|$)', result)
                if category_match:
                    job_data['jobCategory'] = category_match.group(1).strip()
            
            if 'Industry:' in result:
                industry_match = re.search(r'Industry:\s*(.*?)(?:\n|$)', result)
                if industry_match:
                    job_data['jobIndustry'] = industry_match.group(1).strip()
            
            if 'Education:' in result and not job_data.get('education'):
                education_match = re.search(r'Education:\s*(.*?)(?:\n|$)', result)
                if education_match:
                    job_data['education'] = education_match.group(1).strip()
            
            if 'Experience:' in result and not job_data.get('experience'):
                experience_match = re.search(r'Experience:\s*(.*?)(?:\n|$)', result)
                if experience_match:
                    job_data['experience'] = experience_match.group(1).strip()
            
            if 'Job Type:' in result and not job_data.get('jobType'):
                job_type_match = re.search(r'Job Type:\s*(.*?)(?:\n|$)', result)
                if job_type_match:
                    job_data['jobType'] = job_type_match.group(1).strip()
        
        except Exception as e:
            print(f"Error using Gemini API: {str(e)}")
        
        return job_data