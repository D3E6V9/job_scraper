import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from django.conf import settings

from .job_description import JobDescription

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
        
        # Replace search term placeholder
        search_url = search_link.replace('{searchTerm}', query)
        
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
                    response = requests.get(next_page_url, timeout=30)
                    if response.status_code != 200:
                        break
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    job_links = soup.select(job_link_path)
                    
                    if not job_links:
                        break
                    
                    self._process_search_page(domain_link, next_page_url, job_link_path)
                    
                    # Sleep to prevent rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"Error processing page {page} for {domain_link}: {str(e)}")
                    break
    
    def _process_search_page(self, domain_link, search_url, job_link_path):
        """Process a search results page and extract job links"""
        try:
            response = requests.get(search_url, timeout=30)
            if response.status_code != 200:
                print(f"Error: {search_url} returned status code {response.status_code}")
                return
            
            soup = BeautifulSoup(response.text, 'html.parser')
            job_links = soup.select(job_link_path)
            
            print(f"Found {len(job_links)} job links on {search_url}")
            
            for link in job_links:
                href = link.get('href')
                if href:
                    # Make sure the URL is absolute
                    job_url = urljoin(domain_link, href)
                    
                    # Process the job page
                    self.job_description.process_job_page(job_url, domain_link)
                    
                    # Sleep to prevent rate limiting
                    time.sleep(1)
        
        except Exception as e:
            print(f"Error processing search page {search_url}: {str(e)}")