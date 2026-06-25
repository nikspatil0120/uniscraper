"""
Google Vertex AI Service

Replaces standard Gemini API with Vertex AI for better quotas and reliability.

Setup:
1. Get service account JSON from Google Cloud
2. Place in credentials/vertex-key.json
3. Set GOOGLE_APPLICATION_CREDENTIALS and VERTEX_PROJECT_ID in .env
"""
import os
import json
import logging
from typing import Optional, Dict, Any

from config import settings

logger = logging.getLogger(__name__)

# Try to import Vertex AI
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    logger.warning("Vertex AI not installed. Run: pip install google-cloud-aiplatform")


class VertexAIService:
    """
    Wrapper for Google Vertex AI Gemini models.
    
    Falls back to standard Gemini API if Vertex is not configured.
    """
    
    def __init__(self):
        self.initialized = False
        self.model = None
        self.project_id = None
        self.location = settings.vertex_location
        
        # Check if Vertex is configured
        if VERTEX_AVAILABLE and settings.vertex_enabled:
            self._init_vertex()
    
    def _init_vertex(self):
        """Initialize Vertex AI with service account credentials."""
        try:
            # Get configuration from settings
            self.project_id = settings.vertex_project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
            credentials_path = settings.google_application_credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            if not self.project_id:
                logger.warning("VERTEX_PROJECT_ID not set. Vertex AI disabled.")
                return
            
            if credentials_path and not os.path.exists(credentials_path):
                logger.warning(f"Credentials file not found: {credentials_path}")
                return
            
            # Initialize Vertex AI
            vertexai.init(
                project=self.project_id,
                location=self.location
            )
            
            # Create model instance - use model from settings
            self.model = GenerativeModel(settings.vertex_model)
            
            self.initialized = True
            logger.info(f"✅ Vertex AI initialized (project: {self.project_id}, model: {settings.vertex_model}, location: {self.location})")
        
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            self.initialized = False
    
    def is_available(self) -> bool:
        """Check if Vertex AI is available and configured."""
        return VERTEX_AVAILABLE and self.initialized
    
    def generate_content(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_output_tokens: int = 8192,
        **kwargs
    ) -> str:
        """
        Generate content using Vertex AI Gemini.
        
        Args:
            prompt: The prompt text
            temperature: Sampling temperature (0.0-1.0)
            max_output_tokens: Maximum tokens to generate
        
        Returns:
            Generated text response
        
        Raises:
            Exception if Vertex AI is not available or generation fails
        """
        if not self.is_available():
            raise Exception("Vertex AI not available. Check configuration.")
        
        try:
            # Generation configuration
            config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_p=0.95,
                top_k=40,
            )
            
            # Generate content
            response = self.model.generate_content(
                prompt,
                generation_config=config
            )
            
            return response.text
        
        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}")
            raise
    
    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_output_tokens: int = 8192
    ) -> Dict[str, Any]:
        """
        Generate JSON response using Vertex AI.
        
        Args:
            prompt: The prompt text (should request JSON output)
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens to generate
        
        Returns:
            Parsed JSON dict
        
        Raises:
            Exception if generation or parsing fails
        """
        text = self.generate_content(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            return json.loads(text)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {text[:500]}")
            raise


# Global instance
_vertex_service = None


def get_vertex_service() -> VertexAIService:
    """Get or create global Vertex AI service instance."""
    global _vertex_service
    if _vertex_service is None:
        _vertex_service = VertexAIService()
    return _vertex_service


# Convenience functions
def generate(prompt: str, **kwargs) -> str:
    """Generate text using Vertex AI."""
    service = get_vertex_service()
    return service.generate_content(prompt, **kwargs)


def generate_json(prompt: str, **kwargs) -> Dict[str, Any]:
    """Generate JSON using Vertex AI."""
    service = get_vertex_service()
    return service.generate_json(prompt, **kwargs)


def is_vertex_available() -> bool:
    """Check if Vertex AI is configured and available."""
    service = get_vertex_service()
    return service.is_available()
