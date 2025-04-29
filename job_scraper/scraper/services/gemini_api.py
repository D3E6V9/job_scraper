import google.generativeai as genai
from django.conf import settings

class GeminiClient:
    """Client for interacting with the Gemini AI API"""
    
    def __init__(self):
        """Initialize the Gemini client"""
        # Configure the Gemini API with the key from settings
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.initialized = True
        except Exception as e:
            print(f"Failed to initialize Gemini API: {str(e)}")
            self.initialized = False
    
    def extract_job_data(self, job_description):
        """Extract structured job data from a job description"""
        if not self.initialized:
            return {}
        
        prompt = f"""
        Extract the following information from this job description:
        1. Skills required (list up to 14)
        2. Benefits offered (list up to 14)
        3. Job category
        4. Industry
        5. Education requirements
        6. Experience requirements
        7. Job Type (full-time, part-time, contract, etc.)
        
        Return the results in a structured format like this:
        Skills: skill1, skill2, ...
        Benefits: benefit1, benefit2, ...
        Category: category
        Industry: industry
        Education: education requirement
        Experience: experience requirement
        Job Type: job type
        
        Here's the job description:
        {job_description}
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error calling Gemini API: {str(e)}")
            return ""