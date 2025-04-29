from django.urls import path
from . import views

app_name = 'scraper'

urlpatterns = [
    path('run/', views.run_scraper, name='run_scraper'),
    path('run/custom/', views.run_custom_scraper, name='run_custom_scraper'),
    path('status/', views.scraper_status, name='scraper_status'),
    path('export/', views.export_data, name='export_data'),
]