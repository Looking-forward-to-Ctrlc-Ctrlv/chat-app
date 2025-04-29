// Online Status WebSocket
const onlineSocket = new WebSocket(
    'ws://'
    + window.location.host
    + '/ws/online/'
);

// Handle connection events
onlineSocket.onopen = function(e) {
    console.log("Online status socket connected");
    
    // Send online status when connected
    const username = JSON.parse(document.getElementById('json-message-username').textContent);
    onlineSocket.send(JSON.stringify({
        'username': username,
        'type': 'open'
    }));
};

// Handle online status messages
onlineSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    const username = data.username;
    const onlineStatus = data.online_status;
    
    // Update user status in the contacts list
    const userStatus = document.getElementById(`${username}_status`);
    if (userStatus) {
        userStatus.style.color = onlineStatus ? 'green' : 'grey';
    }
    
    // Update user status in the chat header if applicable
    const userStatusSmall = document.getElementById(`${username}_small`);
    if (userStatusSmall) {
        userStatusSmall.textContent = onlineStatus ? 'Online' : 'Offline';
    }
};

// Update status when leaving the page
window.addEventListener('beforeunload', function() {
    const username = JSON.parse(document.getElementById('json-message-username').textContent);
    onlineSocket.send(JSON.stringify({
        'username': username,
        'type': 'close'
    }));
});

onlineSocket.onclose = function(e) {
    console.log("Online status socket disconnected");
};