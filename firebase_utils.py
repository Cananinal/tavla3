from pygammon.structures import Side
from pygammon.core import Game
import json

# Bu dosya sadece serialize/deserialize işlemleri için kullanılacak

# ─────────────────────────────
# Game objesini serileştir / deserileştir
# ─────────────────────────────

def serialize_game(game):
    """Game nesnesini JSON formatına çevir"""
    first_player = game.players[Side.FIRST]
    second_player = game.players[Side.SECOND]

    board_data = []
    for i, point in enumerate(game.board):
        board_data.append({
            "index": i,
            "side": None if point.side is None else int(point.side),
            "count": point.count
        })

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
    """JSON verisinden Game nesnesi oluştur"""
    current_side = Side(game_data.get("current_side", 0))
    game = Game(current_side)

    for point_data in game_data.get("board", []):
        index = point_data.get("index")
        side = point_data.get("side")
        count = point_data.get("count")

        if side is not None:
            game.board[index].side = Side(side)
            game.board[index].count = count

    game.players[Side.FIRST].hit = game_data.get("first_hit", 0)
    game.players[Side.FIRST].borne = game_data.get("first_borne", 0)
    game.players[Side.SECOND].hit = game_data.get("second_hit", 0)
    game.players[Side.SECOND].borne = game_data.get("second_borne", 0)

    game.dice = tuple(game_data.get("dice", []))
    game.dice_played = set(game_data.get("dice_played", []))

    return game
