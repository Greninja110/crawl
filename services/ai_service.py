"""
AI service for processing raw content using LLMs
"""
import json
import logging
import re
import os
import time
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
from models import get_db
from models.raw_content import get_raw_content_by_id, update_raw_content_processing_status
from models.ai_processing_job import (
    get_ai_processing_job_by_id, update_ai_processing_job_status,
    update_ai_processing_job_result
)
from models.admission_data import store_admission_data
from models.placement_data import store_placement_data
from models.internship_data import store_internship_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIModelManager:
    """Manager for AI models used in content processing"""
    
    def __init__(self, model_name=None, device=None):
        """
        Initialize the AI model manager
        
        Args:
            model_name: Name of the model to use
            device: Device to run the model on (cpu, cuda)
        """
        self.model_name = model_name or os.environ.get('AI_MODEL_NAME', 'microsoft/phi-2')
        self.device = device or os.environ.get('AI_MODEL_DEVICE', 'cpu')
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        self.loading_error = None
    
    def load_model(self):
        """
        Load the AI model
        
        Returns:
            Success status and message
        """
        try:
            logger.info(f"Loading model {self.model_name} on {self.device}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Load model with lower precision for memory efficiency
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                device_map=self.device
            )
            
            self.is_loaded = True
            logger.info(f"Model {self.model_name} loaded successfully")
            return True, "Model loaded successfully"
            
        except Exception as e:
            self.loading_error = str(e)
            logger.error(f"Error loading model: {str(e)}", exc_info=True)
            return False, f"Error loading model: {str(e)}"
    
    def unload_model(self):
        """
        Unload the AI model to free memory
        """
        if self.model:
            del self.model
            self.model = None
        
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        
        self.is_loaded = False
        
        # Force garbage collection
        import gc
        gc.collect()
        
        if self.device == 'cuda':
            torch.cuda.empty_cache()
    
    def is_model_loaded(self):
        """
        Check if the model is loaded
        
        Returns:
            True if model is loaded, False otherwise
        """
        return self.is_loaded
    
    def get_loading_error(self):
        """
        Get the error message if model loading failed
        
        Returns:
            Error message or None
        """
        return self.loading_error
    
    def get_model_info(self):
        """
        Get information about the loaded model
        
        Returns:
            Dictionary with model information
        """
        if not self.is_loaded:
            return {
                'name': self.model_name,
                'device': self.device,
                'loaded': False,
                'error': self.loading_error
            }
        
        return {
            'name': self.model_name,
            'device': self.device,
            'loaded': True,
            'tokenizer': self.tokenizer.__class__.__name__,
            'model_type': self.model.__class__.__name__,
            'model_parameters': sum(p.numel() for p in self.model.parameters())
        }
    
    def generate_response(self, prompt, max_length=2000, temperature=0.7, stop_sequences=None):
        """
        Generate a response from the model
        
        Args:
            prompt: Input prompt
            max_length: Maximum length of the generated response
            temperature: Temperature for generation
            stop_sequences: Sequences to stop generation at
            
        Returns:
            Generated text response
        """
        if not self.is_loaded:
            raise ValueError("Model is not loaded")
        
        # Tokenize the prompt
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                inputs.input_ids,
                max_length=max_length,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                num_return_sequences=1
            )
        
        # Decode the response
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the prompt from the response
        if response.startswith(prompt):
            response = response[len(prompt):]
        
        # Apply stop sequences if provided
        if stop_sequences:
            for stop_seq in stop_sequences:
                if stop_seq in response:
                    response = response.split(stop_seq)[0]
        
        return response.strip()

# Global model manager instance
model_manager = AIModelManager()

def process_content(job_id):
    """
    Process raw content using AI model
    
    Args:
        job_id: ID of the AI processing job
        
    Returns:
        Success status and message
    """
    db = get_db()
    
    # Get the AI processing job
    job = get_ai_processing_job_by_id(db, job_id)
    if not job:
        return False, f"AI processing job {job_id} not found"
    
    # Update job status to running
    update_ai_processing_job_status(db, job_id, 'running')
    
    try:
        # Get the raw content
        raw_content_id = job['raw_content_id']
        raw_content = get_raw_content_by_id(db, raw_content_id)
        
        if not raw_content:
            update_ai_processing_job_status(db, job_id, 'failed', f"Raw content {raw_content_id} not found")
            return False, f"Raw content {raw_content_id} not found"
        
        # Check if the model is loaded
        if not model_manager.is_model_loaded():
            success, message = model_manager.load_model()
            if not success:
                update_ai_processing_job_status(db, job_id, 'failed', f"Error loading AI model: {message}")
                return False, f"Error loading AI model: {message}"
        
        # Process the content based on its type
        content_type = raw_content['content_type']
        html_content = raw_content['content']
        college_id = raw_content['college_id']
        source_url = raw_content['url']
        
        # Get prompt for the content type
        prompt = get_prompt_for_content_type(content_type, college_id, source_url, html_content)
        
        # Generate response
        ai_response = model_manager.generate_response(
            prompt,
            max_length=4000,
            temperature=0.3,
            stop_sequences=["</RESPONSE>"]
        )
        
        # Parse the response
        parsed_data, confidence = parse_ai_response(ai_response, content_type)
        
        # Store the processed data
        result_id = store_processed_data(db, college_id, content_type, parsed_data, [source_url])
        
        if not result_id:
            update_ai_processing_job_status(db, job_id, 'failed', "Failed to store processed data")
            return False, "Failed to store processed data"
        
        # Update the AI processing job with the result
        update_ai_processing_job_result(
            db,
            job_id,
            model_manager.model_name,
            confidence,
            result_id,
            prompt,
            ai_response
        )
        
        # Update the raw content as processed
        update_raw_content_processing_status(db, raw_content_id, True)
        
        # Update job status to completed
        update_ai_processing_job_status(db, job_id, 'completed')
        
        return True, f"Content processed successfully"
        
    except Exception as e:
        # Update job status to failed
        update_ai_processing_job_status(db, job_id, 'failed', str(e))
        logger.error(f"Error processing content: {str(e)}", exc_info=True)
        return False, f"Error processing content: {str(e)}"

def get_prompt_for_content_type(content_type, college_id, source_url, html_content):
    """
    Get prompt template for a specific content type
    
    Args:
        content_type: Type of content (admission/placement/internship)
        college_id: ID of the college
        source_url: URL where content was extracted from
        html_content: Raw HTML content
        
    Returns:
        Prompt for the AI model
    """
    db = get_db()
    
    # Get college name
    college = db.colleges.find_one({'_id': college_id})
    college_name = college['name'] if college else "the college"
    
    # Clean HTML content
    clean_text = clean_html_content(html_content)
    
    # Maximum content length to avoid exceeding token limits
    max_content_length = 8000
    if len(clean_text) > max_content_length:
        clean_text = clean_text[:max_content_length] + "... [content truncated]"
    
    if content_type == 'admission':
        return f"""You are analyzing content from {college_name}'s admission webpage.

URL: {source_url}

CONTENT:
{clean_text}

Extract the following information in valid JSON format matching this schema:
{{
  "courses": [{{"name": "", "duration": "", "eligibility": "", "fee_structure": {{"tuition": "", "development": "", "other": ""}}, "seats": ""}}],
  "application_process": "",
  "important_dates": [{{"event": "", "date": ""}}],
  "hostel_facilities": {{"available": true|false, "boys_hostel": {{"fee": "", "seats": ""}}, "girls_hostel": {{"fee": "", "seats": ""}}}}
}}

Only include fields where information is definitely present in the content.
If you're uncertain about any information, mark it as null.
Ensure your response is valid JSON and nothing else.

<RESPONSE>
"""
    
    elif content_type == 'placement':
        return f"""You are analyzing content from {college_name}'s placement webpage.

URL: {source_url}

CONTENT:
{clean_text}

Extract the following information in valid JSON format matching this schema:
{{
  "academic_year": "",
  "overall_statistics": {{
    "eligible_students": "",
    "students_placed": "",
    "placement_percentage": "",
    "highest_package": "",
    "average_package": "",
    "lowest_package": ""
  }},
  "department_statistics": [{{"department": "", "statistics": {{"students_placed": "", "placement_percentage": "", "avg_package": ""}}}}],
  "recruiting_companies": [{{"name": "", "students_hired": "", "package_offered": ""}}]
}}

Only include fields where information is definitely present in the content.
If you're uncertain about any information, mark it as null.
Ensure your response is valid JSON and nothing else.

<RESPONSE>
"""
    
    elif content_type == 'internship':
        return f"""You are analyzing content from {college_name}'s internship webpage.

URL: {source_url}

CONTENT:
{clean_text}

Extract the following information in valid JSON format matching this schema:
{{
  "academic_year": "",
  "overall_statistics": {{
    "internships": "",
    "participation": ""
  }},
  "department_statistics": [{{"department": "", "participation": "", "avg_stipend": ""}}],
  "internship_companies": [{{"name": "", "students_hired": "", "stipend": ""}}]
}}

Only include fields where information is definitely present in the content.
If you're uncertain about any information, mark it as null.
Ensure your response is valid JSON and nothing else.

<RESPONSE>
"""
    
    else:  # general
        return f"""You are analyzing content from {college_name}'s webpage.

URL: {source_url}

CONTENT:
{clean_text}

Analyze this content and determine if it contains information about admissions, placements, or internships.
Extract any relevant information in valid JSON format matching this schema:
{{
  "content_type": "admission|placement|internship|general",
  "relevant_information": "",
  "key_details": {{}}
}}

Only include fields where information is definitely present in the content.
If you're uncertain about any information, mark it as null.
Ensure your response is valid JSON and nothing else.

<RESPONSE>
"""

def clean_html_content(html_content):
    """
    Clean HTML content for AI processing
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        Cleaned text content
    """
    # Parse HTML
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "meta", "link", "head"]):
        script.extract()
    
    # Extract text
    text = soup.get_text(separator='\n')
    
    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def parse_ai_response(response, content_type):
    """
    Parse the AI model's response
    
    Args:
        response: Raw response from the AI model
        content_type: Type of content that was processed
        
    Returns:
        Tuple of (parsed data, confidence score)
    """
    try:
        # Extract JSON from response
        json_match = re.search(r'({[\s\S]*})', response)
        if json_match:
            json_str = json_match.group(1)
            parsed_data = json.loads(json_str)
            
            # Calculate a simple confidence score based on how complete the data is
            confidence = calculate_confidence_score(parsed_data, content_type)
            
            return parsed_data, confidence
        else:
            return {}, 0.0
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AI response as JSON: {response}")
        return {}, 0.0

def calculate_confidence_score(data, content_type):
    """
    Calculate a confidence score for the parsed data
    
    Args:
        data: Parsed data from AI response
        content_type: Type of content that was processed
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not data:
        return 0.0
    
    # Define key fields for each content type
    if content_type == 'admission':
        key_fields = ['courses', 'application_process', 'important_dates']
        secondary_fields = ['hostel_facilities']
    elif content_type == 'placement':
        key_fields = ['overall_statistics', 'recruiting_companies']
        secondary_fields = ['department_statistics', 'academic_year']
    elif content_type == 'internship':
        key_fields = ['overall_statistics', 'internship_companies']
        secondary_fields = ['department_statistics', 'academic_year']
    else:
        key_fields = ['content_type', 'relevant_information']
        secondary_fields = ['key_details']
    
    # Count how many key fields are present and have content
    key_field_count = sum(1 for field in key_fields if field in data and data[field])
    secondary_field_count = sum(1 for field in secondary_fields if field in data and data[field])
    
    # Calculate score
    key_weight = 0.8  # Weight for key fields
    secondary_weight = 0.2  # Weight for secondary fields
    
    key_score = key_field_count / len(key_fields) if key_fields else 0
    secondary_score = secondary_field_count / len(secondary_fields) if secondary_fields else 0
    
    score = (key_score * key_weight) + (secondary_score * secondary_weight)
    
    return score

def store_processed_data(db, college_id, content_type, data, source_urls):
    """
    Store processed data in the appropriate collection
    
    Args:
        db: Database connection
        college_id: ID of the college
        content_type: Type of content (admission/placement/internship)
        data: Processed data
        source_urls: List of source URLs
        
    Returns:
        ID of the created/updated document
    """
    try:
        if content_type == 'admission':
            # Extract fields from data
            courses = data.get('courses', [])
            application_process = data.get('application_process')
            important_dates = data.get('important_dates', [])
            hostel_facilities = data.get('hostel_facilities', {})
            
            # Store in admission_data collection
            return store_admission_data(
                db, college_id, source_urls, courses, application_process, 
                important_dates, hostel_facilities
            )
            
        elif content_type == 'placement':
            # Extract fields from data
            academic_year = data.get('academic_year')
            overall_statistics = data.get('overall_statistics', {})
            department_statistics = data.get('department_statistics', [])
            recruiting_companies = data.get('recruiting_companies', [])
            
            # Store in placement_data collection
            return store_placement_data(
                db, college_id, source_urls, academic_year, overall_statistics,
                department_statistics, recruiting_companies
            )
            
        elif content_type == 'internship':
            # Extract fields from data
            academic_year = data.get('academic_year')
            overall_statistics = data.get('overall_statistics', {})
            department_statistics = data.get('department_statistics', [])
            internship_companies = data.get('internship_companies', [])
            
            # Store in internship_data collection
            return store_internship_data(
                db, college_id, source_urls, academic_year, overall_statistics,
                department_statistics, internship_companies
            )
            
        else:
            # For general content, determine where to store based on detected content_type
            detected_type = data.get('content_type', 'general')
            
            if detected_type == 'admission':
                return store_admission_data(
                    db, college_id, source_urls, [], data.get('relevant_information')
                )
            elif detected_type == 'placement':
                return store_placement_data(
                    db, college_id, source_urls, None, {'description': data.get('relevant_information')}
                )
            elif detected_type == 'internship':
                return store_internship_data(
                    db, college_id, source_urls, None, {'description': data.get('relevant_information')}
                )
            
            # For truly general content, don't store anything
            return None
            
    except Exception as e:
        logger.error(f"Error storing processed data: {str(e)}", exc_info=True)
        return None

def get_model_status():
    """
    Get the status of the AI model
    
    Returns:
        Dictionary with model status information
    """
    return model_manager.get_model_info()

def load_ai_model():
    """
    Load the AI model
    
    Returns:
        Success status and message
    """
    return model_manager.load_model()

def unload_ai_model():
    """
    Unload the AI model
    
    Returns:
        Success status and message
    """
    if not model_manager.is_model_loaded():
        return False, "Model is not loaded"
    
    try:
        model_manager.unload_model()
        return True, "Model unloaded successfully"
    except Exception as e:
        return False, f"Error unloading model: {str(e)}"