// app.js - Main application logic and API integration

// API Configuration
const API_BASE_URL = 'http://localhost:8000';
const API_ENDPOINTS = {
    CHAT: `${API_BASE_URL}/chat`
};

// Initialize application on page load
function initApp() {
    console.log('Initializing Chat AI application...');

    // Initialize UI elements
    initUIElements();

    // Setup event listeners
    setupEventListeners();

    // Load and render conversations
    renderConversationList();

    // Load active conversation if exists
    const activeId = getActiveConversationId();
    if (activeId) {
        renderMessages(activeId);
        updateActiveConversationHighlight(activeId);
    } else {
        showEmptyState();
    }

    // Focus on input
    focusInput();

    console.log('Application initialized successfully');
}

// Setup event listeners
function setupEventListeners() {
    // Message form submit
    if (elements.messageForm) {
        elements.messageForm.addEventListener('submit', handleSendMessage);
    }

    // New conversation button
    if (elements.newConversationBtn) {
        elements.newConversationBtn.addEventListener('click', handleNewConversation);
    }

    // Conversation list click (event delegation)
    if (elements.conversationList) {
        elements.conversationList.addEventListener('click', (e) => {
            // Handle conversation selection
            const conversationItem = e.target.closest('.conversation-item');
            if (conversationItem && !e.target.classList.contains('delete-btn')) {
                handleConversationSelect(conversationItem.dataset.id);
            }

            // Handle conversation deletion
            if (e.target.classList.contains('delete-btn')) {
                e.stopPropagation();
                handleDeleteConversation(e.target.dataset.id);
            }
        });
    }

    // Listen for storage changes in other tabs
    window.addEventListener('storage', (e) => {
        if (e.key === 'chatAI_conversations') {
            renderConversationList();
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + N for new conversation
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            handleNewConversation();
        }
    });
}

// Handle new conversation creation
function handleNewConversation() {
    console.log('Creating new conversation...');

    // Create new conversation without initial message
    const conversation = createNewConversation();

    // Update UI
    renderConversationList();
    renderMessages(conversation.id);
    updateActiveConversationHighlight(conversation.id);

    // Focus on input
    focusInput();
}

// Handle conversation selection
function handleConversationSelect(conversationId) {
    console.log('Selecting conversation:', conversationId);

    // Set as active
    setActiveConversationId(conversationId);

    // Render messages
    renderMessages(conversationId);

    // Update highlight
    updateActiveConversationHighlight(conversationId);

    // Focus on input
    focusInput();
}

// Handle message send
async function handleSendMessage(event) {
    event.preventDefault();

    const userMessage = elements.messageInput.value.trim();

    if (!userMessage) {
        return;
    }

    console.log('Sending message:', userMessage);

    // Disable input
    setInputEnabled(false);

    try {
        // Get or create conversation
        let conversationId = getActiveConversationId();

        if (!conversationId) {
            // Create new conversation with first message
            const conversation = createNewConversation(userMessage);
            conversationId = conversation.id;

            // Update UI
            renderConversationList();
            updateActiveConversationHighlight(conversationId);
        } else {
            // Add user message to existing conversation
            const userMessageObj = {
                role: 'user',
                content: userMessage,
                timestamp: new Date().toISOString()
            };

            addMessageToConversation(conversationId, userMessageObj);
        }

        // Clear input
        clearInput();

        // Render user message
        renderMessages(conversationId);

        // Show thinking animation
        showThinkingAnimation();

        // Call API
        const response = await sendMessageToAPI(userMessage);

        // Hide thinking animation
        hideThinkingAnimation();

        // Process response
        await processAPIResponse(response, conversationId);

    } catch (error) {
        console.error('Error sending message:', error);
        hideThinkingAnimation();
        showErrorMessage('Failed to send message. Please try again.');
    } finally {
        // Re-enable input
        setInputEnabled(true);
        focusInput();
    }
}

// Call the /chat API endpoint
async function sendMessageToAPI(userMessage) {
    try {
        console.log('Calling API:', API_ENDPOINTS.CHAT);

        const response = await fetch(API_ENDPOINTS.CHAT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_message: userMessage
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('API response:', data);

        return data;

    } catch (error) {
        console.error('API Error:', error);

        // Return error response
        return {
            response: 'Sorry, I encountered an error while processing your request. Please try again.',
            finish_reason: 'error',
            turns_used: 0
        };
    }
}

// Process API response and update UI
async function processAPIResponse(apiResponse, conversationId) {
    const assistantMessage = {
        role: 'assistant',
        content: apiResponse.response,
        timestamp: new Date().toISOString(),
        turns_used: apiResponse.turns_used,
        finish_reason: apiResponse.finish_reason
    };

    // Add assistant message to conversation
    addMessageToConversation(conversationId, assistantMessage);

    // Render updated messages
    renderMessages(conversationId);

    // Update conversation list (to refresh timestamps)
    renderConversationList();
}

// Handle conversation deletion
function handleDeleteConversation(conversationId) {
    if (!confirm('Are you sure you want to delete this conversation?')) {
        return;
    }

    console.log('Deleting conversation:', conversationId);

    // Delete conversation
    const success = deleteConversation(conversationId);

    if (success) {
        // Update UI
        renderConversationList();

        // If deleted conversation was active, show empty state
        if (getActiveConversationId() === conversationId) {
            setActiveConversationId(null);
            showEmptyState();
        }
    } else {
        alert('Failed to delete conversation');
    }
}

// Initialize app when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
