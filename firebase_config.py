import os
import base64
import json
import firebase_admin
from firebase_admin import credentials, firestore, db

class FirebaseConfig:
    def __init__(self):
        encoded = os.environ.get("GOOGLE_CREDS_BASE64")
        if not encoded:
            raise ValueError("GOOGLE_CREDS_BASE64 environment variable not found.")

        # Base64 çöz ve JSON olarak oku
        decoded = base64.b64decode(encoded)
        json_data = json.loads(decoded)

        # Firebase başlat
        cred = credentials.Certificate(json_data)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'databaseURL': f"https://{json_data['project_id']}.firebaseio.com"
            })

        # Firestore ve RTDB bağlantıları
        self.firestore_db = firestore.client()
        self.realtime_db = db.reference()
    
    def get_firestore(self):
        return self.firestore_db
    
    def get_realtime(self):
        return self.realtime_db
