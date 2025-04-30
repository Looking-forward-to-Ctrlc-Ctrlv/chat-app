document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const newGroupBtn = document.getElementById('new-group-btn');
    const groupModal = document.getElementById('group-creation-modal');
    const closeGroupModal = document.querySelector('.close-group-modal');
    const createGroupBtn = document.getElementById('create-group-btn');
    const groupNameInput = document.getElementById('group-name');
    const groupMemberCheckboxes = document.querySelectorAll('.group-member-list input[type="checkbox"]');
    const groupChatItems = document.querySelectorAll('.group-chat');
    const currentChatType = document.getElementById('current-chat-type');
    const currentChatId = document.getElementById('current-chat-id');
    const currentChatName = document.getElementById('current-chat-name');
    const messageBox = document.getElementById('message-box');
    const chatBody = document.getElementById('chat-body');

    // WebSocket connection for group chat
    let groupSocket = null;

    // Open group creation modal
    if (newGroupBtn) {
        newGroupBtn.addEventListener('click', function() {
            groupModal.style.display = 'block';
        });
    }

    // Close group creation modal
    if (closeGroupModal) {
        closeGroupModal.addEventListener('click', function() {
            groupModal.style.display = 'none';
        });
    }

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === groupModal) {
            groupModal.style.display = 'none';
        }
    });

    // Create new group
    if (createGroupBtn) {
        createGroupBtn.addEventListener('click', async function() {
            const groupName = groupNameInput.value.trim();
            const selectedMembers = [];

            groupMemberCheckboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    selectedMembers.push(checkbox.value);
                }
            });

            if (!groupName) {
                alert('Please enter a group name');
                return;
            }

            if (selectedMembers.length < 1) {
                alert('Please select at least one member');
                return;
            }

            try {
                const response = await fetch('/group/create/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        name: groupName,
                        members: selectedMembers
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    // Close the modal
                    groupModal.style.display = 'none';

                    // Clear inputs
                    groupNameInput.value = '';
                    groupMemberCheckboxes.forEach(checkbox => {
                        checkbox.checked = false;
                    });

                    // Load the new group chat immediately
                    if (data.group_id) {
                        loadGroupChat(data.group_id);
                    } else {
                        // Or reload the page to show the new group
                        window.location.reload();
                    }
                } else {
                    alert('Error creating group: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error creating group:', error);
                alert('Error creating group. Please try again.');
            }
        });
    }

    // Handle group chat item clicks
    groupChatItems.forEach(item => {
        item.addEventListener('click', function() {
            const groupId = this.getAttribute('data-groupid');
            loadGroupChat(groupId);
        });
    });

    // Function to load a group chat
    async function loadGroupChat(groupId) {
        try {
            // Fetch group details and messages
            const response = await fetch(`/group/${groupId}/messages/`);
            const data = await response.json();

            if (response.ok) {
                // Update UI to show group chat
                currentChatType.value = 'group';
                currentChatId.value = groupId;
                currentChatName.textContent = data.group.name;

                // Clear and populate chat messages
                chatBody.innerHTML = '';
                data.messages.forEach(message => {
                    const isCurrentUser = message.is_current_user;
                    const messageClass = isCurrentUser ? 'bg-success float-right' : 'bg-primary float-left';
                    const senderName = isCurrentUser ? 'You' : message.sender.username;

                    chatBody.innerHTML += `
                        <tr>
                            <td>
                                <p class="${messageClass} p-2 mt-2 mr-5 shadow-sm text-white rounded">
                                    ${senderName}: ${message.content}
                                </p>
                            </td>
                            <td>
                                <p><small class="p-1 shadow-sm">${new Date(message.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</small></p>
                            </td>
                        </tr>`;
                });

                // Scroll to bottom
                const messageTable = document.querySelector('.message-table-scroll');
                messageTable.scrollTop = messageTable.scrollHeight;

                // Initialize WebSocket for group chat
                initializeGroupWebSocket(groupId);

                // Show message box
                messageBox.style.display = 'flex';
            } else {
                console.error('Error loading group chat:', data.error);
                alert('Error loading group chat: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error loading group chat:', error);
            alert('Error loading group chat. Please try again.');
        }
    }

    // Initialize WebSocket connection for group chat
    function initializeGroupWebSocket(groupId) {
        // Close existing connection if any
        if (groupSocket) {
            groupSocket.close();
        }

        // Create new WebSocket connection
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        groupSocket = new WebSocket(
            wsProtocol + window.location.host + '/ws/group/' + groupId + '/'
        );

        groupSocket.onopen = function(e) {
            console.log("Group chat connection established");
        };

        groupSocket.onclose = function(e) {
            console.log("Group chat connection closed");
            // Try to reconnect after a delay if it was not closed intentionally
            setTimeout(function() {
                if (currentChatType.value === 'group' && currentChatId.value === groupId) {
                    initializeGroupWebSocket(groupId);
                }
            }, 3000);
        };

        groupSocket.onerror = function(e) {
            console.log("Group chat error occurred");
        };

        groupSocket.onmessage = function(e) {
            const data = JSON.parse(e.data);
            console.log("Group message received:", data);

            // Add new message to chat
            const isCurrentUser = data.sender.id === parseInt(document.getElementById('json-current-user-id').textContent);
            const messageClass = isCurrentUser ? 'bg-success float-right' : 'bg-primary float-left';
            const senderName = isCurrentUser ? 'You' : data.sender.username;

            chatBody.innerHTML += `
                <tr>
                    <td>
                        <p class="${messageClass} p-2 mt-2 mr-5 shadow-sm text-white rounded">
                            ${senderName}: ${data.message}
                        </p>
                    </td>
                    <td>
                        <p><small class="p-1 shadow-sm">${new Date(data.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</small></p>
                    </td>
                </tr>`;

            // Scroll to bottom
            const messageTable = document.querySelector('.message-table-scroll');
            messageTable.scrollTop = messageTable.scrollHeight;
        };

        // Handle message submission
        const messageSubmit = document.getElementById('chat-message-submit');
        const messageInput = document.getElementById('message_input');

        messageSubmit.onclick = function(e) {
            e.preventDefault();
            sendMessage();
        };

        // Handle Enter key
        messageInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Function to send messages
        function sendMessage() {
            const message = messageInput.value.trim();

            if (message && groupSocket && groupSocket.readyState === WebSocket.OPEN) {
                groupSocket.send(JSON.stringify({
                    'message': message,
                    'sender': document.getElementById('json-current-user-id').textContent
                }));

                messageInput.value = '';
            }
        }
    }

    // Helper function to get cookies
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
});