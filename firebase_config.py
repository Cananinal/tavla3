import os
import base64
import json
import firebase_admin  # EKLENDİ
from firebase_admin import credentials, initialize_app, firestore

class FirebaseConfig:
    def __init__(self):
        encoded = os.environ.get("GOOGLE_CREDS_BASE64")
        if not encoded:
            raise ValueError("GOOGLE_CREDS_BASE64 environment variable not found.")
        decoded = base64.b64decode(encoded)
        json_data = json.loads(decoded)
        cred = credentials.Certificate(json_data)

        # 🔧 initialize_app sadece bir kez çağrılmalı
        if not firebase_admin._apps:
            initialize_app(cred)

        self.db = firestore.client()

    def get_user(self, username):
        doc_ref = self.db.collection("users").document(username)
        return doc_ref.get()

    def save_user(self, username, data):
        doc_ref = self.db.collection("users").document(username)
        doc_ref.set(data)
