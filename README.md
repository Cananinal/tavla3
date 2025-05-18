# Tavla Oyunu

Bu proje, `pygammon` kütüphanesini kullanarak Python ile geliştirilmiş basit bir tavla (backgammon) oyunudur. Oyun konsolda oynanmaktadır.

## Gereksinimler

Bu oyunu çalıştırmak için aşağıdaki paketler gerekmektedir:

- Python 3.6+
- pygammon kütüphanesi

## Kurulum

1. Gereksinimleri yükleyin:
```
pip install pygammon
```

2. Oyunu çalıştırın:
```
python tavla_oyunu.py
```

## Nasıl Oynanır

Oyun, iki oyuncu arasında sırayla oynanır. Her oyuncunun 15 taşı vardır ve amaç, tüm taşları kendi bölgenize getirip oyundan çıkarmaktır.

### Komutlar

- `hamle [zar_indeksi] [kaynak_nokta]`: Bir taşı hareket ettirmek için kullanılır.
  - `zar_indeksi`: Kullanmak istediğiniz zarın indeksi (0 veya 1, çift attıysanız 0, 1, 2 veya 3)
  - `kaynak_nokta`: Hareket ettirmek istediğiniz taşın bulunduğu nokta (0-23)
  
- `geri`: Son hamleyi geri alır.

### Tahta Düzeni

Tavla tahtası 24 noktadan oluşur (0-23). Tahtanın üst kısmı 12-23 arası, alt kısmı 0-11 arası noktaları gösterir.

- `B` harfi Birinci oyuncunun taşlarını temsil eder.
- `S` harfi İkinci oyuncunun taşlarını temsil eder.
- Yanındaki sayı, o noktadaki taş sayısını gösterir.

### Oyunun Başlangıcı

Oyun başlangıcında, sırayı belirlemek için her iki oyuncu da zar atar. Daha yüksek zar atan oyuncu başlar.

### Oyunun Sonu

Bir oyuncu tüm taşlarını tahtadan çıkardığında oyun sona erer.

## Örnek Hamle

```
hamle 0 5
```

Bu komut, 0 indeksindeki zarı kullanarak 5 numaralı noktadan bir taşı hareket ettirir.

## Geliştirici

Bu oyun, pygammon kütüphanesi kullanılarak geliştirilmiştir. 