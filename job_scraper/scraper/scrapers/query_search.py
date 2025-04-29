import os
import time
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .job_description import JobDescription

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

class QuerySearch:
    """Class for searching job portals with specific queries"""
    
    def __init__(self):
        """Initialize the query search class"""
        # Load domain configuration from CSV
        self.domains_file = os.path.join(settings.CSV_FILE_DIR, 'domain.csv')
        try:
            self.domains_df = pd.read_csv(self.domains_file)
        except Exception as e:
            raise Exception(f"Error loading domain configuration: {str(e)}")
        
        # Initialize job description processor
        self.job_description = JobDescription()
    
    def search(self, query):
        """Search for jobs using the given query across all domains"""
        print(f"Searching for: {query}")
        
        for _, domain in self.domains_df.iterrows():
            try:
                self._search_domain(domain, query)
            except Exception as e:
                print(f"Error searching {domain['domain_link']}: {str(e)}")
    
    def _search_domain(self, domain, query):
        """Search a specific domain for the given query"""
        domain_link = domain['domain_link']
        search_link = domain['domian_search_link']
        job_link_path = domain['domain_job_link_path_from_search']
        pagination = domain['domain_pagination']
        
        # Replace search term placeholder and encode spaces properly
        search_url = search_link.replace('{searchTerm}', query.replace(' ', '+'))
        
        print(f"Searching {domain_link} for '{query}'")
        
        # Process the first page
        page = 1
        self._process_search_page(domain_link, search_url, job_link_path)
        
        # Process additional pages if pagination is supported
        if pagination == 'yes':
            while True:
                page += 1
                next_page_url = search_url + f"&page={page}"
                
                try:
                    response = get_with_retry(next_page_url)
                    if response.status_code != 200:
                        break
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    job_links = soup.select(job_link_path)
                    
                    if not job_links:
                        break
                    
                    self._process_search_page(domain_link, next_page_url, job_link_path)
                    
                except Exception as e:
                    print(f"Error processing page {page} for {domain_link}: {str(e)}")
                    break
    
    def _process_search_page(self, domain_link, search_url, job_link_path):
        """Process a search results page and extract job links"""
        try:
            response = get_with_retry(search_url)
            if response.status_code != 200:
                print(f"Error: {search_url} returned status code {response.status_code}")
                return
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # First try with CSS selector
            job_links = soup.select(job_link_path)
            
            # If no links found, try alternative approaches
            if not job_links:
                # Try to find any <a> tags with href containing "job" or "career"
                job_links = [a for a in soup.find_all('a') if a.get('href') and 
                            ('job' in a.get('href').lower() or 'career' in a.get('href').lower())]
            
            print(f"Found {len(job_links)} job links on {search_url}")
            
            for link in job_links:
                href = link.get('href')
                if href:
                    # Make sure the URL is absolute
                    job_url = urljoin(domain_link, href)
                    
                    # Process the job page
                    try:
                        self.job_description.process_job_page(job_url, domain_link)
                    except Exception as e:
                        print(f"Error processing job page {job_url}: {str(e)}")
                    
                    # Random sleep to prevent rate limiting
                    time.sleep(random.uniform(1.5, 3.5))
        
        except Exception as e:
            print(f"Error processing search page {search_url}: {str(e)}")