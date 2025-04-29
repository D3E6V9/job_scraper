import time
import threading
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.conf import settings
import pandas as pd
import csv
import os
from datetime import datetime

from .models import JobData, Skill, Benefit
from .scrapers.query_search import QuerySearch
from .forms import CustomScraperForm

# Global variable to track scraper status
scraper_running = False
scraper_progress = 0
scraper_total = 0
scraper_current_job = ""

def run_scraper(request):
    """Run the predefined job title scraper"""
    global scraper_running, scraper_progress, scraper_total, scraper_current_job
    
    if scraper_running:
        messages.warning(request, "A scraper is already running. Please wait until it completes.")
        return redirect('web:index')
    
    # Read predefined job titles from CSV
    job_titles_file = os.path.join(settings.CSV_FILE_DIR, 'jobtitlestosearch.csv')
    try:
        job_titles_df = pd.read_csv(job_titles_file)
        job_titles = job_titles_df['job_title'].tolist()
    except Exception as e:
        messages.error(request, f"Error reading job titles file: {str(e)}")
        return redirect('web:index')
    
    scraper_running = True
    scraper_progress = 0
    scraper_total = len(job_titles)
    
    # Start scraper in a separate thread
    thread = threading.Thread(target=run_scraper_task, args=(job_titles,))
    thread.daemon = True
    thread.start()
    
    messages.success(request, f"Scraper started for {len(job_titles)} predefined job titles.")
    return redirect('web:index')

def run_custom_scraper(request):
    """Run the scraper with custom search terms"""
    global scraper_running, scraper_progress, scraper_total, scraper_current_job
    
    if scraper_running:
        messages.warning(request, "A scraper is already running. Please wait until it completes.")
        return redirect('web:index')
    
    if request.method == 'POST':
        form = CustomScraperForm(request.POST)
        if form.is_valid():
            search_term = form.cleaned_data['search_term']
            
            scraper_running = True
            scraper_progress = 0
            scraper_total = 1
            scraper_current_job = search_term
            
            # Start scraper in a separate thread
            thread = threading.Thread(target=run_scraper_task, args=([search_term],))
            thread.daemon = True
            thread.start()
            
            messages.success(request, f"Scraper started for custom search: {search_term}")
            return redirect('web:index')
    else:
        form = CustomScraperForm()
    
    return render(request, 'web/custom_search.html', {'form': form})

def run_scraper_task(job_titles):
    """Background task to run the scraper"""
    global scraper_running, scraper_progress, scraper_total, scraper_current_job
    
    try:
        scraper = QuerySearch()
        
        for i, job_title in enumerate(job_titles):
            scraper_current_job = job_title
            scraper_progress = i
            
            # Run the scraper for this job title
            scraper.search(job_title)
            
            # Sleep to prevent rate limiting
            time.sleep(2)
    
    except Exception as e:
        print(f"Scraper error: {str(e)}")
    
    finally:
        scraper_running = False
        scraper_current_job = ""

def scraper_status(request):
    """Return the current status of the scraper as JSON"""
    global scraper_running, scraper_progress, scraper_total, scraper_current_job
    
    return JsonResponse({
        'running': scraper_running,
        'progress': scraper_progress,
        'total': scraper_total,
        'current_job': scraper_current_job,
        'percentage': int((scraper_progress / max(scraper_total, 1)) * 100)
    })

def export_data(request):
    """Export job data to Excel file"""
    # Get all job data
    jobs = JobData.objects.all().select_related('skill', 'benefit')
    
    # Create a DataFrame with job data
    data = []
    for job in jobs:
        job_data = {
            'Job Title': job.jobTitle,
            'Company': job.company,
            'Location': job.jobLocation,
            'Category': job.jobCategory,
            'Industry': job.jobIndustry,
            'Type': job.jobType,
            'Salary': job.salary,
            'Education': job.education,
            'Experience': job.experience,
            'Deadline': job.deadline,
            'Date Posted': job.datePosted,
            'Link': job.link,
        }
        
        # Add skills
        if job.skill:
            for i in range(1, 15):
                skill_value = getattr(job.skill, f'skill_{i}', None)
                if skill_value:
                    job_data[f'Skill {i}'] = skill_value
        
        # Add benefits
        if job.benefit:
            for i in range(1, 15):
                benefit_value = getattr(job.benefit, f'benefit_{i}', None)
                if benefit_value:
                    job_data[f'Benefit {i}'] = benefit_value
        
        data.append(job_data)
    
    # Create DataFrame and export to Excel
    df = pd.DataFrame(data)
    
    # Create response with Excel file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'job_data_{timestamp}.xlsx'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write DataFrame to Excel
    df.to_excel(response, index=False, engine='openpyxl')
    
    return response