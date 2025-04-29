from django.contrib import admin
from .models import JobData, Skill, Benefit

@admin.register(JobData)
class JobDataAdmin(admin.ModelAdmin):
    list_display = ('jobTitle', 'company', 'jobLocation', 'datePosted', 'link')
    list_filter = ('jobCategory', 'jobIndustry', 'jobType')
    search_fields = ('jobTitle', 'company', 'jobLocation')
    date_hierarchy = 'datePosted'

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('id',) + tuple(f'skill_{i}' for i in range(1, 15))
    search_fields = tuple(f'skill_{i}' for i in range(1, 15))

@admin.register(Benefit)
class BenefitAdmin(admin.ModelAdmin):
    list_display = ('id',) + tuple(f'benefit_{i}' for i in range(1, 15))
    search_fields = tuple(f'benefit_{i}' for i in range(1, 15))