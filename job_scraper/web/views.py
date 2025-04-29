from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from scraper.models import JobData
from scraper.forms import CustomScraperForm

def index(request):
    """Home page view"""
    # Get latest 5 jobs
    latest_jobs = JobData.objects.all().order_by('-datePosted')[:5]
    
    # Count total jobs
    total_jobs = JobData.objects.count()
    
    context = {
        'latest_jobs': latest_jobs,
        'total_jobs': total_jobs,
    }
    
    return render(request, 'web/index.html', context)

def job_list(request):
    """List all jobs with pagination"""
    # Get all jobs
    jobs = JobData.objects.all().order_by('-datePosted')
    
    # Filter by search query if provided
    query = request.GET.get('q')
    if query:
        jobs = jobs.filter(
            Q(jobTitle__icontains=query) | 
            Q(company__icontains=query) | 
            Q(jobLocation__icontains=query) |
            Q(jobCategory__icontains=query) |
            Q(jobIndustry__icontains=query)
        )
    
    # Paginate results
    paginator = Paginator(jobs, 20)  # 20 jobs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'web/jobs.html', {'page_obj': page_obj, 'query': query})

def job_detail(request, job_id):
    """Show details for a specific job"""
    job = get_object_or_404(JobData, id=job_id)
    
    # Get skills and benefits
    skills = []
    if job.skill:
        for i in range(1, 15):
            skill = getattr(job.skill, f'skill_{i}', None)
            if skill:
                skills.append(skill)
    
    benefits = []
    if job.benefit:
        for i in range(1, 15):
            benefit = getattr(job.benefit, f'benefit_{i}', None)
            if benefit:
                benefits.append(benefit)
    
    context = {
        'job': job,
        'skills': skills,
        'benefits': benefits,
    }
    
    return render(request, 'web/job_detail.html', context)

def search(request):
    """Search for jobs"""
    query = request.GET.get('q', '')
    
    if query:
        # Redirect to job list with the query parameter
        return redirect(f'/jobs/?q={query}')
    
    return render(request, 'web/search.html')

def custom_search(request):
    """Custom search form for initiating scraping"""
    if request.method == 'POST':
        form = CustomScraperForm(request.POST)
        if form.is_valid():
            search_term = form.cleaned_data['search_term']
            
            # Redirect to the run custom scraper view
            return redirect('scraper:run_custom_scraper')
    else:
        form = CustomScraperForm()
    
    return render(request, 'web/custom_search.html', {'form': form})

def debug_paths(request):
    """Debug view to check paths"""
    import os
    from django.conf import settings
    from django.http import HttpResponse
    
    base_dir = settings.BASE_DIR
    csv_file_dir = settings.CSV_FILE_DIR
    jobtitles_file = os.path.join(csv_file_dir, 'jobtitlestosearch.csv')
    
    # Check for file existence
    jobtitles_exists = os.path.exists(jobtitles_file)
    
    # List all files in the directory
    try:
        dir_contents = os.listdir(csv_file_dir)
    except Exception as e:
        dir_contents = f"Error listing directory: {str(e)}"
    
    response = f"""
    BASE_DIR: {base_dir}
    CSV_FILE_DIR: {csv_file_dir}
    jobtitles_file: {jobtitles_file}
    jobtitles_file exists: {jobtitles_exists}
    
    Directory contents:
    {dir_contents}
    """
    
    return HttpResponse(response, content_type='text/plain')