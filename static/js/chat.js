// Enhanced file upload and message handling
document.addEventListener('DOMContentLoaded', function() {
    // Get necessary elements and setup
    const fileInput = document.getElementById('myFile');
    const chatMessageSubmit = document.getElementById('chat-message-submit');
    const messageInput = document.getElementById('message_input');
    const fileNameDisplay = document.getElementById('selected-file-name');

    // Calculate room name for consistency with the server
    const id = JSON.parse(document.getElementById('json-username').textContent);
    const message_username = JSON.parse(document.getElementById('json-message-username').textContent);
    const receiver = JSON.parse(document.getElementById('json-username-receiver').textContent);
    const currentUserId = JSON.parse(document.getElementById('json-current-user-id').textContent);

    let roomName;
    if (parseInt(currentUserId) > parseInt(id)) {
        roomName = `${currentUserId}-${id}`;
    } else {
        roomName = `${id}-${currentUserId}`;
    }

    // Setup WebSocket
    const socket = new WebSocket(
        'ws://' + window.location.host + '/ws/' + id + '/'
    );

    socket.onopen = function(e) {
        console.log("CONNECTION ESTABLISHED");
    };

    socket.onclose = function(e) {
        console.log("CONNECTION LOST");
    };

    socket.onerror = function(e) {
        console.log("ERROR OCCURRED");
    };

    // Enhanced message receiver
    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log("Message received:", data);

        // Create HTML for message content based on message type
        let messageContent;

        // Check if this is a file message
        if (data.message_type === 'file' && data.file_data) {
            const fileData = data.file_data;

            if (fileData.file_type.startsWith('image/')) {
                messageContent = `
                    <div>
                        <img src="${fileData.file_url}" alt="${fileData.filename}" style="max-width: 200px; max-height: 150px; border-radius: 5px; margin-bottom: 5px;">
                        <div><a href="${fileData.file_url}" download style="color: white; text-decoration: underline;">${fileData.filename}</a></div>
                    </div>`;
            } else if (fileData.file_type === 'application/pdf' || fileData.filename.toLowerCase().endsWith('.pdf')) {
                // For PDFs - show PDF icon
                messageContent = `
                    <div>
                        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="white" style="margin-bottom: 5px;">
                            <path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z"/>
                        </svg>
                        <div><a href="${fileData.file_url}" target="_blank" download style="color: white; text-decoration: underline;">${fileData.filename}</a></div>
                    </div>`;
            } else {
                // For other files - generic file icon
                messageContent = `
                    <div>
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="white" style="margin-bottom: 5px;">
                            <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                        </svg>
                        <div><a href="${fileData.file_url}" download style="color: white; text-decoration: underline;">${fileData.filename}</a></div>
                        <small style="color: rgba(255,255,255,0.7);">${formatFileSize(fileData.file_size)}</small>
                    </div>`;
            }
        } else {
            // Regular text message
            messageContent = data.message;
        }

        // Add message to chat
        if (data.username == message_username) {
            document.querySelector('#chat-body').innerHTML += `
                <tr>
                    <td>
                        <p class="bg-success p-2 mt-2 mr-5 shadow-sm text-white float-right rounded">
                            ${messageContent}
                        </p>
                    </td>
                    <td>
                        <p><small class="p-1 shadow-sm">${getCurrentTime()}</small></p>
                    </td>
                </tr>`;
        } else {
            document.querySelector('#chat-body').innerHTML += `
                <tr>
                    <td>
                        <p class="bg-primary p-2 mt-2 mr-5 shadow-sm text-white float-left rounded">
                            ${messageContent}
                        </p>
                    </td>
                    <td>
                        <p><small class="p-1 shadow-sm">${getCurrentTime()}</small></p>
                    </td>
                </tr>`;
        }

        // Scroll to bottom of chat
        const chatBody = document.querySelector('.message-table-scroll');
        chatBody.scrollTop = chatBody.scrollHeight;
    };

    // Helper function to get current time
    function getCurrentTime() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' +
               now.getMinutes().toString().padStart(2, '0');
    }

    // Helper function to format file size
    function formatFileSize(size) {
        if (!size) return '';
        const i = Math.floor(Math.log(size) / Math.log(1024));
        return (size / Math.pow(1024, i)).toFixed(1) + ' ' + ['B', 'KB', 'MB', 'GB', 'TB'][i];
    }

    // Helper function to get cookies (for CSRF token)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Get CSRF token
    const csrftoken = getCookie('csrftoken');

    // Handle file selection
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const file = this.files[0];
                // Show file name on the UI
                fileNameDisplay.textContent = file.name;
                fileNameDisplay.style.display = 'block';
                // Update message input placeholder
                messageInput.placeholder = `Ready to send: ${file.name}`;
            } else {
                fileNameDisplay.textContent = '';
                fileNameDisplay.style.display = 'none';
                messageInput.placeholder = 'Write message...';
            }
        });
    }

    // Submit handler for both text messages and file uploads
    if (chatMessageSubmit) {
        chatMessageSubmit.onclick = async function(e) {
            e.preventDefault();

            const message = messageInput.value.trim();
            const file = fileInput.files[0];

            // Handle file upload if a file is selected
            if (file) {
                // Create loading indicator in chat
                const tempMessageId = 'temp-' + Date.now();
                document.querySelector('#chat-body').innerHTML += `
                    <tr id="${tempMessageId}">
                        <td>
                            <p class="bg-success p-2 mt-2 mr-5 shadow-sm text-white float-right rounded">
                                <div>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="white" class="animate-spin" style="animation: spin 2s linear infinite;">
                                        <path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/>
                                    </svg>
                                    <div>Uploading ${file.name}...</div>
                                </div>
                            </p>
                        </td>
                        <td>
                            <p><small class="p-1 shadow-sm">${getCurrentTime()}</small></p>
                        </td>
                    </tr>`;

                // Scroll to see the loading message
                const chatBody = document.querySelector('.message-table-scroll');
                chatBody.scrollTop = chatBody.scrollHeight;

                // Create FormData object for file upload
                const formData = new FormData();
                formData.append('file', file);
                formData.append('thread_name', `chat_${roomName}`);

                try {
                    // Send file to server
                    const response = await fetch('/service_worker/upload-file/', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': csrftoken
                        },
                        credentials: 'same-origin'
                    });

                    if (!response.ok) {
                        throw new Error('Upload failed: ' + response.status);
                    }

                    const result = await response.json();

                    if (result.status === 'success') {
                        // Remove loading message
                        document.getElementById(tempMessageId).remove();

                        // Get the full URL for the file
                        let fileUrl = result.file_url;
                        if (!fileUrl.startsWith('http')) {
                            fileUrl = window.location.origin + fileUrl;
                        }

                        // Send WebSocket message with file info
                        socket.send(JSON.stringify({
                            'username': message_username,
                            'receiver': receiver,
                            'type': 'file',
                            'file_data': {
                                'file_id': result.file_id,
                                'filename': result.filename,
                                'file_url': fileUrl,
                                'file_type': result.file_type || file.type,
                                'file_size': file.size
                            }
                        }));

                        // Reset file input and message placeholder
                        fileInput.value = '';
                        fileNameDisplay.textContent = '';
                        fileNameDisplay.style.display = 'none';
                        messageInput.placeholder = 'Write message...';
                    } else {
                        // Show error message
                        document.getElementById(tempMessageId).innerHTML = `
                            <td>
                                <p class="bg-danger p-2 mt-2 mr-5 shadow-sm text-white float-right rounded">
                                    Failed to upload: ${result.error || 'Unknown error'}
                                </p>
                            </td>
                            <td>
                                <p><small class="p-1 shadow-sm">${getCurrentTime()}</small></p>
                            </td>`;
                    }
                } catch (error) {
                    console.error('Error uploading file:', error);
                    // Show error message
                    document.getElementById(tempMessageId).innerHTML = `
                        <td>
                            <p class="bg-danger p-2 mt-2 mr-5 shadow-sm text-white float-right rounded">
                                Error: ${error.message}
                            </p>
                        </td>
                        <td>
                            <p><small class="p-1 shadow-sm">${getCurrentTime()}</small></p>
                        </td>`;
                }
            }

            // Handle text message if present
            if (message) {
                socket.send(JSON.stringify({
                    'message': message,
                    'username': message_username,
                    'receiver': receiver,
                    'type': 'text'
                }));
                
                messageInput.value = '';
            }
        };
    }
    
    // Handle Enter key press for text messages
    if (messageInput) {
        messageInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                chatMessageSubmit.click();
            }
        });
    }
});