from pygammon.structures import Side, GameState
from pygammon.core import Game
import json

def serialize_game(game):
    """Game nesnesini JSON'a çevir"""
    first_player = game.players[Side.FIRST]
    second_player = game.players[Side.SECOND]
    
    # Tahtayı serileştir
    board_data = []
    for i, point in enumerate(game.board):
        board_data.append({
            "index": i,
            "side": None if point.side is None else int(point.side),
            "count": point.count
        })
    
    # Oyun durumunu serileştir
    game_data = {
        "board": board_data,
        "first_hit": first_player.hit,
        "first_borne": first_player.borne,
        "second_hit": second_player.hit,
        "second_borne": second_player.borne,
        "current_side": int(game.side),
        "dice": list(game.dice) if hasattr(game, "dice") else [],
        "dice_played": list(game.dice_played) if hasattr(game, "dice_played") else []
    }
    
    return game_data

def deserialize_game(game_data):
    """JSON'dan Game nesnesi oluştur"""
    # Başlayan tarafı belirle
    current_side = Side(game_data.get("current_side", 0))
    
    # Yeni oyun nesnesi oluştur
    game = Game(current_side)
    
    # Tahtayı yükle
    board_data = game_data.get("board", [])
    for point_data in board_data:
        index = point_data.get("index")
        side = point_data.get("side")
        count = point_data.get("count")
        
        if side is not None:
            game.board[index].side = Side(side)
            game.board[index].count = count
    
    # Oyuncu durumlarını yükle
    game.players[Side.FIRST].hit = game_data.get("first_hit", 0)
    game.players[Side.FIRST].borne = game_data.get("first_borne", 0)
    game.players[Side.SECOND].hit = game_data.get("second_hit", 0)
    game.players[Side.SECOND].borne = game_data.get("second_borne", 0)
    
    # Zarları yükle - dice tuple olmalı, dice_played ise set
    game.dice = tuple(game_data.get("dice", []))  # Set yerine tuple kullan - pygammon kütüphanesi bunu bekliyor
    game.dice_played = set(game_data.get("dice_played", []))  # Bu bir set olabilir
    
    return game
