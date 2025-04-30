# CREATE this new file at scraper/management/commands/reprocess_html.py

from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import random
from bs4 import BeautifulSoup
from ...models import ScrapedHTML
from ...scrapers.job_description import JobDescription

class Command(BaseCommand):
    help = 'Reprocess stored HTML that failed extraction'
    
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100,
                            help='Maximum number of HTML records to process')
        parser.add_argument('--domain', type=str, default=None,
                            help='Optional domain to filter by')
        
    def handle(self, *args, **options):
        # Get unprocessed HTML records
        query = ScrapedHTML.objects.filter(processing_success=False)
        
        if options['domain']:
            query = query.filter(source_domain__contains=options['domain'])
            
        records = query.order_by('-scraped_at')[:options['limit']]
        
        # Initialize job description processor
        job_processor = JobDescription()
        
        total = records.count()
        self.stdout.write(f"Reprocessing {total} HTML records")
        
        for i, record in enumerate(records, 1):
            self.stdout.write(f"[{i}/{total}] Processing {record.url}")
            
            try:
                # Parse the stored HTML
                soup = BeautifulSoup(record.html_content, 'html.parser')
                
                # Extract job data
                job_data = job_processor._extract_job_data(
                    soup, 
                    "", # We'll rely on robust selectors instead of domain-specific ones
                    record.url, 
                    None # No domain config, use defaults
                )
                
                if job_data:
                    # Clean the data
                    job_data = job_processor._clean_job_data(job_data)
                    
                    # Save the job data
                    if 'jobTitle' in job_data and job_data['jobTitle']:
                        success = job_processor.job_data.save_job(job_data)
                        if success:
                            record.processing_success = True
                            record.last_processed = timezone.now()
                            record.save()
                            self.stdout.write(self.style.SUCCESS(f"  Success: {job_data.get('jobTitle')}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"  Failed to save job data"))
                    else:
                        self.stdout.write(self.style.ERROR(f"  No job title extracted"))
                else:
                    self.stdout.write(self.style.ERROR(f"  Failed to extract job data"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error processing record: {str(e)}"))
            
            # Add a small delay between processing
            time.sleep(random.uniform(0.1, 0.5))