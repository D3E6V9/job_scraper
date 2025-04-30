import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_with_retry(url, max_retries=3):
    """Make HTTP requests with retry logic and browser-like headers"""
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Add random delay before request
    time.sleep(random.uniform(1, 3))
    
    return session.get(url, headers=headers, timeout=30)
# ADD these new functions to scraper/scrapers/utils.py

def extract_with_multiple_selectors(soup, selectors, attr=None):
    """
    Try multiple CSS selectors and return the first match
    
    Args:
        soup: BeautifulSoup object
        selectors: List of CSS selectors to try
        attr: Optional attribute to extract instead of text
        
    Returns:
        Extracted text or None if no match
    """
    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            element = elements[0]
            if attr:
                return element.get(attr)
            return element.get_text(strip=True)
    return None

def extract_job_title(soup):
    """Extract job title with multiple selector strategies"""
    # Try common job title selectors
    selectors = [
        'h1.job-title', 'h1.position-title', '.job-header h1', 
        'h1', 'h2.job-title', '.position-title h1',
        '[data-automation="job-detail-title"]', '.job-title-header',
        'header h1', '.job-position h1', '.listing-header h1'
    ]
    
    title = extract_with_multiple_selectors(soup, selectors)
    if title:
        # Clean up common patterns
        title = re.sub(r'\s*\(m/f/d\)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\([^)]*\)$', '', title)  # Remove parentheses at the end
        return title.strip()
    
    # Fallback: Look for a title tag
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text()
        # Many sites use "Title | Company" format in the title tag
        if ' | ' in title_text:
            return title_text.split(' | ')[0].strip()
        # Or "Title - Company" format
        if ' - ' in title_text:
            return title_text.split(' - ')[0].strip()
        return title_text.strip()
    
    return None

def extract_company(soup):
    """Extract company name with multiple selector strategies"""
    selectors = [
        '.company-name', '.employer-name', '.company', 
        '[data-automation="advertiser-name"]', '.job-company',
        '.company-title', '.employer', '.job-company-name',
        'span.company', '.listing-company'
    ]
    
    company = extract_with_multiple_selectors(soup, selectors)
    if company:
        # Clean common suffixes
        company = re.sub(r'\s*(Pvt\.|Private|Ltd\.?|Limited|Inc\.?|Corporation)$', '', company)
        return company.strip()
    
    # Fallback: Look for a title tag
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text()
        # Many sites use "Title | Company" format in the title tag
        if ' | ' in title_text:
            return title_text.split(' | ')[1].strip()
        # Or "Title - Company" format
        if ' - ' in title_text:
            return title_text.split(' - ')[1].strip()
    
    return None

def extract_location(soup):
    """Extract job location with multiple strategies"""
    selectors = [
        '.job-location', '.location', '.job-info .location',
        '[data-automation="job-location"]', '.job-details .location',
        '.job-meta .location', 'span.location', '.listing-location'
    ]
    
    location = extract_with_multiple_selectors(soup, selectors)
    if location:
        # Clean location text
        location = re.sub(r'^\s*location\s*:\s*', '', location, flags=re.IGNORECASE)
        # Remove office address prefixes
        location = re.sub(r'^\s*office\s+address\s*', '', location, flags=re.IGNORECASE)
        return location.strip()
    
    return None

def extract_job_type(soup):
    """Extract job type with multiple strategies"""
    selectors = [
        '.job-type', '.employment-type', '.job-info .type',
        '[data-automation="job-type"]', '.job-meta .type',
        'span.job-type', '.listing-job-type'
    ]
    
    job_type = extract_with_multiple_selectors(soup, selectors)
    if job_type:
        # Clean job type text
        job_type = re.sub(r'^\s*job\s+type\s*:\s*', '', job_type, flags=re.IGNORECASE)
        return job_type.strip()
    
    # Try to find job type in the text
    job_types = ['full-time', 'part-time', 'contract', 'temporary', 'internship', 'freelance', 'remote']
    text = soup.get_text().lower()
    found_types = []
    
    for jt in job_types:
        # Look for job type surrounded by spaces or punctuation
        if re.search(r'[^\w]' + jt + r'[^\w]', text):
            found_types.append(jt.title())
    
    if found_types:
        return ', '.join(found_types)
    
    return None

def clean_text(text):
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