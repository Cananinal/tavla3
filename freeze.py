import firebase_admin
from firebase_admin import credentials, firestore, db
import pyrebase
import os
import json

class FirebaseConfig:
    def __init__(self):
        # Admin SDK ile Firebase'e bağlanma (sunucu taraflı işlemler için)
        cred_path = os.path.join(os.path.dirname(__file__), 'firebase-credentials.json')
        cred = credentials.Certificate(cred_path)
        
        # Firebase uygulamasını başlat
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://SIZIN-PROJE-ID.firebaseio.com'
        })
        
        # Firestore ve Realtime Database referansları
        self.firestore_db = firestore.client()
        self.realtime_db = db.reference()
        
        # PyreBase yapılandırması (client taraflı işlemler için)
        self.firebase_config = {
            "apiKey": "YOUR_API_KEY",
            "authDomain": "YOUR_PROJECT_ID.firebaseapp.com",
            "databaseURL": "https://YOUR_PROJECT_ID.firebaseio.com",
            "projectId": "YOUR_PROJECT_ID",
            "storageBucket": "YOUR_PROJECT_ID.appspot.com",
            "messagingSenderId": "YOUR_MESSAGING_SENDER_ID",
            "appId": "YOUR_APP_ID"
        }
        
        self.firebase = pyrebase.initialize_app(self.firebase_config)
        self.auth = self.firebase.auth()

    # Firestore yardımcı fonksiyonları
    def get_user(self, username):
        return self.firestore_db.collection('users').document(username).get()
    
    def create_user(self, username, password_hash):
        return self.firestore_db.collection('users').document(username).set({
            'username': username,
            'password': password_hash
        })
    
    # Realtime Database yardımcı fonksiyonları
    def create_game(self, game_id, game_data):
        self.realtime_db.child('games').child(game_id).set(game_data)
    
    def update_game(self, game_id, updates):
        self.realtime_db.child('games').child(game_id).update(updates)
    
    def get_game(self, game_id):
        return self.realtime_db.child('games').child(game_id).get()
    
    def get_active_games(self):
        return self.realtime_db.child('games').get()
    
    def delete_game(self, game_id):
        self.realtime_db.child('games').child(game_id).delete()