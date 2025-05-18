from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps   # <─ login_required için
import random
import json
import uuid
import copy
import time
from pygammon.core import Game
from pygammon.structures import (
    GameState, InputType, InvalidMoveCode, OutputType, Side, DieRolls
)
from pygammon.exceptions import InvalidMove, GameWon
import os
from firebase_config import FirebaseConfig
from firebase_utils import serialize_game, deserialize_game
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Firebase örneği oluşturun
firebase = FirebaseConfig()

app = Flask(__name__)
app.config["SECRET_KEY"] = "tavla-gizli-anahtar"

# Socket.IO yapılandırması
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    ping_timeout=20,
    ping_interval=5,
    async_mode='eventlet'  # Cloud Run'da eventlet kullanımı gereklidir
)

# Hafızadaki games sözlüğü (geçici olarak kullanılacak)
# Not: Firebase ile tamamen kaldırılabilir ancak geçiş için tutuyoruz
games = {}

# Kullanıcı sid eşleştirmesi
user_sid = {}
sid_user = {}

# ---------------------------------------------------------------------------
#  LOGIN REQUIRED DECORATOR  -------------------------------------------------
# ---------------------------------------------------------------------------

def login_required(view):
    """Her istekte oturum var mı kontrol et. Yoksa /login'e yönlendir."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapper

# ---------------------------------------------------------------------------
#  AUTH ROUTES  --------------------------------------------------------------
# ---------------------------------------------------------------------------

# GİRİŞ POST
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Kullanıcıyı bul
        user_doc = firebase.get_user(username)
        
        # Şifre kontrolü
        if user_doc.exists and check_password_hash(user_doc.to_dict()['password'], password):
            # Oturuma kullanıcı bilgilerini kaydet
            session['user_id'] = username  # Firestore'da id yerine username kullanıyoruz
            session['username'] = username
            return redirect('/')  # Ana sayfaya yönlendir
        
        return render_template('login.html', error='Geçersiz kullanıcı adı veya şifre')
    else:
        return render_template('login.html')

# KAYIT POST
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Kullanıcı adını kontrol et
        user_doc = firebase.get_user(username)
        if user_doc.exists:
            return render_template('register.html', error='Kullanıcı adı zaten mevcut')
        
        # Şifreyi güvenli şekilde hashle
        hashed_password = generate_password_hash(password)
        
        # Yeni kullanıcı oluştur
        firebase.create_user(username, hashed_password)
        
        return redirect('/login')
    else:
        return render_template('register.html')

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------------------------------------------------------------------
#  MAIN ROUTES  --------------------------------------------------------------
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    active_games = []
    
    # Firebase'den aktif oyunları al
    games_data = firebase.get_active_games()
    
    if games_data:
        for game_id, game_info in games_data.items():
            # players içindeki aktif oyuncu sayısını hesapla
            players_data = game_info.get("players", {})
            player_count = sum(1 for p in players_data.values() 
                              if isinstance(p, dict) and p.get('side') in [0, 1])  # 0=FIRST, 1=SECOND
            
            can_join = player_count < 2
            
            active_games.append({
                'game_id': game_id,
                'players': player_count,
                'can_join': can_join,
                'status': 'Oyuncu Bekleniyor' if player_count < 2 else 'Oyun Devam Ediyor'
            })
    
    return render_template("index.html", 
                          username=session["username"], 
                          active_games=active_games)

@app.route("/oyun/<game_id>")
@login_required
def oyun(game_id):
    # Firebase'den oyun verilerini kontrol et
    game_data_fb = firebase.get_game(game_id)
    if not game_data_fb:
        return "Oyun bulunamadı", 404
    return render_template("game.html", game_id=game_id, username=session["username"])

@app.route("/aktif-oyunlar")
@login_required
def aktif_oyunlar():
    # Firebase'den aktif oyunları al
    waiting_games = []
    games_data = firebase.get_active_games()
    
    if games_data:
        for game_id, game_info in games_data.items():
            # Sadece bir oyuncusu olan ve ikinci oyuncu bekleyen oyunları listele
            players_data = game_info.get("players", {})
            player_count = sum(1 for p in players_data.values() 
                              if isinstance(p, dict) and p.get('side') in [0, 1])
            
            if player_count == 1:
                # Birinci oyuncuyu bul
                first_player = None
                for p in players_data.values():
                    if isinstance(p, dict) and p.get('side') == 0:  # 0=FIRST
                        first_player = p.get('username')
                        break
                
                waiting_games.append({
                    "game_id": game_id, 
                    "created_time": game_info.get("last_update", 0),
                    "first_player": first_player
                })
    
    return render_template("active_games.html", waiting_games=waiting_games, username=session["username"])

@app.route("/katil/<game_id>")
@login_required
def oyuna_katil(game_id):
    if game_id not in games:
        return "Oyun bulunamadı", 404
    
    # Bu oyunda zaten ikinci oyuncu var mı kontrol et
    game_data = games[game_id]
    if Side.SECOND in game_data["player_usernames"].values():
        return "Bu oyun dolu", 403
    
    # Oyuna yönlendir
    return redirect(f"/oyun/{game_id}")

@app.route("/yeni-oyun", methods=["POST"])
def yeni_oyun():
    # Yeni oyun ID'si oluştur
    game_id = str(uuid.uuid4())[:8]  # Daha kısa ID
    
    # Başlangıç zarları
    allowed_rolls = list(range(1, 7))
    first_roll = random.choice(allowed_rolls)
    allowed_rolls.remove(first_roll)
    second_roll = random.choice(allowed_rolls)
    
    # Başlayacak tarafı belirle
    side = Side.FIRST if first_roll > second_roll else Side.SECOND
    
    # Yeni oyun oluştur
    game = Game(side)
    
    # Test için zarları hazırla
    game.roll_dice()
    
    # Oyun durumunu serileştir
    game_state = serialize_game(game)
    
    # Oyun bilgilerini oluştur
    game_data = {
        "game_state": game_state,
        "start_rolls": [first_roll, second_roll],
        "players": {},
        "messages": [],
        "last_update": time.time(),
        "status": "waiting"
    }
    
    # Firebase'e kaydet
    firebase.create_game(game_id, game_data)
    
    # Geçici olarak hafızada da tutuyoruz (geçiş dönemi için)
    games[game_id] = {
        "game": game,
        "start_rolls": (first_roll, second_roll),
        "players": {},
        "messages": [],
        "last_update": time.time(),
        "status": "waiting"
    }
    
    print(f"Yeni oyun oluşturuldu: {game_id}")
    return jsonify({"game_id": game_id})

# Bağlantı kurulduğunda durum bildirimi için yeni olay
@socketio.on('connect')
def handle_connect():
    if "username" not in session:
        return False  # Bağlantıyı reddet
    
    print(f"Kullanıcı bağlandı: {session['username']}, sid: {request.sid}")
    # Kullanıcı sid eşleştirmesi
    user_sid[session['username']] = request.sid
    sid_user[request.sid] = session['username']
    emit('connection_status', {'status': 'connected', 'username': session['username']})

@socketio.on("join")
def on_join(data):
    try:
        game_id = data["game_id"]
        player_id = request.sid
        username = session.get('username')
        
        print(f"Oyuncu katılıyor: {username} (sid: {player_id}), oyun: {game_id}")
        
        # Firebase'den oyun verilerini al
        game_data_fb = firebase.get_game(game_id)
        
        if not game_data_fb:
            emit("error", {"message": "Oyun bulunamadı"})
            return
        
        # Game nesnesini oluştur
        game_state = game_data_fb.get("game_state", {})
        game = deserialize_game(game_state)
        
        # Geçiş için bellekte de tutuyoruz
        if game_id not in games:
            games[game_id] = {
                "game": game,
                "start_rolls": tuple(game_data_fb.get("start_rolls", (1, 2))),
                "players": {},
                "messages": game_data_fb.get("messages", []),
                "last_update": game_data_fb.get("last_update", time.time()),
                "status": game_data_fb.get("status", "waiting")
            }
        
        game_data = games[game_id]
        players_data = game_data_fb.get("players", {})
        
        # Bu kullanıcı zaten oyunda mı kontrol et
        username_exists = False
        for sid, player_info in players_data.items():
            if isinstance(player_info, dict) and player_info.get('username') == username:
                # Aynı kullanıcı yeni oturumla bağlanıyorsa, eski bağlantıyı kaldır
                old_side = player_info.get('side')
                players_data.pop(sid)
                players_data[player_id] = {'username': username, 'side': old_side}
                username_exists = True
                side = old_side
                side_str = "Birinci" if side == 0 else ("İkinci" if side == 1 else "İzleyici")  # 0=FIRST, 1=SECOND
                emit("player_side", {"side": side})
                message = f"{username} ({side_str}) yeniden bağlandı"
                print(f"Mevcut oyuncu yeniden bağlandı: {username}, taraf: {side_str}")
                break
        
        # Yeni oyuncu olarak katılma
        if not username_exists:
            # Uygun tarafı belirle
            side = None
            sides_taken = [p.get('side') for p in players_data.values() if isinstance(p, dict)]
            
            if 0 not in sides_taken:  # 0=FIRST
                side = 0  # Side.FIRST
            elif 1 not in sides_taken:  # 1=SECOND
                side = 1  # Side.SECOND
            else:
                # İzleyici olarak katıl
                side = None
                
            # Oyuncuyu kaydet
            players_data[player_id] = {
                'username': username,
                'side': side
            }
            side_str = "Birinci" if side == 0 else ("İkinci" if side == 1 else "İzleyici")
            print(f"Yeni oyuncu katıldı: {username}, taraf: {side_str}")
        
        # Bellekteki versiyon için de oyuncuyu kaydet
        game_data['players'][player_id] = {
            'username': username,
            'side': Side(side) if side is not None else None
        }
        
        # Firebase'e oyuncu güncellemesi
        firebase.update_game(game_id, {"players": players_data})
        
        join_room(game_id)
        
        # Oyuncuya tarafını bildir
        if side is not None:
            emit("player_side", {"side": side})
            print(f"Oyuncuya tarafı bildirildi: {username}, taraf: {side}")
        
        # Oyun durumunu gönder
        send_game_state(game_id)
        
        # Başlangıç zarlarını gönder
        emit("turn_rolls", {
            "first": game_data_fb["start_rolls"][0], 
            "second": game_data_fb["start_rolls"][1]
        }, room=game_id)
        
        # Mevcut sıra bilgisini gönder
        emit("turn_info", {
            "current_side": int(game.side),
            "dice": list(game.dice),
            "dice_played": list(game.dice_played) if hasattr(game, "dice_played") and game.dice_played else []
        }, room=game_id)
        
        # Oyuncu katıldı mesajı
        side_str = "Birinci" if side == 0 else (
            "İkinci" if side == 1 else "İzleyici"
        )
        
        message = f"{username} ({side_str}) oyuna katıldı"
        
        # Mesajı Firebase'e ekle
        messages = game_data_fb.get("messages", [])
        messages.append(message)
        firebase.update_game(game_id, {"messages": messages})
        
        # Bellekteki messages'a da ekle
        game_data["messages"].append(message)
        
        emit("message", {"text": message}, room=game_id)
        
        # Son güncelleme zamanını kaydet
        current_time = time.time()
        firebase.update_game(game_id, {"last_update": current_time})
        game_data["last_update"] = current_time
        
    except Exception as e:
        print(f"Oyuncu katılırken hata: {str(e)}")
        emit("error", {"message": f"Beklenmeyen bir hata oluştu: {str(e)}"})

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid                       # isim net: socket id
    print(f"Oyuncu ayrıldı: {sid}")
    username = session.get('username', 'Bilinmeyen oyuncu')

    # Oyuncunun bulunduğu ilk oyunu bul
    for game_id, g in list(games.items()):
        if sid not in g["players"]:
            continue

        player_info = g["players"].get(sid)
        if not isinstance(player_info, dict):
            continue
            
        leaving_side = player_info.get('side')
        username = player_info.get('username', username)
        
        g["players"].pop(sid)          # oyuncuyu çıkar
        leave_room(game_id)                           # odadan çık

        # Bilgilendirme mesajı
        side_str = ("Birinci"  if leaving_side == Side.FIRST  else
                    "İkinci"   if leaving_side == Side.SECOND else
                    "İzleyici")
        msg = f"{username} ({side_str}) oyundan ayrıldı"
        g["messages"].append(msg)
        emit("message", {"text": msg}, room=game_id)

        # Aktif oyuncu kalmadıysa oyunu sil
        active_sides = []
        for player in g["players"].values():
            if isinstance(player, dict) and player.get('side') in (Side.FIRST, Side.SECOND):
                active_sides.append(player.get('side'))
                
        if not active_sides:
            emit("game_ended", {"message": "Tüm oyuncular ayrıldı"}, room=game_id)
            games.pop(game_id, None)

        break

@socketio.on("move")
def on_move(data):
    try:
        game_id = data["game_id"]
        die_index = data["die_index"]
        source = data["source"]
        player_id = request.sid
        username = session.get('username', 'Bilinmeyen oyuncu')
        
        print(f"Hamle isteği: oyun={game_id}, oyuncu={username}, zar={die_index}, kaynak={source}")
        
        # Firebase'den oyun verilerini al
        game_data_fb = firebase.get_game(game_id)
        
        if not game_data_fb:
            emit("error", {"message": "Oyun bulunamadı"})
            return
        
        # Game nesnesini oluştur
        game_state = game_data_fb.get("game_state", {})
        game = deserialize_game(game_state)
        
        # Geçiş için bellekte de tutuyoruz
        if game_id not in games:
            games[game_id] = {
                "game": game,
                "players": game_data_fb.get("players", {}),
                "messages": game_data_fb.get("messages", []),
                "last_update": game_data_fb.get("last_update", time.time())
            }
        
        game_data = games[game_id]
        game_data["game"] = game  # Güncel oyun nesnesini belleğe kaydet
        
        # Bu oyuncunun tarafını bul
        players_data = game_data_fb.get("players", {})
        
        if player_id not in players_data:
            emit("error", {"message": "Bu oyuna katılmış değilsiniz"})
            return
            
        player_info = players_data[player_id]
        if not isinstance(player_info, dict):
            emit("error", {"message": "Oyuncu bilgisi hatalı"})
            return
            
        player_side = player_info.get('side')
        
        # Sıranın bu oyuncuda olup olmadığını kontrol et
        if player_side != int(game.side):
            print(f"Sıra hatası: Oyuncu tarafı={player_side}, Oyun sırası={int(game.side)}")
            emit("error", {"message": "Şu anda sıra sizde değil"})
            return
        
        # Hamleyi yap
        try:
            # Oyunun bir kopyasını al, hata olursa geri dönebilmek için
            backup_game = copy.deepcopy(game)
            
            # game.dice set ise tuple'a dönüştür (pygammon kütüphanesi tuple bekliyor)
            if isinstance(game.dice, set):
                # Set olarak geliyorsa tuple'a dönüştür
                game.dice = tuple(game.dice)
            
            # Debug bilgisi ekle
            print(f"Hamle detayları: Zarlar={game.dice}, Seçilen zar indeksi={die_index}, Kaynak={source}")
            
            # Girişi doğru formata dönüştür
            die_index_int = int(die_index)
            # Kırık taş durumu için source'u None olarak ayarla
            source_int = None if source is None else int(source)
            
            # İndex doğrulaması yap
            if die_index_int < 0 or die_index_int >= len(game.dice):
                raise ValueError(f"Geçersiz zar indeksi: {die_index_int}. Zarlar: {game.dice}")
            
            # DEBUG: Doğru zar değerini göster
            print(f"Seçilen zar indeksi: {die_index_int}, Zar değeri: {game.dice[die_index_int]}")
            
            # Güvenli hamle yap - zar indeksini ve kaynağı geçir
            game.move(die_index_int, source_int)
            
            # Oyun durumunu Firebase'e kaydet
            updated_game_state = serialize_game(game)
            firebase.update_game(game_id, {"game_state": updated_game_state})
            
            # Oyun durumunu güncelle
            send_game_state(game_id)
            
            # Hamlenin başarılı olduğunu bildir
            emit("move_success", {}, room=game_id)
            
            # Oynanan zarı dice_played set'ine ekle
            # NOT: Artık selected_die değil, die_index_int'i eklememiz gerekiyor
            try:
                # Zar indeksini dice_played setine ekle
                game.dice_played.add(die_index_int)
                print(f"Oynanan zar indeksi eklendi: {die_index_int}, Oynanan zarlar: {game.dice_played}")
            except Exception as e:
                print(f"Zar eklenirken hata: {str(e)}")
                game.dice_played = set([die_index_int])
                print(f"Yeni dice_played seti oluşturuldu: {game.dice_played}")
                
            # Eğer tüm zarlar oynanmışsa sırayı değiştir
            if len(game.dice_played) == len(game.dice):
                print(f"Tüm zarlar oynandı. Sıra değiştiriliyor.")
                # Sırayı değiştir (Side enumerasyonu ile güvenli dönüşüm)
                next_side = Side.SECOND if game.side == Side.FIRST else Side.FIRST
                game.side = next_side
                game.dice_played = set()
                
                # Yeni zarları at
                game.roll_dice()
                print(f"Yeni zarlar: {game.dice}")
                
                # Güncellenmiş oyun durumunu Firebase'e kaydet
                updated_game_state = serialize_game(game)
                firebase.update_game(game_id, {"game_state": updated_game_state})
                
                # Yeni zarları gönder
                emit("move_rolls", {
                    "dice": list(game.dice),
                    "side": int(game.side)
                }, room=game_id)
                
                # Sıra değişimini açıkça bildir
                change_turn(game_id)
            
            # Son güncelleme zamanını kaydet
            current_time = time.time()
            firebase.update_game(game_id, {"last_update": current_time})
            game_data["last_update"] = current_time
                
        except InvalidMove as e:
            # Hata durumunda oyunu eski haline getir
            games[game_id]["game"] = backup_game
            
            # Hata mesajı gönder
            error_messages = {
                InvalidMoveCode.DIE_INDEX_INVALID: "Geçersiz zar indeksi",
                InvalidMoveCode.SOURCE_INVALID: "Geçersiz başlangıç noktası",
                InvalidMoveCode.SOURCE_NOT_OWNED_PIECE: "Bu noktada size ait taş yok",
                InvalidMoveCode.DESTINATION_OUT_OF_BOARD: "Hedef nokta tahta dışında",
                InvalidMoveCode.DESTINATION_OCCUPIED: "Hedef nokta rakip tarafından tutulmuş"
            }
            
            error_message = error_messages.get(e.code, "Geçersiz hamle")
            emit("error", {"message": error_message})
            
        except GameWon:
            # Oyun kazanıldı
            winner = "Birinci" if game.side == Side.FIRST else "İkinci"
            message = f"{winner} oyuncu kazandı!"
            
            # Mesajı Firebase'e ekle
            messages = game_data_fb.get("messages", [])
            messages.append(message)
            firebase.update_game(game_id, {
                "messages": messages,
                "status": "finished",
                "winner": int(game.side)
            })
            
            # Bellekteki messages'a da ekle
            game_data["messages"].append(message)
            
            # Oyun durumunu son kez gönder
            send_game_state(game_id)
            
            # Oyun sonu mesajını gönder
            emit("game_won", {
                "winner": int(game.side),
                "message": message
            }, room=game_id)
            
        except ValueError as ve:
            # Geçersiz indeks veya parametre hatası
            print(f"Değer hatası: {str(ve)}")
            emit("error", {"message": f"Geçersiz değer: {str(ve)}"})
            
        except Exception as e:
            # Beklenmeyen diğer hatalar
            error_detail = str(e)
            error_type = type(e).__name__
            print(f"Hamle işlenirken hata: {error_type} - {error_detail}")
            
            # Stack trace'i de yazdır
            import traceback
            traceback.print_exc()
            
            # Kullanıcıya anlaşılır hata mesajı gönder
            emit("error", {"message": f"Beklenmeyen bir hata oluştu: {error_type} - {error_detail}"})
            
    except Exception as e:
        print(f"Hamle isteği işlenirken genel hata: {str(e)}")
        emit("error", {"message": f"Beklenmeyen bir hata oluştu: {str(e)}"})

@socketio.on("roll_dice")
def on_roll_dice(data):
    try:
        game_id = data["game_id"]
        player_id = request.sid
        username = session.get('username', 'Bilinmeyen oyuncu')
        
        print(f"Zar atma isteği: oyun={game_id}, oyuncu={username}")
        
        if game_id not in games:
            emit("error", {"message": "Oyun bulunamadı"})
            return
            
        game_data = games[game_id]
        game = game_data["game"]
        
        # Bu oyuncunun tarafını bul
        if player_id not in game_data["players"]:
            emit("error", {"message": "Bu oyuna katılmış değilsiniz"})
            return
            
        player_info = game_data["players"][player_id]
        if not isinstance(player_info, dict):
            emit("error", {"message": "Oyuncu bilgisi hatalı"})
            return
            
        player_side = player_info.get('side')
        
        # Sıranın bu oyuncuda olup olmadığını kontrol et
        if player_side != game.side:
            print(f"Zar atma hatası: Oyuncu tarafı={player_side}, Oyun sırası={game.side}")
            emit("error", {"message": "Şu anda sıra sizde değil"})
            return
        
        # Zar at
        game.roll_dice()
        
        print(f"Zarlar atıldı: {game.dice}")
        
        # Zarları gönder
        emit("move_rolls", {
            "dice": list(game.dice),
            "side": int(game.side)
        }, room=game_id)
        
        # Oyun durumunu güncelle
        send_game_state(game_id)
        
        # Son güncelleme zamanını kaydet
        game_data["last_update"] = time.time()
    except Exception as e:
        print(f"Zar atılırken hata: {str(e)}")
        emit("error", {"message": f"Beklenmeyen bir hata oluştu: {str(e)}"})

@socketio.on("chat_message")
def on_chat_message(data):
    game_id = data["game_id"]
    message = data["message"]
    player_id = request.sid
    
    if game_id not in games:
        emit("error", {"message": "Oyun bulunamadı"})
        return
        
    game_data = games[game_id]
    
    # Oyuncu ismini belirle
    if player_id in game_data["players"]:
        side = game_data["players"][player_id]
        player_name = "Birinci" if side == Side.FIRST else (
            "İkinci" if side == Side.SECOND else "İzleyici"
        )
    else:
        player_name = "İzleyici"
    
    # Mesajı kaydet ve gönder
    full_message = f"{player_name}: {message}"
    game_data["messages"].append(full_message)
    emit("message", {"text": full_message}, room=game_id)
    
    # Son güncelleme zamanını kaydet
    game_data["last_update"] = time.time()

# Oyun durumu isteme endpoint'i
@socketio.on("request_game_state")
def on_request_game_state(data):
    game_id = data["game_id"]
    player_id = request.sid
    username = session.get('username', 'Bilinmeyen')
    
    if game_id in games:
        game_data = games[game_id]
        game = game_data["game"]
        
        # Oyuncunun tarafını bul
        player_side = None
        if player_id in game_data["players"]:
            player_info = game_data["players"][player_id]
            if isinstance(player_info, dict):
                player_side = player_info.get('side')
                print(f"Oyun durumu isteği: oyun={game_id}, oyuncu={username}, taraf={player_side}, mevcut sıra={game.side}")
        
        send_game_state(game_id)
        
        # Mevcut sıra bilgisini de gönder
        emit("turn_info", {
            "current_side": int(game.side),
            "dice": list(game.dice),
            "dice_played": list(game.dice_played) if hasattr(game, "dice_played") and game.dice_played else []
        })
        
        # Son güncelleme zamanını kaydet
        games[game_id]["last_update"] = time.time()

# Sıra değişimi bildirimi
def change_turn(game_id):
    """Sıra değişimini tüm oyunculara bildir"""
    if game_id not in games:
        return
        
    game_data = games[game_id]
    game = game_data["game"]
    
    # Açık ve net bir sıra değişimi bildirimi gönder
    socketio.emit("turn_change", {
        "current_side": int(game.side),
        "timestamp": int(time.time()),
        "dice": list(game.dice)
    }, room=game_id)
    
    # Mevcut oyuncuya özel bildirim gönder
    for player_id, player_info in game_data["players"].items():
        if isinstance(player_info, dict) and player_info.get('side') == int(game.side):
            socketio.emit("your_turn", {
                "dice": list(game.dice)
            }, room=player_id)

def send_game_state(game_id):
    """Oyun durumunu tüm oyunculara gönder"""
    # Firebase'den oyun verilerini al
    game_data_fb = firebase.get_game(game_id)
    
    if not game_data_fb:
        return
    
    # Game nesnesini Firebase'den al veya bellekten kullan
    if game_id in games:
        game = games[game_id]["game"]
    else:
        game_state = game_data_fb.get("game_state", {})
        game = deserialize_game(game_state)
    
    first_player = game.players[Side.FIRST]
    second_player = game.players[Side.SECOND]
    
    # Oyun tahtasını JSON formatına dönüştür
    board_data = []
    for i, point in enumerate(game.board):
        board_data.append({
            "index": i,
            "side": None if point.side is None else int(point.side),
            "count": point.count
        })
    
    game_state = {
        "board": board_data,
        "first_hit": first_player.hit,
        "first_borne": first_player.borne,
        "second_hit": second_player.hit,
        "second_borne": second_player.borne,
        "current_side": int(game.side),
        "dice": list(game.dice) if hasattr(game, "dice") else [],
        "dice_played": list(game.dice_played) if hasattr(game, "dice_played") and game.dice_played else []
    }
    
    print(f"Oyun durumu gönderiliyor: {game_id}")
    socketio.emit("game_state", game_state, room=game_id)

# Belirli aralıklarla çalışacak temizleme fonksiyonu
def cleanup_inactive_games():
    """1 saatten uzun süredir güncellenmemiş oyunları temizle"""
    current_time = time.time()
    inactive_threshold = 3600  # 1 saat
    
    games_data = firebase.get_active_games()
    
    if games_data:
        for game_id, game_info in games_data.items():
            last_update = game_info.get("last_update", 0)
            if current_time - last_update > inactive_threshold:
                print(f"İnaktif oyun siliniyor: {game_id}")
                firebase.delete_game(game_id)
                if game_id in games:
                    games.pop(game_id)

# Belirli aralıklarla cleanup işlemini çağır
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_inactive_games, 'interval', minutes=30)
scheduler.start()

# Flask uygulamasını durdurduğunda scheduler'ı da durdur
atexit.register(lambda: scheduler.shutdown())

@app.route('/firebase-test')
def firebase_test():
    try:
        # Firestore test
        firebase.firestore_db.collection('test').document('test').set({'test': True})
        
        # Realtime Database test
        firebase.realtime_db.child('test').set({'test': True})
        
        return "Firebase bağlantısı başarılı!"
    except Exception as e:
        return f"Firebase hatası: {str(e)}"

@socketio.on("pass_turn")
def on_pass_turn(data):
    try:
        game_id = data["game_id"]
        player_id = request.sid
        username = session.get('username', 'Bilinmeyen oyuncu')
        
        print(f"Pas geçme isteği: oyun={game_id}, oyuncu={username}")
        
        # Firebase'den oyun verilerini al
        game_data_fb = firebase.get_game(game_id)
        
        if not game_data_fb:
            emit("error", {"message": "Oyun bulunamadı"})
            return
        
        # Game nesnesini oluştur
        game_state = game_data_fb.get("game_state", {})
        game = deserialize_game(game_state)
        
        # Geçiş için bellekte de tutuyoruz
        if game_id not in games:
            games[game_id] = {
                "game": game,
                "players": game_data_fb.get("players", {}),
                "messages": game_data_fb.get("messages", []),
                "last_update": game_data_fb.get("last_update", time.time())
            }
        
        game_data = games[game_id]
        game_data["game"] = game  # Güncel oyun nesnesini belleğe kaydet
        
        # Bu oyuncunun tarafını bul
        players_data = game_data_fb.get("players", {})
        
        if player_id not in players_data:
            emit("error", {"message": "Bu oyuna katılmış değilsiniz"})
            return
            
        player_info = players_data[player_id]
        if not isinstance(player_info, dict):
            emit("error", {"message": "Oyuncu bilgisi hatalı"})
            return
            
        player_side = player_info.get('side')
        
        # Sıranın bu oyuncuda olup olmadığını kontrol et
        if player_side != int(game.side):
            print(f"Pas geçme hatası: Oyuncu tarafı={player_side}, Oyun sırası={int(game.side)}")
            emit("error", {"message": "Şu anda sıra sizde değil"})
            return
        
        # Kırılan taş kontrolü yap
        current_player = game.players[Side(player_side)]
        has_hit_checker = current_player.hit > 0
        
        if not has_hit_checker:
            emit("error", {"message": "Kırılan taşınız olmadığı için pas geçemezsiniz"})
            return
            
        # Hamle yapılabilir mi kontrol et
        if can_move_hit_checker(game, player_side):
            emit("error", {"message": "Oynayabileceğiniz bir hamle var, pas geçemezsiniz"})
            return
        
        # Tüm kontroller başarılı, pas geçme işlemini uygula
        # Sırayı değiştir
        next_side = Side.SECOND if game.side == Side.FIRST else Side.FIRST
        game.side = next_side
        game.dice_played = set()  # Oynanan zarları sıfırla
        
        # Yeni zarları at
        game.roll_dice()
        print(f"Pas geçildi, yeni zarlar: {game.dice}")
        
        # Güncellenmiş oyun durumunu Firebase'e kaydet
        updated_game_state = serialize_game(game)
        firebase.update_game(game_id, {"game_state": updated_game_state})
        
        # Pas mesajını Firebase'e ekle
        messages = game_data_fb.get("messages", [])
        messages.append(f"{username} hamle yapamadığı için pas geçti")
        firebase.update_game(game_id, {"messages": messages})
        
        # Bellekteki messages'a da ekle
        game_data["messages"].append(f"{username} hamle yapamadığı için pas geçti")
        
        # Oyun durumunu güncelle
        send_game_state(game_id)
        
        # Pas kabul edildi bilgisini gönder
        emit("pass_accepted", {}, room=game_id)
        
        # Yeni zarları gönder
        emit("move_rolls", {
            "dice": list(game.dice),
            "side": int(game.side)
        }, room=game_id)
        
        # Sıra değişimini açıkça bildir
        change_turn(game_id)
        
        # Son güncelleme zamanını kaydet
        current_time = time.time()
        firebase.update_game(game_id, {"last_update": current_time})
        game_data["last_update"] = current_time
            
    except Exception as e:
        print(f"Pas geçme isteği işlenirken hata: {str(e)}")
        import traceback
        traceback.print_exc()
        emit("error", {"message": f"Beklenmeyen bir hata oluştu: {str(e)}"})

# Kırılan taş için hamle yapılabilir mi kontrol et
def can_move_hit_checker(game, player_side):
    """Kırılan taş için hamle yapılabilir mi kontrol eder"""
    # Oyuncunun tarafını al
    side = Side(player_side)
    
    # Zarları al
    dice = game.dice
    dice_played = game.dice_played
    
    # Oynanabilir zarlar
    playable_dice = [d for i, d in enumerate(dice) if i not in dice_played]
    
    # Oyuncunun kırılan taşları var mı?
    current_player = game.players[side]
    if current_player.hit <= 0:
        return True  # Kırılan taş yoksa pas geçemez
    
    # Hamle yapılabilir mi?
    for die_value in playable_dice:
        destination = None
        
        if side == Side.FIRST:
            # Birinci oyuncu için (baş noktadan aşağı doğru hareket eder)
            destination = current_player.beginning - die_value * current_player.direction
        else:
            # İkinci oyuncu için (baş noktadan yukarı doğru hareket eder)
            destination = current_player.beginning + die_value * current_player.direction
        
        # Hedef noktanın tahta içinde olup olmadığını kontrol et
        if 0 <= destination < len(game.board):
            destination_point = game.board[destination]
            
            # Hedef noktanın boş olup olmadığını veya oyuncunun kendi taşı olup olmadığını kontrol et
            if (destination_point.side is None or 
                destination_point.side == side or 
                (destination_point.side != side and destination_point.count == 1)):
                # Hamle yapılabilir
                return True
    
    # Hiçbir hamle bulunamadı
    return False

if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
