// Tavla oyunu için genel değişkenler
let socket;
let gameState = null;
let selectedPoint = null;
let selectedDieIndex = null;
let playerSide = null;
let isMyTurn = false; // Yeni: Sıranın bizde olup olmadığını takip edeceğiz
let lastUpdateTime = 0; // Son güncelleme zamanı
const AUTO_SYNC_INTERVAL = 5000; // 5 saniyede bir otomatik senkronizasyon
let connectionStatus = 'connecting'; // Bağlantı durumu
let shouldRefreshAfterModal = false; // Modal kapandığında sayfa yenilenecek mi?
let lastTurn = false; // Son sıra durumu

// Oyuncu taraflarını tanımla
const SIDE = {
    FIRST: 0,
    SECOND: 1
};

// DOM yüklendikten sonra çalışacak fonksiyonlar
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    initializeEventListeners();
    setupAutoSync(); // Otomatik senkronizasyon kurulumu
    setupModalEvents(); // Modal olaylarını dinle
    
    // Debug için yardımcı bilgiler
    console.log("Tavla oyunu yüklendi. game_id:", GAME_ID);
});

window.addEventListener("load", () => {
  const savedUsername = sessionStorage.getItem("rejoin_username");
  if (savedUsername) {
    username = savedUsername;
    socket.emit("join", {
      username: username,
      room: room,
      color: null // renk seçimi yeniden yapılacak
    });
    document.getElementById("joinForm").style.display = "block";
    sessionStorage.removeItem("rejoin_username");
  }
});


// Modal olaylarını kurma fonksiyonu
function setupModalEvents() {
    // Modal kapandığında tetiklenecek olay
    const notificationModal = document.getElementById('notification-modal');
    notificationModal.addEventListener('hidden.bs.modal', function() {
        if (shouldRefreshAfterModal) {
            console.log("Modal kapandı, sayfa yenileniyor...");
            window.location.reload();
        }
        // Her durumda bayrak sıfırlanır
        shouldRefreshAfterModal = false;
    });
}

// Socket.io bağlantısını başlat
function initializeSocket() {
    // İyileştirilmiş bağlantı ayarları
    socket = io({
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 20000
    });
    
    // Socket bağlantısı açıldığında oyuna katıl
    socket.on('connect', function() {
        console.log("Socket.io bağlantısı kuruldu");
        connectionStatus = 'connected';
        updateConnectionStatus(); // Bağlantı durumunu güncelle
        flashStatusIndicator("Sunucuya bağlandı", "success");
        socket.emit('join', { game_id: GAME_ID });
    });
    
    // Socket olaylarını dinle
    socket.on('game_state', handleGameState);
    socket.on('turn_rolls', handleTurnRolls);
    socket.on('move_rolls', handleMoveRolls);
    socket.on('move_success', handleMoveSuccess);
    socket.on('game_won', handleGameWon);
    socket.on('message', handleChatMessage);
    socket.on('error', handleError);
    socket.on('player_side', handlePlayerSide);
    socket.on('pass_accepted', handlePassAccepted);
    
    // Yeni: Bağlantı durum olaylarını dinle
    socket.on('connection_status', handleConnectionStatus);
    socket.on('turn_change', handleTurnChange);
    socket.on('your_turn', handleYourTurn);
    socket.on('turn_info', handleTurnInfo);
    
    // Yeniden bağlantı olaylarını dinle
    socket.on('reconnect', function(attemptNumber) {
        console.log(`Yeniden bağlandı, deneme: ${attemptNumber}`);
        connectionStatus = 'connected';
        updateConnectionStatus();
        requestGameState();
        flashStatusIndicator("Sunucuya yeniden bağlandı", "success");
        showNotification("Bağlantı Başarılı", "Sunucuya yeniden bağlandı, oyun durumu güncelleniyor...");
    });
    
    socket.on('reconnect_attempt', function(attemptNumber) {
        console.log(`Yeniden bağlanma denemesi: ${attemptNumber}`);
        connectionStatus = 'connecting';
        updateConnectionStatus();
        flashStatusIndicator("Sunucuya yeniden bağlanılıyor...", "warning");
    });
    
    socket.on('reconnect_error', function(error) {
        console.error("Yeniden bağlanma hatası:", error);
        connectionStatus = 'error';
        updateConnectionStatus();
        flashStatusIndicator("Yeniden bağlanma başarısız", "error");
    });
    
    socket.on('disconnect', function() {
        console.log("Sunucu bağlantısı kesildi");
        connectionStatus = 'disconnected';
        updateConnectionStatus();
        flashStatusIndicator("Sunucu bağlantısı kesildi", "error");
    });
    
    // Bağlantı hatası olduğunda
    socket.on('connect_error', function(error) {
        console.error("Socket bağlantı hatası:", error);
        connectionStatus = 'error';
        updateConnectionStatus();
        flashStatusIndicator("Sunucu bağlantı hatası", "error");
        showNotification("Bağlantı Hatası", "Sunucu bağlantısında bir sorun oluştu. Yeniden bağlanmaya çalışılıyor...");
    });
}

// DOM olaylarını dinle
function initializeEventListeners() {
    // Zar atma butonu
    document.getElementById('roll-dice-btn').addEventListener('click', function() {
        if (!isMyTurn) {
            showNotification("Uyarı", "Şu anda sıra sizde değil!");
            return;
        }
        
        console.log("Zar atma isteği gönderiliyor...");
        socket.emit('roll_dice', { game_id: GAME_ID });
    });
    
    // Mesaj gönderme butonu
    document.getElementById('send-message-btn').addEventListener('click', sendChatMessage);
    
    // Mesaj inputu Enter tuşu dinleme
    document.getElementById('chat-input').addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            sendChatMessage();
        }
    });
    
    // Yenile butonu
    document.getElementById('refresh-state-btn').addEventListener('click', function() {
        requestGameState();
        flashStatusIndicator("Oyun durumu yenileniyor...", "info");
    });
    
    // DEV: Oyuncu tarafını manuel belirleme butonu (geliştirme için)
    const container = document.createElement('div');
    container.className = 'mt-2 d-flex justify-content-between';
    
    const firstBtn = document.createElement('button');
    firstBtn.className = 'btn btn-sm btn-outline-primary';
    firstBtn.textContent = 'Birinci Oyuncu Ol';
    firstBtn.onclick = function() { setPlayerSide(SIDE.FIRST); };
    
    const secondBtn = document.createElement('button');
    secondBtn.className = 'btn btn-sm btn-outline-danger';
    secondBtn.textContent = 'İkinci Oyuncu Ol';
    secondBtn.onclick = function() { setPlayerSide(SIDE.SECOND); };
    
    container.appendChild(firstBtn);
    container.appendChild(secondBtn);
    
    document.querySelector('.card-body').appendChild(container);
}

// Otomatik senkronizasyon kurulumu
function setupAutoSync() {
    setInterval(() => {
        // Son güncellemeden beri belirli bir süre geçtiyse otomatik senkronizasyon yap
        const now = Date.now();
        if (now - lastUpdateTime > AUTO_SYNC_INTERVAL) {
            console.log("Otomatik senkronizasyon yapılıyor...");
            requestGameState();
        }
    }, 2000); // 2 saniyede bir kontrol et
}

// Bağlantı durumunu güncelle
function updateConnectionStatus() {
    const statusElement = document.getElementById('connection-status');
    if (!statusElement) return;
    
    // Durum metni ve sınıfını belirle
    let statusText = '';
    let statusClass = '';
    
    switch (connectionStatus) {
        case 'connected':
            statusText = 'Bağlı';
            statusClass = 'bg-success';
            break;
        case 'connecting':
            statusText = 'Bağlanıyor...';
            statusClass = 'bg-warning';
            break;
        case 'disconnected':
            statusText = 'Bağlantı Kesildi';
            statusClass = 'bg-danger';
            break;
        case 'error':
            statusText = 'Bağlantı Hatası';
            statusClass = 'bg-danger';
            break;
        default:
            statusText = 'Bilinmiyor';
            statusClass = 'bg-secondary';
    }
    
    // Durumu güncelle
    statusElement.textContent = statusText;
    statusElement.className = `badge ${statusClass}`;
    
    // Durum sisteme ekleme
    if (connectionStatus !== 'connected') {
        const message = `Bağlantı durumu: ${statusText}`;
        addChatMessage({ text: message }, 'system');
    }
}

// Sıra göstergesini güncelle
function updateTurnIndicator() {
    const turnIndicator = document.getElementById('turn-indicator');
    if (!turnIndicator || !gameState) return;
    
    const currentSide = gameState.current_side;
    const sideText = currentSide === SIDE.FIRST ? "Birinci" : "İkinci";
    
    if (isMyTurn) {
        turnIndicator.textContent = "Sıra sizde! Hamle yapabilirsiniz.";
        turnIndicator.className = "alert alert-success mb-3 text-center p-2";
    } else {
        turnIndicator.textContent = `Sıra ${sideText} oyuncuda. Lütfen bekleyin.`;
        turnIndicator.className = "alert alert-warning mb-3 text-center p-2";
    }
}

// Geçici durum bildirimi göster
function flashStatusIndicator(message, type = 'info') {
    const indicator = document.getElementById('status-indicator');
    if (!indicator) return;
    
    // Tip sınıfını belirle
    let colorClass = '';
    switch (type) {
        case 'success':
            colorClass = 'bg-success';
            break;
        case 'warning':
            colorClass = 'bg-warning';
            break;
        case 'error':
            colorClass = 'bg-danger';
            break;
        default:
            colorClass = 'bg-info';
    }
    
    // Göstergeyi ayarla
    indicator.textContent = message;
    indicator.className = `status-indicator ${colorClass}`;
    indicator.style.display = 'block';
    
    // Animasyon bitince gizle
    setTimeout(() => {
        indicator.style.display = 'none';
    }, 3000);
}

// Oyun durumunu sunucudan iste
function requestGameState() {
    console.log("Oyun durumu isteniyor...");
    socket.emit('request_game_state', { game_id: GAME_ID });
    addChatMessage({ text: "Oyun durumu yenileniyor..." }, 'system');
}

// Bağlantı durumu olayını işle
function handleConnectionStatus(data) {
    console.log("Bağlantı durumu:", data.status);
    if (data.status === 'connected') {
        connectionStatus = 'connected';
        updateConnectionStatus();
        requestGameState();
    }
}

// Sıra değişimi olayını işle
function handleTurnChange(data) {
    console.log("Sıra değişti:", data);
    
    // Güncel sıra bilgisini al
    const currentSide = data.current_side;
    
    // Sıra kontrolü yap
    isMyTurn = playerSide === currentSide;
    
    // Arayüzü güncelle
    if (gameState) {
        gameState.current_side = currentSide;
    }
    
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Zarları güncelle
    if (data.dice && data.dice.length > 0) {
        renderDice(data.dice);
    }
    
    // Bildirim göster
    const sideText = currentSide === SIDE.FIRST ? "Birinci" : "İkinci";
    if (isMyTurn) {
        flashStatusIndicator("Sıra size geldi!", "success");
        showNotification("Sıra Değişimi", "Sıra size geldi!", true);
        addChatMessage({ text: "Sıra size geldi! Hamle yapabilirsiniz." }, 'success');
    } else {
        flashStatusIndicator(`Sıra ${sideText} oyuncuya geçti.`, "info");
        addChatMessage({ text: `Sıra ${sideText} oyuncuya geçti. Lütfen bekleyin.` }, 'system');
    }
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Sıra bilgisi olayını işle
function handleTurnInfo(data) {
    // Oyun durumu güncelleme
    if (gameState) {
        gameState.current_side = data.current_side;
        gameState.dice = data.dice;
        gameState.dice_played = data.dice_played;
    }
    
    console.log("Sıra bilgisi:", data);
    console.log("Mevcut sıra:", data.current_side === SIDE.FIRST ? "Birinci (0)" : "İkinci (1)");
    console.log("Oyuncu tarafı:", playerSide === SIDE.FIRST ? "Birinci (0)" : (playerSide === SIDE.SECOND ? "İkinci (1)" : "İzleyici (null)"));
    console.log("Data type kontrolü: data.current_side typeof =", typeof data.current_side, ", playerSide typeof =", typeof playerSide);
    
    // Sıra kontrolü
    if (playerSide !== null) {
        isMyTurn = data.current_side === playerSide;
        console.log("Sıra bende mi:", isMyTurn);
    } else {
        isMyTurn = false;
    }
    
    // Zarları güncelle (eğer benim sıramsa)
    if (isMyTurn && data.dice && data.dice.length > 0) {
        renderDice(data.dice);
    }
    
    // UI güncellemeleri
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Eğer sıramsa bildirim göster
    if (isMyTurn && lastTurn !== isMyTurn) {
        const notification = {
            text: 'Sıra sizde! Zar seçip hamle yapınız.'
        };
        addChatMessage(notification, 'turn-notification');
        flashStatusIndicator('Sıra sizde!', 'success');
        
        // Zar yoksa otomatik at
        if (!data.dice || data.dice.length === 0 || (data.dice_played && data.dice_played.length === data.dice.length)) {
            socket.emit('roll_dice', {
                game_id: GAME_ID
            });
        }
    }
    
    // Son sıra durumunu sakla
    lastTurn = isMyTurn;
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Sizin sıranız olayını işle
function handleYourTurn(data) {
    console.log("Sizin sıranız:", data);
    
    isMyTurn = true;
    
    // Arayüzü güncelle
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Zarları göster
    if (data.dice && data.dice.length > 0) {
        renderDice(data.dice);
    }
    
    // Bildirim göster
    flashStatusIndicator("Sıra sizde!", "success");
    showNotification("Sıra Sizde", "Hamle yapabilirsiniz!", true);
    addChatMessage({ text: "Sıra sizde! Hamle yapabilirsiniz." }, 'success');
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// DEV: Oyuncu tarafını manuel olarak ayarla
function setPlayerSide(side) {
    playerSide = side;
    console.log("Oyuncu tarafı ayarlandı:", playerSide === SIDE.FIRST ? "Birinci" : "İkinci");
    
    // Sıra kontrolü yap
    isMyTurn = gameState && gameState.current_side === playerSide;
    
    // Arayüzü güncelle
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Butonları güncelle
    document.getElementById('roll-dice-btn').disabled = !isMyTurn;
}

// Oyun durumunu işle
function handleGameState(data) {
    console.log("Oyun durumu güncellendi:", data);
    gameState = data;
    
    // Otomatik oyuncu tarafı atama (ilk kez)
    if (playerSide === null && gameState) {
        // Taraf verisini almaya çalış
        // İlk gelen oyun verisi için varsayılan taraf belirle
        // NOT: Bu sadece tek kullanıcılı test yaparken yardımcı olur
        // Gerçek oyunda socket.on('join') ile playerSide değerini almalıyız
        playerSide = gameState.current_side;
        console.log("Oyuncu tarafı otomatik atandı:", playerSide === SIDE.FIRST ? "Birinci" : "İkinci");
    }
    
    // Sıra kontrolü
    isMyTurn = playerSide === gameState.current_side;
    
    updateBoard();
    updatePlayerInfo();
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Zar gösterimi
    if (gameState.dice && gameState.dice.length > 0) {
        renderDice(gameState.dice);
    }

    // Pas butonu kontrolü - eğer kırık taş varsa ve hamle yapılamıyorsa pas butonu göster
    checkForPassOption();
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
    
    // Durum bildirimini göster
    flashStatusIndicator("Oyun durumu güncellendi", "info");
}

// Pas seçeneği kontrolü
function checkForPassOption() {
    // Pas butonu container'ı
    let passButtonContainer = document.getElementById('pass-button-container');
    
    // Container yoksa oluştur
    if (!passButtonContainer) {
        passButtonContainer = document.createElement('div');
        passButtonContainer.id = 'pass-button-container';
        passButtonContainer.className = 'mt-3 text-center';
        
        // Dice container'ın altına ekle
        const diceContainer = document.getElementById('dice-container');
        diceContainer.parentNode.insertBefore(passButtonContainer, diceContainer.nextSibling);
    }
    
    // Varsayılan olarak pas butonunu gizle
    passButtonContainer.innerHTML = '';
    
    // Kontrol et: Sıra bizde mi, kırık taşımız var mı?
    if (!isMyTurn || !gameState) return;
    
    const hasHitChecker = playerSide === SIDE.FIRST ? 
        gameState.first_hit > 0 : 
        gameState.second_hit > 0;
    
    if (hasHitChecker) {
        // Kırık taş için hamle yapılabilir mi kontrol et
        const canMoveHitChecker = checkIfHitCheckerCanMove();
        
        if (!canMoveHitChecker) {
            // Pas butonu oluştur
            const passButton = document.createElement('button');
            passButton.className = 'btn btn-warning mt-2';
            passButton.innerHTML = 'Pas Geç';
            passButton.onclick = function() {
                sendPassRequest();
            };
            
            // Açıklama ekle
            const helpText = document.createElement('p');
            helpText.className = 'text-muted small mt-1';
            helpText.innerHTML = 'Kırık taşı oynayabileceğiniz hamle yok.';
            
            passButtonContainer.appendChild(passButton);
            passButtonContainer.appendChild(helpText);
            
            // Bildirim göster
            showNotification("Hamle Yapılamıyor", "Kırık taşı oynayabileceğiniz hamle yok. Pas geçebilirsiniz.", false);
        }
    }
}

// Kırık taş için hamle yapılabilir mi kontrol et
function checkIfHitCheckerCanMove() {
    if (!gameState || !gameState.dice) return true; // Varsayılan olarak doğru kabul et
    
    // Oyuncunun tarafını al
    const side = playerSide;
    
    // Zar değerlerini al
    const dice = gameState.dice;
    const dicePlayed = gameState.dice_played || [];
    
    // Oynanabilir zarlar
    const playableDice = dice.filter((_, index) => !dicePlayed.includes(index));
    
    // Hamle yapılabilir mi?
    let canMove = false;
    
    // Oyuncu tarafına göre potansiyel hedef noktaları kontrol et
    for (let dieValue of playableDice) {
        let targetIndex;
        
        if (side === SIDE.FIRST) {
            // Birinci oyuncu için hedef nokta (kırık taşlar tahta dışından girer)
            targetIndex = 24 - dieValue; // 24'ten başlayıp aşağı gider
        } else {
            // İkinci oyuncu için hedef nokta (kırık taşlar tahta dışından girer)
            targetIndex = dieValue - 1; // -1'den başlayıp yukarı gider
        }
        
        // Hedef nokta tahta içinde mi?
        if (targetIndex >= 0 && targetIndex < 24) {
            // Hedef noktadaki taş
            const targetPoint = gameState.board.find(p => p.index === targetIndex);
            
            // Hedef nokta boş ya da bizim taşımız varsa veya rakibin tek taşı varsa hamle yapılabilir
            if (!targetPoint || targetPoint.side === null || 
                targetPoint.side === side || 
                (targetPoint.side !== side && targetPoint.count === 1)) {
                canMove = true;
                break;
            }
        }
    }
    
    return canMove;
}

// Pas geçme isteği gönder
function sendPassRequest() {
    // Kontrol: Sıra bizde mi?
    if (!isMyTurn) {
        showNotification("Uyarı", "Şu anda sizin sıranız değil!");
        return;
    }
    
    console.log("Pas geçme isteği gönderiliyor...");
    socket.emit('pass_turn', {
        game_id: GAME_ID
    });
    
    // Pas butonunu gizle
    const passButtonContainer = document.getElementById('pass-button-container');
    if (passButtonContainer) {
        passButtonContainer.innerHTML = '';
    }
}

// Başlangıç zarlarını işle
function handleTurnRolls(data) {
    console.log("Tur zarları geldi:", data);
    const message = `Sıra belirlemek için atılan zarlar: Birinci: ${data.first}, İkinci: ${data.second}`;
    addChatMessage({ text: message }, 'system');
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Hamle zarlarını işle
function handleMoveRolls(data) {
    console.log("Hamle zarları geldi:", data);
    const dice = data.dice;
    const side = data.side;
    
    // Sıra kontrolü yap
    isMyTurn = playerSide === side;
    
    // Zarları göster
    renderDice(dice);
    
    // Sıranın kimde olduğunu güncelle
    updateCurrentPlayerIndicator();
    updateTurnIndicator();
    
    // Seçimleri temizle
    clearSelections();
    
    // Bildirim göster
    if (isMyTurn) {
        addChatMessage({ text: "Sıra sizde. Zar atıldı, hamle yapabilirsiniz." }, 'success');
        flashStatusIndicator("Zarlar atıldı, sıra sizde!", "success");
        showNotification("Sıra Sizde", "Zar atıldı, hamle yapabilirsiniz.", true);
    } else {
        addChatMessage({ text: "Sıra rakipte. Bekleyin." }, 'system');
        flashStatusIndicator("Zarlar atıldı, sıra rakipte", "info");
    }
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Başarılı hamleyi işle
function handleMoveSuccess() {
    // Hamle başarılı olduğunda yapılacak işlemler
    console.log("Hamle başarılı!");
    flashStatusIndicator("Hamle başarılı", "success");
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Oyun kazanıldı mesajını işle
function handleGameWon(data) {
    const winner = data.winner === SIDE.FIRST ? "Birinci" : "İkinci";
    console.log("Oyun bitti, kazanan:", winner);
    
    // Bildirim modalı göster
    showNotification("Oyun Bitti", `${winner} oyuncu kazandı!`, true);
    flashStatusIndicator(`${winner} oyuncu kazandı!`, "success");
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Chat mesajını işle
function handleChatMessage(data) {
    addChatMessage(data);
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Hata mesajını işle
function handleError(data) {
    console.error("Sunucu hatası:", data.message);
    showNotification("Hata", data.message);
    flashStatusIndicator(data.message, "error");
    addChatMessage({ text: `Hata: ${data.message}` }, 'alert');
}

// Bildirim göster (genelleştirilmiş fonksiyon)
function showNotification(title, message, refreshAfterClose = false) {
    // Sayfa yenileme bayrağını ayarla
    shouldRefreshAfterModal = refreshAfterClose;
    
    // Bootstrap modal kullanalım
    const modal = new bootstrap.Modal(document.getElementById('notification-modal'));
    document.getElementById('notification-title').textContent = title;
    document.getElementById('notification-body').textContent = message;
    
    // Yenileme bilgisini göster/gizle
    const refreshInfo = document.getElementById('refresh-info');
    if (refreshAfterClose) {
        refreshInfo.classList.remove('d-none');
    } else {
        refreshInfo.classList.add('d-none');
    }
    
    modal.show();
    
    // Ayrıca chat'e de ekleyelim
    addChatMessage({ text: `${title}: ${message}` }, 'system');
    
    // Konsola da yazalım
    console.log(`${title}: ${message}`, refreshAfterClose ? "(Kapandığında sayfa yenilenecek)" : "");
}

// Tahta durumunu güncelle
function updateBoard() {
    if (!gameState) return;
    
    // Tahtayı temizle
    clearBoard();
    
    // Üst tahtayı oluştur (12-23)
    const upperContainer = document.querySelector('.board-upper .point-container');
    for (let i = 12; i < 24; i++) {
        const point = createPoint(i, true);
        upperContainer.appendChild(point);
    }
    
    // Alt tahtayı oluştur (11-0)
    const lowerContainer = document.querySelector('.board-lower .point-container');
    for (let i = 11; i >= 0; i--) {
        const point = createPoint(i, false);
        lowerContainer.appendChild(point);
    }
    
    // Kırılan taşları göster
    renderHitCheckers();
    
    // Çıkarılan taşları göster
    renderBorneCheckers();
}

// Oyuncu bilgilerini güncelle
function updatePlayerInfo() {
    if (!gameState) return;
    
    document.getElementById('first-hit').textContent = gameState.first_hit;
    document.getElementById('first-borne').textContent = gameState.first_borne;
    document.getElementById('second-hit').textContent = gameState.second_hit;
    document.getElementById('second-borne').textContent = gameState.second_borne;
}

// Sıranın kimde olduğunu göster
function updateCurrentPlayerIndicator() {
    if (!gameState) return;
    
    const currentPlayerElement = document.getElementById('current-player');
    const currentSide = gameState.current_side;
    
    currentPlayerElement.textContent = currentSide === SIDE.FIRST ? "Birinci Oyuncu" : "İkinci Oyuncu";
    currentPlayerElement.className = `badge ${currentSide === SIDE.FIRST ? "bg-primary" : "bg-danger"}`;
    
    // Sıra kontrolünü güncelle
    isMyTurn = playerSide === currentSide;
    
    // Eğer oyuncunun sırası ise zar atma butonunu aktifleştir
    const rollDiceBtn = document.getElementById('roll-dice-btn');
    rollDiceBtn.disabled = !isMyTurn;
    
    // Sıra durumunu konsola yaz (debug)
    console.log("Sıra:", currentSide === SIDE.FIRST ? "Birinci" : "İkinci", "oyuncuda. Benim tarafım:", 
                playerSide === SIDE.FIRST ? "Birinci" : "İkinci", 
                "Sıra bende mi:", isMyTurn);
}

// Tahtayı temizle
function clearBoard() {
    document.querySelector('.board-upper .point-container').innerHTML = '';
    document.querySelector('.board-lower .point-container').innerHTML = '';
    document.getElementById('first-hit-area').innerHTML = '';
    document.getElementById('second-hit-area').innerHTML = '';
    document.getElementById('first-borne-area').innerHTML = '';
    document.getElementById('second-borne-area').innerHTML = '';
}

// Nokta oluştur
function createPoint(index, isUpper) {
    const point = document.createElement('div');
    point.className = `point ${isUpper ? 'upper' : 'lower'} ${(index % 2 === 0) ? 'dark' : 'light'}`;
    point.dataset.index = index;
    
    // Nokta indeks numarasını göster
    const indexElement = document.createElement('span');
    indexElement.className = 'point-index';
    indexElement.textContent = index;
    point.appendChild(indexElement);
    
    // Bu noktadaki taşları ekle
    const pointData = gameState.board.find(p => p.index === index);
    if (pointData && pointData.count > 0) {
        for (let i = 0; i < pointData.count; i++) {
            const checker = createChecker(pointData.side);
            point.appendChild(checker);
        }
    }
    
    // Tıklama olayı ekle
    point.addEventListener('click', function() {
        handlePointClick(index);
    });
    
    return point;
}

// Taş oluştur
function createChecker(side) {
    const checker = document.createElement('div');
    checker.className = `checker ${side === SIDE.FIRST ? 'first' : 'second'}`;
    return checker;
}

// Kırılan taşları göster
function renderHitCheckers() {
    const firstHitArea = document.getElementById('first-hit-area');
    const secondHitArea = document.getElementById('second-hit-area');
    
    // Varolan içeriği temizle
    firstHitArea.innerHTML = '';
    secondHitArea.innerHTML = '';
    
    // Birinci oyuncunun kırılan taşları
    for (let i = 0; i < gameState.first_hit; i++) {
        const checker = createChecker(SIDE.FIRST);
        firstHitArea.appendChild(checker);
    }
    
    // İkinci oyuncunun kırılan taşları
    for (let i = 0; i < gameState.second_hit; i++) {
        const checker = createChecker(SIDE.SECOND);
        secondHitArea.appendChild(checker);
    }
    
    // Kırılan taşlar için tıklama olayları
    firstHitArea.addEventListener('click', function() {
        if (gameState.current_side === SIDE.FIRST && gameState.first_hit > 0 && isMyTurn) {
            handleHitAreaClick(SIDE.FIRST);
        }
    });
    
    secondHitArea.addEventListener('click', function() {
        if (gameState.current_side === SIDE.SECOND && gameState.second_hit > 0 && isMyTurn) {
            handleHitAreaClick(SIDE.SECOND);
        }
    });
}

// Çıkarılan taşları göster
function renderBorneCheckers() {
    const firstBorneArea = document.getElementById('first-borne-area');
    const secondBorneArea = document.getElementById('second-borne-area');
    
    // Varolan içeriği temizle
    firstBorneArea.innerHTML = '';
    secondBorneArea.innerHTML = '';
    
    // Birinci oyuncunun çıkardığı taşlar
    for (let i = 0; i < gameState.first_borne; i++) {
        const checker = createChecker(SIDE.FIRST);
        firstBorneArea.appendChild(checker);
    }
    
    // İkinci oyuncunun çıkardığı taşlar
    for (let i = 0; i < gameState.second_borne; i++) {
        const checker = createChecker(SIDE.SECOND);
        secondBorneArea.appendChild(checker);
    }
}

// Zarları göster
function renderDice(dice) {
    const diceContainer = document.getElementById('dice-container');
    diceContainer.innerHTML = '';
    
    console.log("Zarlar gösteriliyor:", dice, "Oynanmış zarlar:", gameState.dice_played);
    
    dice.forEach((value, index) => {
        const diceElement = document.createElement('div');
        diceElement.className = `dice ${gameState.dice_played.includes(index) ? 'played' : ''}`;
        diceElement.textContent = value;
        diceElement.dataset.index = index;
        
        // Oynanmamış zarlar için tıklama olayı ekle
        if (!gameState.dice_played.includes(index) && isMyTurn) {
            diceElement.addEventListener('click', function() {
                handleDiceClick(index);
            });
        }
        
        diceContainer.appendChild(diceElement);
    });
}

function handlePointClick(index) {
    // Sıranın bizde olup olmadığını kontrol et
    if (!isMyTurn) {
        showNotification("Uyarı", "Şu anda sizin sıranız değil!");
        return;
    }
    
    // Oyuncu rolü kontrol et
    if (playerSide === null || (gameState.current_side !== playerSide)) {
        showNotification("Uyarı", "Bu tarafın hamle yapma hakkınız yok!");
        return;
    }

    console.log("Nokta tıklandı:", index);
    const pointData = gameState.board.find(p => p.index === index);

    if (selectedDieIndex === null) {
        showNotification("Uyarı", "Önce bir zar seçmelisiniz!");
        return;
    }

    // ✅ Eğer bir taş zaten seçildiyse, bu tıklama artık HAMLENİN HEDEFİDİR
    if (selectedPoint !== null) {
        if (index === selectedPoint) {
            // Aynı noktaya tıkladıysa seçim iptal
            clearSelections();
            return;
        }

        console.log("Hamle yapılıyor, zar:", selectedDieIndex, "kaynak:", selectedPoint,"hedef:",index);
        makeMove(selectedDieIndex, selectedPoint,index);
        return;
    }

    // 🔽 Aksi halde bu ilk tıklamadır (taş seçimi yapılmamış)
    // Seçilen taş bizim tarafımızın mı kontrol et
    if (pointData && pointData.side === playerSide) {
        // Taş seçme
        selectedPoint = index;
        highlightSelectedPoint(index);
        console.log("Taş seçildi, kaynak:", index);
    } else {
        showNotification("Geçersiz Seçim", "Kendi taşınızı seçmelisiniz!");
    }
}


// Kırılan taş alanı tıklama işleyicisi
function handleHitAreaClick(side) {
    // Oyuncunun sırası değilse hiçbir şey yapma
    if (!isMyTurn) {
        showNotification("Uyarı", "Şu anda sizin sıranız değil!");
        return;
    }
    
    console.log("Kırılan taş alanı tıklandı, taraf:", side);
    
    // Zar seçilmişse hamle yap (kaynak null olacak)
    if (selectedDieIndex !== null) {
        console.log("Kırılan taşla hamle yapılıyor, zar:", selectedDieIndex);
        makeMove(selectedDieIndex, null);
    } else {
        // Oyuncuya zarı seçmesini hatırlat
        showNotification("Uyarı", "Önce bir zar seçmelisiniz!");
    }
}

// Zar tıklama işleyicisi
function handleDiceClick(index) {
    console.log("Zar tıklandı, indeks:", index);
    
    // Seçili zarı değiştir
    selectedDieIndex = index;
    
    // Tüm zarları normal hale getir
    document.querySelectorAll('.dice').forEach(dice => {
        dice.classList.remove('selected');
    });
    
    // Seçili zarı vurgula
    const selectedDice = document.querySelector(`.dice[data-index="${index}"]`);
    if (selectedDice) {
        selectedDice.classList.add('selected');
    }
}

// Seçili noktayı vurgula
function highlightSelectedPoint(index) {
    // Tüm noktaları normal hale getir
    document.querySelectorAll('.point').forEach(point => {
        point.classList.remove('selected');
    });
    
    // Seçili noktayı vurgula
    const selectedPointElement = document.querySelector(`.point[data-index="${index}"]`);
    if (selectedPointElement) {
        selectedPointElement.classList.add('selected');
    }
}

// Hamle yap
function makeMove(dieIndex, source) {
    // Sıra bizde değilse hamle yapma
    if (!isMyTurn) {
        console.log("Hamle yapılamadı: Şu anda sıra sizde değil!");
        showNotification("Uyarı", "Şu anda sıra sizde değil!");
        return;
    }
    
    console.log("Hamle yapılıyor:", {
        game_id: GAME_ID, 
        die_index: dieIndex, 
        source: source, 
        playerSide: playerSide,
        current_side: gameState ? gameState.current_side : 'unknown'
    });
    
    // Kırılmış taş için özel durum kontrolü
    const isPlayerHit = playerSide === SIDE.FIRST ? 
        (gameState && gameState.first_hit > 0) : 
        (gameState && gameState.second_hit > 0);
    
    // Kırılmış taşı varsa source null olmalı
    if (isPlayerHit) {
        console.log("Kırılmış taş ile hamle yapılıyor, source null olarak ayarlanıyor");
        source = null;
    }
    
    socket.emit('move', {
        game_id: GAME_ID,
        die_index: dieIndex,
        source: source
    });
    
    // Seçimleri temizle
    clearSelections();
}

// Seçimleri temizle
function clearSelections() {
    selectedPoint = null;
    selectedDieIndex = null;
    
    // Tüm seçimleri kaldır
    document.querySelectorAll('.point.selected').forEach(point => {
        point.classList.remove('selected');
    });
    
    document.querySelectorAll('.dice.selected').forEach(dice => {
        dice.classList.remove('selected');
    });
}

// Chat mesajı gönder
function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const message = chatInput.value.trim();
    
    if (message) {
        socket.emit('chat_message', {
            game_id: GAME_ID,
            message: message
        });
        
        chatInput.value = '';
    }
}

// Chat mesajı ekle
function addChatMessage(data, type = '') {
    const chatMessages = document.getElementById('chat-messages');
    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${type}`;
    messageElement.textContent = data.text;
    chatMessages.appendChild(messageElement);
    
    // Otomatik olarak en son mesaja kaydır
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Oyuncunun tarafını işle
function handlePlayerSide(data) {
    playerSide = data.side;
    console.log("Oyuncu tarafı sunucudan alındı:", playerSide === SIDE.FIRST ? "Birinci (0)" : (playerSide === SIDE.SECOND ? "İkinci (1)" : "İzleyici (null)"));
    console.log("Raw playerSide value:", playerSide);
    
    // UI'da oyuncu tarafı bilgisini göster
    const sideIndicator = document.getElementById('player-side-indicator');
    if (sideIndicator) {
        if (playerSide === SIDE.FIRST) {
            sideIndicator.textContent = 'Birinci Oyuncu';
            sideIndicator.className = 'badge bg-primary';
        } else if (playerSide === SIDE.SECOND) {
            sideIndicator.textContent = 'İkinci Oyuncu';
            sideIndicator.className = 'badge bg-danger';
        } else {
            sideIndicator.textContent = 'İzleyici';
            sideIndicator.className = 'badge bg-secondary';
        }
    } else {
        // Eğer gösterge henüz yoksa, oluştur
        const container = document.createElement('div');
        container.className = 'mt-3 player-side-info text-center p-2 border rounded';
        
        const sideTitle = document.createElement('h5');
        sideTitle.className = 'mb-2';
        sideTitle.textContent = 'Oyuncu Tarafınız:';
        
        const sideValue = document.createElement('div');
        sideValue.id = 'player-side-indicator';
        sideValue.className = playerSide === SIDE.FIRST ? 'badge bg-primary' : 
                             (playerSide === SIDE.SECOND ? 'badge bg-danger' : 'badge bg-secondary');
        sideValue.textContent = playerSide === SIDE.FIRST ? 'Birinci Oyuncu' : 
                             (playerSide === SIDE.SECOND ? 'İkinci Oyuncu' : 'İzleyici');
        
        container.appendChild(sideTitle);
        container.appendChild(sideValue);
        
        // Uygun bir yere ekle
        const cardBody = document.querySelector('.card-body');
        if (cardBody) {
            cardBody.appendChild(container);
        }
    }
    
    // Sıra kontrolü yap (eğer oyun durumu zaten yüklendiyse)
    if (gameState) {
        isMyTurn = gameState.current_side === playerSide;
        console.log("Sıra kontrolü: gameState.current_side =", gameState.current_side, "playerSide =", playerSide, "isMyTurn =", isMyTurn);
        updateCurrentPlayerIndicator();
        updateTurnIndicator();
    }
    
    // Bildirim göster
    let sideText = "";
    if (playerSide === SIDE.FIRST) sideText = "Birinci";
    else if (playerSide === SIDE.SECOND) sideText = "İkinci";
    else sideText = "İzleyici";
    
    flashStatusIndicator(`${sideText} oyuncu olarak atandınız`, "success");
    addChatMessage({ text: `${sideText} oyuncu olarak atandınız` }, 'success');
    
    // Tahtayı güncelle - kendi tarafımızı vurgulama ve kontrol için
    if (gameState) updateBoard();
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
}

// Pas kabul edildi olayını işle
function handlePassAccepted(data) {
    console.log("Pas geçme kabul edildi:", data);
    
    // Bildirim göster
    flashStatusIndicator("Pas geçildi, sıra rakibe geçti", "info");
    addChatMessage({ text: "Hamle yapılamadığı için pas geçildi, sıra rakibe geçti." }, 'system');
    
    // Pas butonunu kaldır
    const passButtonContainer = document.getElementById('pass-button-container');
    if (passButtonContainer) {
        passButtonContainer.innerHTML = '';
    }
    
    // Son güncelleme zamanını kaydet
    lastUpdateTime = Date.now();
} 