import os
import base64
import json
from firebase_admin import credentials, initialize_app

class FirebaseConfig:
    def __init__(self):
        encoded = os.environ.get("GOOGLE_CREDS_BASE64")
        if not encoded:
            raise ValueError("GOOGLE_CREDS_BASE64 environment variable not found.")
        decoded = base64.b64decode(encoded)
        json_data = json.loads(decoded)
        cred = credentials.Certificate(json_data)
        initialize_app(cred)
