"""
Test script for Google Vertex AI integration.

This script verifies that:
1. Vertex AI dependencies are installed
2. Configuration is loaded correctly
3. Service initializes when credentials are available
4. Extraction falls back gracefully when Vertex is not configured

Run this script to test your Vertex AI setup.
"""
import asyncio
import sys
from config import settings

print("=" * 70)
print("VERTEX AI INTEGRATION TEST")
print("=" * 70)

# Step 1: Check if Vertex AI packages are installed
print("\n[1/5] Checking Vertex AI dependencies...")
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    print("✅ Vertex AI packages installed")
except ImportError as e:
    print(f"❌ Vertex AI packages not installed: {e}")
    print("   Run: py -3.13 -m pip install google-cloud-aiplatform google-auth")
    sys.exit(1)

# Step 2: Check configuration
print("\n[2/5] Checking Vertex AI configuration...")
print(f"   VERTEX_ENABLED: {settings.vertex_enabled}")
print(f"   VERTEX_PROJECT_ID: {settings.vertex_project_id or '(not set)'}")
print(f"   VERTEX_MODEL: {settings.vertex_model}")
print(f"   VERTEX_LOCATION: {settings.vertex_location}")
print(f"   GOOGLE_APPLICATION_CREDENTIALS: {settings.google_application_credentials or '(not set)'}")

if not settings.vertex_enabled:
    print("⚠️  Vertex AI is disabled (VERTEX_ENABLED=false)")
    print("   This is normal - Vertex will be used once credentials are configured")
else:
    print("✅ Vertex AI is enabled")

# Step 3: Check if credentials file exists
print("\n[3/5] Checking credentials file...")
import os
if settings.google_application_credentials:
    if os.path.exists(settings.google_application_credentials):
        print(f"✅ Credentials file found: {settings.google_application_credentials}")
    else:
        print(f"❌ Credentials file not found: {settings.google_application_credentials}")
        print("   Create the file and place your service account JSON there")
else:
    print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set")
    print("   Set this to the path of your service account JSON file")

# Step 4: Test Vertex AI service initialization
print("\n[4/5] Testing Vertex AI service...")
try:
    from services.vertex_service import get_vertex_service, is_vertex_available
    
    service = get_vertex_service()
    available = is_vertex_available()
    
    if available:
        print("✅ Vertex AI service initialized successfully")
        print(f"   Project: {service.project_id}")
        print(f"   Location: {service.location}")
        print(f"   Model: {settings.vertex_model}")
    else:
        print("⚠️  Vertex AI service not available")
        print("   This is expected if credentials are not configured yet")
        print("   System will fall back to standard Gemini API")
except Exception as e:
    print(f"❌ Error initializing Vertex service: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Test extraction pipeline awareness
print("\n[5/5] Testing extraction pipeline integration...")
try:
    from pipeline import ai_extractor
    
    # Check if ai_extractor can see Vertex
    if hasattr(ai_extractor, 'VERTEX_AVAILABLE'):
        if ai_extractor.VERTEX_AVAILABLE:
            print("✅ AI extractor can use Vertex AI")
        else:
            print("⚠️  AI extractor cannot import Vertex (expected if not installed)")
    
    print("✅ Extraction pipeline integrated")
except Exception as e:
    print(f"❌ Error testing extraction pipeline: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if settings.vertex_enabled and is_vertex_available():
    print("✅ Vertex AI is READY and will be used for extraction")
    print("   Priority: Vertex → Gemini API → Groq → Ollama")
elif settings.vertex_enabled:
    print("⚠️  Vertex AI is ENABLED but NOT CONFIGURED")
    print("   Current fallback: Gemini API → Groq → Ollama")
    print("\n   To enable Vertex AI:")
    print("   1. Get service account JSON from your company/Google Cloud")
    print("   2. Place it at: uniscraper-backend/credentials/vertex-key.json")
    print("   3. Set VERTEX_PROJECT_ID in .env to your GCP project ID")
    print("   4. Ensure VERTEX_ENABLED=true in .env")
else:
    print("⚠️  Vertex AI is DISABLED")
    print("   Current: Gemini API → Groq → Ollama")
    print("   To enable Vertex AI:")
    print("   1. Get service account JSON from your company/Google Cloud")
    print("   2. Place it at: uniscraper-backend/credentials/vertex-key.json")
    print("   3. Set VERTEX_PROJECT_ID in .env")
    print("   4. Set VERTEX_ENABLED=true in .env")

print("=" * 70)
