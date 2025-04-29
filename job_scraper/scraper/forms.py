from django import forms

class CustomScraperForm(forms.Form):
    search_term = forms.CharField(
        max_length=100, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter job title to search'})
    )