// storage.js - localStorage management for chat conversations

const STORAGE_KEYS = {
    CONVERSATIONS: 'chatAI_conversations',
    ACTIVE_CONVERSATION_ID: 'chatAI_activeConversationId'
};

// Generate UUID for conversations
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Get all conversations from localStorage
function getAllConversations() {
    try {
        const stored = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
        if (!stored) {
            return [];
        }
        return JSON.parse(stored);
    } catch (error) {
        console.error('Error loading conversations:', error);
        return [];
    }
}

// Get a specific conversation by ID
function getConversation(conversationId) {
    const conversations = getAllConversations();
    return conversations.find(c => c.id === conversationId);
}

// Save/update a conversation
function saveConversation(conversation) {
    try {
        const conversations = getAllConversations();
        const index = conversations.findIndex(c => c.id === conversation.id);

        conversation.updated_at = new Date().toISOString();

        if (index !== -1) {
            conversations[index] = conversation;
        } else {
            conversations.push(conversation);
        }

        localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
        return true;
    } catch (error) {
        console.error('Error saving conversation:', error);
        if (error.name === 'QuotaExceededError') {
            alert('Storage quota exceeded. Please delete some old conversations.');
        }
        return false;
    }
}

// Delete a conversation
function deleteConversation(conversationId) {
    try {
        const conversations = getAllConversations();
        const filtered = conversations.filter(c => c.id !== conversationId);
        localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(filtered));

        // If the deleted conversation was active, clear active ID
        if (getActiveConversationId() === conversationId) {
            localStorage.removeItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID);
        }

        return true;
    } catch (error) {
        console.error('Error deleting conversation:', error);
        return false;
    }
}

// Get current active conversation ID
function getActiveConversationId() {
    return localStorage.getItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID);
}

// Set active conversation ID
function setActiveConversationId(conversationId) {
    if (conversationId) {
        localStorage.setItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID, conversationId);
    } else {
        localStorage.removeItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID);
    }
}

// Create a new conversation
function createNewConversation(firstMessage = null) {
    const conversation = {
        id: generateUUID(),
        title: firstMessage ? generateConversationTitle(firstMessage) : 'New Conversation',
        messages: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
    };

    if (firstMessage) {
        conversation.messages.push({
            role: 'user',
            content: firstMessage,
            timestamp: new Date().toISOString()
        });
    }

    saveConversation(conversation);
    setActiveConversationId(conversation.id);

    return conversation;
}

// Generate conversation title from first message
function generateConversationTitle(message) {
    const maxLength = 50;
    let title = message.trim();

    if (title.length > maxLength) {
        title = title.substring(0, maxLength) + '...';
    }

    return title || 'New Conversation';
}

// Add a message to a conversation
function addMessageToConversation(conversationId, message) {
    const conversation = getConversation(conversationId);
    if (!conversation) {
        console.error('Conversation not found:', conversationId);
        return false;
    }

    conversation.messages.push({
        ...message,
        timestamp: message.timestamp || new Date().toISOString()
    });

    return saveConversation(conversation);
}

// Update conversation title
function updateConversationTitle(conversationId, newTitle) {
    const conversation = getConversation(conversationId);
    if (!conversation) {
        return false;
    }

    conversation.title = newTitle;
    return saveConversation(conversation);
}

// Clear all conversations (for debugging/reset)
function clearAllConversations() {
    try {
        localStorage.removeItem(STORAGE_KEYS.CONVERSATIONS);
        localStorage.removeItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID);
        return true;
    } catch (error) {
        console.error('Error clearing conversations:', error);
        return false;
    }
}
