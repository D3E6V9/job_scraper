import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from django.conf import settings
import google.generativeai as genai
import logging

# Import handling for different execution contexts
try:
    # When running as part of the Django app
    from scraper.scrapers.utils import get_with_retry
except ImportError:
    try:
        # When running directly
        from utils import get_with_retry
    except ImportError:
        # Fallback
        from .query_search import get_with_retry

from .job_data import JobData

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
            logger.warning(f"Gemini API not configured properly. Error: {str(e)}")
            self.gemini_model = None
    
    def process_job_page(self, job_url, domain_link):
        """Process a job description page"""
        logger.info(f"Processing job page: {job_url}")
        
        try:
            # Get the domain config for this URL
            domain_config = self.domains_df[self.domains_df['domain_link'] == domain_link].iloc[0]
            description_tags = domain_config['domain_job_description_tags']
            
            # Fetch the job page
            response = requests.get(job_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"Error: {job_url} returned status code {response.status_code}")
                return
                
            # Store the HTML content in the database regardless of success
            html_content = response.text
            
            # Import the model directly (not using relative import)
            from scraper.models import ScrapedHTML
            from django.utils import timezone
            
            scraped_html, created = ScrapedHTML.objects.update_or_create(
                url=job_url,
                defaults={
                    'html_content': html_content,
                    'scraped_at': timezone.now(),
                    'source_domain': domain_link
                }
            )
            
            # Parse the HTML
            soup = BeautifulSoup(self._clean_html(html_content), 'html.parser')
            
            # Extract job data from the page
            job_data = self._extract_job_data(soup, description_tags, job_url, domain_config)
            
            # Clean the extracted data
            if job_data:
                job_data = self._clean_job_data(job_data)
                
                # If job data was successfully extracted, save it
                if 'jobTitle' in job_data and job_data['jobTitle']:
                    success = self.job_data.save_job(job_data)
                    if success:
                        # Update the HTML record
                        scraped_html.processing_success = True
                        scraped_html.last_processed = timezone.now()
                        scraped_html.save()
                        logger.info(f"Job data saved for {job_data.get('jobTitle', 'Unknown job')}")
                    else:
                        logger.warning(f"Failed to save job data for {job_url}")
                else:
                    logger.warning(f"Job title missing for {job_url}")
            else:
                logger.warning(f"Failed to extract job data from {job_url}")
            
        except Exception as e:
            logger.error(f"Error processing job page {job_url}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _extract_job_data(self, soup, description_tags, job_url, domain_config):
        """Extract job data from the soup object using improved selectors"""
        job_data = {
            'link': job_url,
            'skills': [],
            'benefits': []
        }
        
        # First try to extract structured data from tables if available
        structured_data = self._extract_structured_data_from_table(soup)
        if structured_data:
            job_data.update(structured_data)
        
        # If we couldn't get a title from structured data, try the standard way
        if 'jobTitle' not in job_data or not job_data['jobTitle']:
            # Try common job title selectors
            title_selectors = [
                'h1.job-title', 'h1.position-title', '.job-header h1', 
                'h1', 'h2.job-title', '.position-title h1',
                '[data-automation="job-detail-title"]', '.job-title-header',
                'header h1', '.job-position h1', '.listing-header h1'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    job_data['jobTitle'] = title_elem.text.strip()
                    break
                    
            # Fallback to title tag if no heading found
            if 'jobTitle' not in job_data or not job_data['jobTitle']:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text()
                    # Many sites use "Title | Company" format in the title tag
                    if ' | ' in title_text:
                        job_data['jobTitle'] = title_text.split(' | ')[0].strip()
                    # Or "Title - Company" format
                    elif ' - ' in title_text:
                        job_data['jobTitle'] = title_text.split(' - ')[0].strip()
                    else:
                        job_data['jobTitle'] = title_text.strip()
        
        # Find the job description content - use only specific tags to avoid irrelevant content
        description_content = ""
        if description_tags:
            for tag in description_tags.split(','):
                if tag.strip():  # Ensure tag is not empty
                    elements = soup.select(tag.strip())
                    for element in elements:
                        # Skip elements that are likely to be navigation, footer, or other irrelevant content
                        if self._is_relevant_content(element):
                            description_content += element.text.strip() + "\n"
        
        # Extract company if not already found
        if 'company' not in job_data or not job_data['company']:
            company_selectors = [
                '.company-name', '.employer-name', '.company', 
                '[data-automation="advertiser-name"]', '.job-company',
                '.company-title', '.employer', '.job-company-name',
                'span.company', '.listing-company'
            ]
            
            for selector in company_selectors:
                company_elem = soup.select_one(selector)
                if company_elem:
                    job_data['company'] = company_elem.text.strip()
                    break
            
            # If still not found, try pattern matching
            if 'company' not in job_data or not job_data['company']:
                job_data['company'] = self._extract_pattern(soup, ['company', 'organization'])
        
        # Extract location if not already found
        if 'jobLocation' not in job_data or not job_data['jobLocation']:
            location_selectors = [
                '.job-location', '.location', '.job-info .location',
                '[data-automation="job-location"]', '.job-details .location',
                '.job-meta .location', 'span.location', '.listing-location'
            ]
            
            for selector in location_selectors:
                location_elem = soup.select_one(selector)
                if location_elem:
                    job_data['jobLocation'] = location_elem.text.strip()
                    break
            
            # If still not found, try pattern matching
            if 'jobLocation' not in job_data or not job_data['jobLocation']:
                job_data['jobLocation'] = self._extract_pattern(soup, ['location', 'address', 'place'])
        
        # Extract job type if not already found
        if 'jobType' not in job_data or not job_data['jobType']:
            type_selectors = [
                '.job-type', '.employment-type', '.job-info .type',
                '[data-automation="job-type"]', '.job-meta .type',
                'span.job-type', '.listing-job-type'
            ]
            
            for selector in type_selectors:
                type_elem = soup.select_one(selector)
                if type_elem:
                    job_data['jobType'] = type_elem.text.strip()
                    break
            
            # If still not found, try pattern matching
            if 'jobType' not in job_data or not job_data['jobType']:
                job_data['jobType'] = self._extract_pattern(soup, ['job type', 'employment type', 'contract'])
                
                # If still not found, try to extract from text content
                if not job_data['jobType']:
                    job_types = ['full-time', 'part-time', 'contract', 'temporary', 'internship', 'freelance', 'remote']
                    text = soup.get_text().lower()
                    found_types = []
                    
                    for jt in job_types:
                        # Look for job type surrounded by spaces or punctuation
                        if re.search(r'[^\w]' + jt + r'[^\w]', text):
                            found_types.append(jt.title())
                    
                    if found_types:
                        job_data['jobType'] = ', '.join(found_types)
        
        # Extract other details using pattern matching if not already in structured data
        if 'salary' not in job_data or not job_data['salary']:
            job_data['salary'] = self._extract_pattern(soup, ['salary', 'compensation', 'pay'])
        
        if 'experience' not in job_data or not job_data['experience']:
            job_data['experience'] = self._extract_pattern(soup, ['experience', 'years of exp'])
        
        if 'education' not in job_data or not job_data['education']:
            job_data['education'] = self._extract_pattern(soup, ['education', 'qualification', 'degree'])
        
        if 'deadline' not in job_data or not job_data['deadline']:
            job_data['deadline'] = self._extract_pattern(soup, ['deadline', 'closing date', 'apply by'])
        
        # Extract job category if not already found
        if 'jobCategory' not in job_data or not job_data['jobCategory']:
            job_data['jobCategory'] = self._extract_pattern(soup, ['category', 'job category'])
        
        # Use Gemini API to extract structured data if available and we have significant content
        if self.gemini_model and (description_content or soup.get_text()) and len(description_content or soup.get_text()) > 100:
            try:
                # If description_content is empty, use the whole page text
                content_to_process = description_content if description_content else soup.get_text()
                job_data = self._enhance_with_gemini(job_data, content_to_process)
            except Exception as e:
                logger.error(f"Gemini API error: {str(e)}")
        
        return job_data
    
    def _clean_html(self, html_content):
        """Clean HTML before parsing"""
        # Remove script and style elements
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted tags that typically contain navigation, ads, etc.
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        
        # Remove elements with common nav/footer class names
        nav_classes = ['nav', 'menu', 'navigation', 'footer', 'header', 'sidebar']
        for cls in nav_classes:
            for tag in soup.find_all(class_=lambda x: x and cls in x.lower()):
                tag.decompose()
        
        return str(soup)
    
    def _clean_job_data(self, job_data):
        """Clean and normalize job data"""
        if 'jobTitle' in job_data and job_data['jobTitle']:
            job_data['jobTitle'] = self._clean_text(job_data['jobTitle'])
            # Remove common unwanted patterns
            job_data['jobTitle'] = re.sub(r'^\s*job\s*:\s*', '', job_data['jobTitle'], flags=re.IGNORECASE)
            job_data['jobTitle'] = re.sub(r'^\s*title\s*:\s*', '', job_data['jobTitle'], flags=re.IGNORECASE)
        
        if 'company' in job_data and job_data['company']:
            job_data['company'] = self._clean_text(job_data['company'])
            # Remove verification tags often seen
            job_data['company'] = re.sub(r'verified.*employer', '', job_data['company'], flags=re.IGNORECASE)
            # Remove other common patterns
            job_data['company'] = re.sub(r'office address.*$', '', job_data['company'], flags=re.IGNORECASE)
            job_data['company'] = re.sub(r'website.*$', '', job_data['company'], flags=re.IGNORECASE)
            # Remove industry text
            job_data['company'] = re.sub(r'industrycomputer.*$', '', job_data['company'], flags=re.IGNORECASE)
        
        if 'jobLocation' in job_data and job_data['jobLocation']:
            job_data['jobLocation'] = self._clean_text(job_data['jobLocation'])
            # Remove prefixes
            job_data['jobLocation'] = re.sub(r'^\s*location\s*:\s*', '', job_data['jobLocation'], flags=re.IGNORECASE)
            # Remove office address prefixes
            job_data['jobLocation'] = re.sub(r'^\s*office\s+address\s*', '', job_data['jobLocation'], flags=re.IGNORECASE)
            # Remove common noise patterns
            job_data['jobLocation'] = re.sub(r'office 8.*$', '', job_data['jobLocation'], flags=re.IGNORECASE)
            # Remove address text if too long
            if job_data['jobLocation'] and len(job_data['jobLocation']) > 100:
                # Try to extract just the city/country
                location_parts = re.split(r'[,\n]', job_data['jobLocation'])
                if location_parts:
                    # Use the last two parts which often contain city, country
                    job_data['jobLocation'] = ', '.join([p.strip() for p in location_parts[-2:] if p.strip()])
        
        if 'jobType' in job_data and job_data['jobType']:
            job_data['jobType'] = self._clean_text(job_data['jobType'])
            # Remove prefixes
            job_data['jobType'] = re.sub(r'^\s*job\s+type\s*:\s*', '', job_data['jobType'], flags=re.IGNORECASE)
            # If jobType contains "refine search" or similar text, it's likely not the job type
            if job_data['jobType'] and ('refine search' in job_data['jobType'].lower() or 'results displaying' in job_data['jobType'].lower()):
                job_data['jobType'] = None
            else:
                # Extract only recognized job types
                job_types = ['full-time', 'part-time', 'contract', 'temporary', 'internship', 'freelance', 'remote']
                found_types = []
                for jt in job_types:
                    if job_data['jobType'] and jt in job_data['jobType'].lower():
                        found_types.append(jt.title())
                if found_types:
                    job_data['jobType'] = ', '.join(found_types)
        
        if 'jobCategory' in job_data and job_data['jobCategory']:
            job_data['jobCategory'] = self._clean_text(job_data['jobCategory'])
            # Remove navigation text often found
            if job_data['jobCategory'] and ('guide' in job_data['jobCategory'].lower() or 'start hiring' in job_data['jobCategory'].lower() or 'partnership' in job_data['jobCategory'].lower()):
                job_data['jobCategory'] = None
        
        if 'salary' in job_data and job_data['salary']:
            job_data['salary'] = self._clean_text(job_data['salary'])
            # Remove common patterns that aren't actually salary
            if job_data['salary'] and ('png' in job_data['salary'].lower() or 'report this company' in job_data['salary'].lower()):
                job_data['salary'] = None
        
        return job_data
    
    def _extract_structured_data_from_table(self, soup):
        """Extract structured job data from tables on the page"""
        structured_data = {}
        
        # Look for job tables
        tables = soup.find_all('table')
        for table in tables:
            # Skip tables that are likely navigation or unrelated content
            if 'menu' in str(table).lower() or 'navigation' in str(table).lower():
                continue
                
            # Check if this looks like a job listing table
            if 'job' in str(table).lower() or 'position' in str(table).lower() or 'title' in str(table).lower():
                rows = table.find_all('tr')
                
                # Process table rows
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        header = cells[0].text.strip().lower()
                        value = cells[1].text.strip()
                        
                        # Map table headers to our data structure
                        if any(keyword in header for keyword in ['title', 'position']):
                            # Split title and skills if in format "Title (Skills: xyz)"
                            title_parts = value.split('Skills:')
                            structured_data['jobTitle'] = title_parts[0].strip()
                            if len(title_parts) > 1:
                                skills_text = title_parts[1].strip()
                                structured_data['skills'] = [s.strip() for s in skills_text.split(',')]
                        
                        elif any(keyword in header for keyword in ['company', 'organization']):
                            structured_data['company'] = value
                        
                        elif any(keyword in header for keyword in ['category', 'field']):
                            structured_data['jobCategory'] = value
                        
                        elif any(keyword in header for keyword in ['location', 'place', 'address']):
                            structured_data['jobLocation'] = value
                        
                        elif any(keyword in header for keyword in ['deadline', 'closing date', 'apply by']):
                            structured_data['deadline'] = value
                        
                        elif any(keyword in header for keyword in ['type', 'employment']):
                            structured_data['jobType'] = value
                        
                        elif any(keyword in header for keyword in ['link', 'url', 'apply']):
                            # Try to get href if it's an anchor tag
                            link_tag = cells[1].find('a')
                            if link_tag and link_tag.get('href'):
                                structured_data['link'] = link_tag.get('href')
        
        return structured_data
    
    def _is_relevant_content(self, element):
        """Check if an element is likely to contain relevant job content"""
        # Skip elements that are likely navigation, footer, or sidebars
        blacklist_classes = ['nav', 'menu', 'footer', 'sidebar', 'header', 'copyright', 'social']
        element_classes = element.get('class', [])
        
        if isinstance(element_classes, str):
            element_classes = [element_classes]
            
        # Check if any blacklisted class is in the element's classes
        for cls in element_classes:
            if any(blacklist in cls.lower() for blacklist in blacklist_classes):
                return False
        
        # Check element ID
        element_id = element.get('id', '')
        if any(blacklist in element_id.lower() for blacklist in blacklist_classes):
            return False
        
        # Check if element contains very little text or too much text
        text = element.text.strip()
        if len(text) < 10 or len(text) > 10000:
            return False
        
        # Check if element contains typical job description terms
        job_terms = ['experience', 'requirements', 'qualifications', 'responsibilities', 
                    'skills', 'education', 'about', 'description', 'overview']
        if any(term in text.lower() for term in job_terms):
            return True
            
        return True  # Default to including content if no red flags
    
    def _extract_pattern(self, soup, keywords):
        """Extract data from soup based on pattern matching"""
        text = soup.get_text().lower()
        
        for keyword in keywords:
            pattern = rf'{keyword}\s*:?\s*([\w\s,-./]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _clean_text(self, text):
        """Basic text cleaning function"""
        if not text:
            return None
        
        # Convert to string
        text = str(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Return None if empty
        if not text:
            return None
        
        return text
    
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
            
            if 'Category:' in result and not job_data.get('jobCategory'):
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
            logger.error(f"Error using Gemini API: {str(e)}")
        
        return job_data
    
def process_job_page(self, job_url, domain_link):
    """Process a job description page"""
    # Skip login, registration, and non-job pages
    non_job_patterns = [
        '/login/', 
        '/register/', 
        '#jobseeker', 
        'employer-zone',
        'play.google.com',
        'apple.com'
    ]
    
    # Check if URL matches any non-job pattern
    if any(pattern in job_url for pattern in non_job_patterns):
        logger.info(f"Skipping non-job page: {job_url}")
        return
    
    # Continue with existing code...