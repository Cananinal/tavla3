document.addEventListener('DOMContentLoaded', function() {
    const yeniOyunBtn = document.getElementById('yeni-oyun-btn');
    const katilBtn = document.getElementById('katil-btn');
    const oyunIdInput = document.getElementById('oyun-id');
    const refreshGamesBtn = document.getElementById('refresh-games-btn');
    
    // Yeni oyun oluştur butonu
    yeniOyunBtn.addEventListener('click', function() {
        // Butonun durumunu güncelle
        yeniOyunBtn.disabled = true;
        yeniOyunBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Oluşturuluyor...';
        
        // Sunucuya istek gönder
        fetch('/yeni-oyun', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            // Oluşturulan oyun ID'si ile oyun sayfasına yönlendir
            window.location.href = `/oyun/${data.game_id}`;
        })
        .catch(error => {
            console.error('Hata:', error);
            alert('Oyun oluşturulurken bir hata oluştu.');
            
            // Hata durumunda butonu eski haline getir
            yeniOyunBtn.disabled = false;
            yeniOyunBtn.innerHTML = '<i class="fas fa-gamepad"></i> Yeni Oyun Oluştur';
        });
    });
    
    // Oyuna katıl butonu
    katilBtn.addEventListener('click', function() {
        const gameId = oyunIdInput.value.trim();
        
        if (!gameId) {
            alert('Lütfen bir Oyun ID girin.');
            return;
        }
        
        // Katılma işlemini göster
        katilBtn.disabled = true;
        katilBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Katılınıyor...';
        
        // Oyun ID'sinin varlığını kontrol et
        fetch(`/oyun/${gameId}`, {
            method: 'HEAD'
        })
        .then(response => {
            if (response.ok) {
                // Oyun sayfasına yönlendir
                window.location.href = `/oyun/${gameId}`;
            } else {
                alert('Geçersiz Oyun ID! Böyle bir oyun bulunamadı.');
                katilBtn.disabled = false;
                katilBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Katıl';
            }
        })
        .catch(error => {
            console.error('Hata:', error);
            alert('Oyuna katılırken bir hata oluştu.');
            katilBtn.disabled = false;
            katilBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Katıl';
        });
    });
    
    // Liste yenileme butonu
    if (refreshGamesBtn) {
        refreshGamesBtn.addEventListener('click', function() {
            // Yenileme animasyonu göster
            refreshGamesBtn.disabled = true;
            refreshGamesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yenileniyor...';
            
            // Sayfayı yenile
            window.location.reload();
        });
    }
    
    // Enter tuşuna basıldığında da katıl butonunu aktifleştir
    oyunIdInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            katilBtn.click();
        }
    });
    
    // Otomatik yenileme - 30 saniyede bir
    setInterval(function() {
        console.log("Lobi otomatik yenileniyor...");
        window.location.reload();
    }, 30000);
}); 