// ui.js - UI manipulation and rendering functions

// DOM element cache
const elements = {
    conversationList: null,
    chatMessages: null,
    messageInput: null,
    sendButton: null,
    messageForm: null,
    newConversationBtn: null,
    emptyState: null
};

// Initialize DOM element references
function initUIElements() {
    elements.conversationList = document.getElementById('conversation-list');
    elements.chatMessages = document.getElementById('chat-messages');
    elements.messageInput = document.getElementById('message-input');
    elements.sendButton = document.getElementById('send-button');
    elements.messageForm = document.getElementById('message-form');
    elements.newConversationBtn = document.getElementById('new-conversation-btn');
    elements.emptyState = document.getElementById('empty-state');
}

// Render conversation list in sidebar
function renderConversationList() {
    const conversations = getAllConversations();
    const activeId = getActiveConversationId();

    if (!elements.conversationList) return;

    elements.conversationList.innerHTML = '';

    if (conversations.length === 0) {
        elements.conversationList.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-secondary);">No conversations yet</div>';
        return;
    }

    // Sort by updated_at (most recent first)
    conversations.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

    conversations.forEach(conversation => {
        const item = document.createElement('div');
        item.className = 'conversation-item';
        item.dataset.id = conversation.id;

        if (conversation.id === activeId) {
            item.classList.add('active');
        }

        const title = document.createElement('div');
        title.className = 'conversation-title';
        title.textContent = conversation.title;

        const time = document.createElement('div');
        time.className = 'conversation-time';
        time.textContent = formatTimestamp(conversation.updated_at);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = '×';
        deleteBtn.dataset.id = conversation.id;
        deleteBtn.title = 'Delete conversation';

        item.appendChild(title);
        item.appendChild(time);
        item.appendChild(deleteBtn);

        elements.conversationList.appendChild(item);
    });
}

// Render messages for current conversation
function renderMessages(conversationId) {
    if (!conversationId) {
        showEmptyState();
        return;
    }

    const conversation = getConversation(conversationId);
    if (!conversation) {
        showEmptyState();
        return;
    }

    hideEmptyState();
    clearChatDisplay();

    conversation.messages.forEach(message => {
        addMessageToUI(message, false);
    });

    scrollToBottom();
}

// Add a message to the chat display
function addMessageToUI(message, shouldScroll = true) {
    if (!elements.chatMessages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = message.content;

    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'message-timestamp';
    timestampDiv.textContent = formatTimestamp(message.timestamp);

    contentDiv.appendChild(textDiv);
    contentDiv.appendChild(timestampDiv);
    messageDiv.appendChild(contentDiv);

    elements.chatMessages.appendChild(messageDiv);

    if (shouldScroll) {
        scrollToBottom();
    }
}

// Show thinking animation
function showThinkingAnimation() {
    const template = document.getElementById('thinking-template');
    if (!template) return;

    const thinkingElement = template.content.cloneNode(true);
    elements.chatMessages.appendChild(thinkingElement);
    scrollToBottom();
}

// Hide thinking animation
function hideThinkingAnimation() {
    const thinkingMessage = elements.chatMessages.querySelector('.thinking-message');
    if (thinkingMessage) {
        thinkingMessage.remove();
    }
}

// Scroll to bottom of chat
function scrollToBottom() {
    if (elements.chatMessages) {
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }
}

// Update active conversation highlight in sidebar
function updateActiveConversationHighlight(conversationId) {
    if (!elements.conversationList) return;

    // Remove active class from all items
    const items = elements.conversationList.querySelectorAll('.conversation-item');
    items.forEach(item => item.classList.remove('active'));

    // Add active class to selected item
    if (conversationId) {
        const activeItem = elements.conversationList.querySelector(`[data-id="${conversationId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }
}

// Clear chat display
function clearChatDisplay() {
    if (!elements.chatMessages) return;

    // Remove all messages except empty state
    const messages = elements.chatMessages.querySelectorAll('.message');
    messages.forEach(msg => msg.remove());
}

// Show empty state
function showEmptyState() {
    if (elements.emptyState) {
        elements.emptyState.style.display = 'flex';
    }
    clearChatDisplay();
}

// Hide empty state
function hideEmptyState() {
    if (elements.emptyState) {
        elements.emptyState.style.display = 'none';
    }
}

// Enable/disable input controls
function setInputEnabled(enabled) {
    if (elements.messageInput) {
        elements.messageInput.disabled = !enabled;
    }
    if (elements.sendButton) {
        elements.sendButton.disabled = !enabled;
    }
}

// Focus on message input
function focusInput() {
    if (elements.messageInput) {
        elements.messageInput.focus();
    }
}

// Clear message input
function clearInput() {
    if (elements.messageInput) {
        elements.messageInput.value = '';
    }
}

// Format timestamp to relative time
function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

    const diffWeeks = Math.floor(diffDays / 7);
    if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks > 1 ? 's' : ''} ago`;

    const diffMonths = Math.floor(diffDays / 30);
    return `${diffMonths} month${diffMonths > 1 ? 's' : ''} ago`;
}

// Show error message in UI
function showErrorMessage(errorText) {
    const errorMessage = {
        role: 'assistant',
        content: `Error: ${errorText}`,
        timestamp: new Date().toISOString()
    };
    addMessageToUI(errorMessage);
}
