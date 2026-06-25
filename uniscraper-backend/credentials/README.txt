VERTEX AI CREDENTIALS FOLDER
============================

This folder should contain your Google Cloud service account JSON key file.

SETUP INSTRUCTIONS:
-------------------

1. Get the service account JSON file from:
   - Your company/reviewers (they will provide the account)
   - OR create one yourself in Google Cloud Console:
     a. Go to https://console.cloud.google.com
     b. Select your project
     c. Navigate to: IAM & Admin → Service Accounts
     d. Create Service Account → Add "Vertex AI User" role
     e. Generate JSON key

2. Place the JSON file here as:
   vertex-key.json

3. Update your .env file:
   VERTEX_PROJECT_ID=your-gcp-project-id
   VERTEX_ENABLED=true
   GOOGLE_APPLICATION_CREDENTIALS=C:\Projects\uniscrape\uniscraper-backend\credentials\vertex-key.json

4. Run test:
   py -3.13 test_vertex_integration.py

SECURITY:
---------
- DO NOT commit vertex-key.json to git
- The .gitignore already excludes this folder
- Keep credentials secure and private

FILE STRUCTURE:
---------------
credentials/
  ├── README.txt (this file)
  └── vertex-key.json (place your service account JSON here)
