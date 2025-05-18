import firebase_admin
from firebase_admin import credentials, firestore, db
import os

class FirebaseConfig:
    def __init__(self):
        # Admin SDK ile Firebase'e bağlanma
        cred_path = os.path.join(os.path.dirname(__file__), 'tavla-8d2ce-firebase-adminsdk-fbsvc-88ccd45de2.json')
        cred = credentials.Certificate(cred_path)
        
        # Firebase uygulamasını başlat 
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://tavla-8d2ce-default-rtdb.europe-west1.firebasedatabase.app/'
        })
        
        # Firestore ve Realtime Database referansları
        self.firestore_db = firestore.client()
        self.realtime_db = db.reference()
    
    # Firestore yardımcı fonksiyonları (kullanıcılar için)
    def get_user(self, username):
        return self.firestore_db.collection('users').document(username).get()
    
    def create_user(self, username, password_hash):
        return self.firestore_db.collection('users').document(username).set({
            'username': username,
            'password': password_hash
        })
    
    # Realtime Database yardımcı fonksiyonları (oyunlar için)
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
