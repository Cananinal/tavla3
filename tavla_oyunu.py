import sys
from typing import Optional, Tuple

from pygammon.core import run
from pygammon.structures import (
    GameState, InputType, InvalidMoveCode, OutputType, Side, DieRolls
)

def tavla_tahta_goster(tahta, birinci_hit, birinci_borne, ikinci_hit, ikinci_borne):
    """Tavla tahtasını konsola yazdır"""
    print("\n" + "=" * 60)
    print(f"Birinci Oyuncu: Kırılan Taş: {birinci_hit}, Çıkarılan Taş: {birinci_borne}")
    print(f"İkinci Oyuncu: Kırılan Taş: {ikinci_hit}, Çıkarılan Taş: {ikinci_borne}")
    print("=" * 60)
    
    # Üst taraf (12-23 arası noktalar)
    print("\n   ", end="")
    for i in range(12, 24):
        print(f"{i:2d} ", end="")
    print("\n   ", end="")
    for i in range(12, 24):
        print("---", end="")
    print("\n   ", end="")
    
    # Üst taraftaki taşları göster
    for i in range(12, 24):
        point = tahta[i]
        if point.side is None:
            print("   ", end="")
        elif point.side == Side.FIRST:
            print(f"B{point.count:1d} ", end="")
        else:
            print(f"S{point.count:1d} ", end="")
    print()
    
    # Orta çizgi
    print("\n" + "=" * 60)
    
    # Alt taraf (11-0 arası noktalar)
    print("\n   ", end="")
    for i in range(11, -1, -1):
        print(f"{i:2d} ", end="")
    print("\n   ", end="")
    for i in range(11, -1, -1):
        print("---", end="")
    print("\n   ", end="")
    
    # Alt taraftaki taşları göster
    for i in range(11, -1, -1):
        point = tahta[i]
        if point.side is None:
            print("   ", end="")
        elif point.side == Side.FIRST:
            print(f"B{point.count:1d} ", end="")
        else:
            print(f"S{point.count:1d} ", end="")
    print("\n")


def oyuncu_girisi_al(taraf: Side) -> Tuple[InputType, Optional[Tuple[int, Optional[int]]]]:
    """Oyuncudan hamle girdisi al"""
    oyuncu_adi = "Birinci" if taraf == Side.FIRST else "İkinci"
    print(f"\n{oyuncu_adi} Oyuncu'nun sırası.")
    
    while True:
        giris = input("Hamle yapın (örn: 'hamle 0 5') veya geri almak için 'geri' yazın: ").strip()
        
        if giris.lower() == "geri":
            return InputType.UNDO, None
        
        if giris.lower().startswith("hamle"):
            try:
                parcalar = giris.split()
                if len(parcalar) != 3:
                    raise ValueError("Hatalı format")
                
                zar_indeksi = int(parcalar[1])
                kaynak = int(parcalar[2]) if parcalar[2].isdigit() else None
                
                return InputType.MOVE, (zar_indeksi, kaynak)
            except (ValueError, IndexError):
                print("Geçersiz hamle formatı. 'hamle [zar_indeksi] [kaynak_nokta]' veya 'geri' yazın.")
        else:
            print("Geçersiz komut. 'hamle [zar_indeksi] [kaynak_nokta]' veya 'geri' yazın.")


def cikti_gonder(cikti_tipi: OutputType, veri, taraf: Optional[Side] = None):
    """Oyun durumunu ekrana yazdır"""
    if cikti_tipi == OutputType.GAME_STATE:
        game_state = veri  # GameState tipinde
        tavla_tahta_goster(
            game_state.board,
            game_state.first_hit,
            game_state.first_borne,
            game_state.second_hit,
            game_state.second_borne,
        )
    
    elif cikti_tipi == OutputType.TURN_ROLLS:
        die_rolls = veri  # DieRolls tipinde
        print(f"Sıra belirlemek için atılan zarlar: Birinci: {die_rolls.first}, İkinci: {die_rolls.second}")
    
    elif cikti_tipi == OutputType.MOVE_ROLLS:
        die_rolls = veri  # DieRolls tipinde
        print(f"Atılan zarlar: {die_rolls.first}, {die_rolls.second}")
    
    elif cikti_tipi == OutputType.INVALID_MOVE:
        hata_kodu = veri  # InvalidMoveCode tipinde
        oyuncu = "Birinci" if taraf == Side.FIRST else "İkinci"
        
        if hata_kodu == InvalidMoveCode.DIE_INDEX_INVALID:
            print(f"{oyuncu} Oyuncu: Geçersiz zar indeksi.")
        elif hata_kodu == InvalidMoveCode.SOURCE_INVALID:
            print(f"{oyuncu} Oyuncu: Geçersiz başlangıç noktası.")
        elif hata_kodu == InvalidMoveCode.SOURCE_NOT_OWNED_PIECE:
            print(f"{oyuncu} Oyuncu: Bu noktada size ait taş yok.")
        elif hata_kodu == InvalidMoveCode.DESTINATION_OUT_OF_BOARD:
            print(f"{oyuncu} Oyuncu: Hedef nokta tahta dışında.")
        elif hata_kodu == InvalidMoveCode.DESTINATION_OCCUPIED:
            print(f"{oyuncu} Oyuncu: Hedef nokta rakip tarafından tutulmuş.")
        elif hata_kodu == InvalidMoveCode.INVALID_MOVE_TYPE:
            print(f"{oyuncu} Oyuncu: Geçersiz hamle türü.")
        elif hata_kodu == InvalidMoveCode.NOTHING_TO_UNDO:
            print(f"{oyuncu} Oyuncu: Geri alınacak hamle yok.")
        elif hata_kodu == InvalidMoveCode.INVALID_INPUT_TYPE:
            print(f"{oyuncu} Oyuncu: Geçersiz giriş türü.")
    
    elif cikti_tipi == OutputType.GAME_WON:
        kazanan_taraf = veri  # Side tipinde
        kazanan = "Birinci" if kazanan_taraf == Side.FIRST else "İkinci"
        print(f"\n{'='*20} OYUN BİTTİ {'='*20}")
        print(f"{kazanan} Oyuncu kazandı! Tebrikler!")
        print(f"{'='*50}")


def main():
    """Ana oyun fonksiyonu"""
    print("\n" + "="*50)
    print("Tavla Oyununa Hoş Geldiniz!")
    print("="*50)
    print("\nOyun Kuralları:")
    print("- 'hamle [zar_indeksi] [kaynak_nokta]' komutuyla hamle yapabilirsiniz.")
    print("- zar_indeksi: 0 veya 1 (çift atarsanız 0, 1, 2, 3)")
    print("- kaynak_nokta: Hareket ettirmek istediğiniz taşın bulunduğu nokta (0-23)")
    print("- 'geri' yazarak son hamlenizi geri alabilirsiniz.")
    print("\nİyi oyunlar!")
    
    try:
        run(oyuncu_girisi_al, cikti_gonder)
    except KeyboardInterrupt:
        print("\nOyun sonlandırıldı.")
    except Exception as e:
        print(f"Hata oluştu: {e}")


if __name__ == "__main__":
    main() 