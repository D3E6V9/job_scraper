from django.db import models

class Skill(models.Model):
    skill_1 = models.CharField(max_length=255, blank=True, null=True)
    skill_2 = models.CharField(max_length=255, blank=True, null=True)
    skill_3 = models.CharField(max_length=255, blank=True, null=True)
    skill_4 = models.CharField(max_length=255, blank=True, null=True)
    skill_5 = models.CharField(max_length=255, blank=True, null=True)
    skill_6 = models.CharField(max_length=255, blank=True, null=True)
    skill_7 = models.CharField(max_length=255, blank=True, null=True)
    skill_8 = models.CharField(max_length=255, blank=True, null=True)
    skill_9 = models.CharField(max_length=255, blank=True, null=True)
    skill_10 = models.CharField(max_length=255, blank=True, null=True)
    skill_11 = models.CharField(max_length=255, blank=True, null=True)
    skill_12 = models.CharField(max_length=255, blank=True, null=True)
    skill_13 = models.CharField(max_length=255, blank=True, null=True)
    skill_14 = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        skills = [getattr(self, f'skill_{i}', None) for i in range(1, 15)]
        return ', '.join([s for s in skills if s])

class Benefit(models.Model):
    benefit_1 = models.CharField(max_length=255, blank=True, null=True)
    benefit_2 = models.CharField(max_length=255, blank=True, null=True)
    benefit_3 = models.CharField(max_length=255, blank=True, null=True)
    benefit_4 = models.CharField(max_length=255, blank=True, null=True)
    benefit_5 = models.CharField(max_length=255, blank=True, null=True)
    benefit_6 = models.CharField(max_length=255, blank=True, null=True)
    benefit_7 = models.CharField(max_length=255, blank=True, null=True)
    benefit_8 = models.CharField(max_length=255, blank=True, null=True)
    benefit_9 = models.CharField(max_length=255, blank=True, null=True)
    benefit_10 = models.CharField(max_length=255, blank=True, null=True)
    benefit_11 = models.CharField(max_length=255, blank=True, null=True)
    benefit_12 = models.CharField(max_length=255, blank=True, null=True)
    benefit_13 = models.CharField(max_length=255, blank=True, null=True)
    benefit_14 = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        benefits = [getattr(self, f'benefit_{i}', None) for i in range(1, 15)]
        return ', '.join([b for b in benefits if b])

class JobData(models.Model):
    jobTitle = models.CharField(max_length=255)
    jobCategory = models.CharField(max_length=255, blank=True, null=True)
    jobIndustry = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    vacancy = models.CharField(max_length=50, blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    experience = models.CharField(max_length=255, blank=True, null=True)
    jobLocation = models.CharField(max_length=255, blank=True, null=True)
    jobType = models.CharField(max_length=100, blank=True, null=True)
    deadline = models.CharField(max_length=100, blank=True, null=True)
    datePosted = models.DateTimeField(auto_now_add=True)
    salary = models.CharField(max_length=255, blank=True, null=True)
    link = models.URLField(max_length=500)
    entered_at = models.DateTimeField(auto_now_add=True)
    
    # Foreign keys to related models
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, null=True, blank=True)
    benefit = models.ForeignKey(Benefit, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.jobTitle} at {self.company}" if self.company else self.jobTitle

    class Meta:
        ordering = ['-datePosted']
        verbose_name = 'Job Data'
        verbose_name_plural = 'Job Data'

# ADD this new model after the existing models in scraper/models.py

class ScrapedHTML(models.Model):
    url = models.URLField(unique=True)
    html_content = models.TextField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    last_processed = models.DateTimeField(null=True, blank=True)
    processing_success = models.BooleanField(default=False)
    source_domain = models.CharField(max_length=255)
    
    def __str__(self):
        return f"HTML for {self.url} ({self.scraped_at.strftime('%Y-%m-%d')})"
    
    class Meta:
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['scraped_at']),
            models.Index(fields=['processing_success']),
        ]
        verbose_name = "Scraped HTML"
        verbose_name_plural = "Scraped HTMLs"

