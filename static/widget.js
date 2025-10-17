/**
 * Embeddable Chat Widget for External Websites
 * 
 * This script creates a chat widget that can be embedded on any website.
 * It handles session management, message sending, and token refresh automatically.
 * 
 * Usage:
 * <script src="https://myapp.com/static/widget.js" 
 *         data-bot-id="123" 
 *         data-token="your-widget-token"
 *         data-api-base="https://myapp.com/widget"
 *         data-theme="light"
 *         data-position="bottom-right">
 * </script>
 */

(function () {
    'use strict';

    // ==================== Configuration ====================

    const script = document.currentScript;
    const CONFIG = {
        botId: script.dataset.botId,
        token: script.dataset.token,
        apiBase: script.dataset.apiBase || 'http://localhost:8000/widget',
        theme: script.dataset.theme || 'light',
        position: script.dataset.position || 'bottom-right',
        primaryColor: script.dataset.primaryColor || '#3b82f6',
        bubbleIcon: script.dataset.bubbleIcon || '💬'
    };

    // Validate required config
    if (!CONFIG.botId || !CONFIG.token) {
        console.error('[ChatWidget] Missing required data attributes: data-bot-id and data-token');
        return;
    }

    // ==================== Storage Keys ====================

    const STORAGE_KEYS = {
        SESSION_ID: `chat_widget_session_${CONFIG.botId}`,
        TOKEN: `chat_widget_token_${CONFIG.botId}`,
        MESSAGES: `chat_widget_messages_${CONFIG.botId}`
    };

    // ==================== Chat Widget Class ====================

    class ChatWidget {
        constructor(config) {
            this.config = config;
            this.sessionId = null;
            this.messages = [];
            this.isOpen = false;
            this.isInitialized = false;
            this.botName = 'Assistant';

            // Bind methods
            this.toggle = this.toggle.bind(this);
            this.sendMessage = this.sendMessage.bind(this);
            this.handleKeyPress = this.handleKeyPress.bind(this);
        }

        // ==================== Initialization ====================

        async init() {
            // Load stored session and messages
            this.loadFromStorage();

            // Create UI
            this.createUI();

            // Start or resume session
            if (!this.sessionId) {
                await this.startSession();
            }

            this.isInitialized = true;
        }

        loadFromStorage() {
            try {
                this.sessionId = localStorage.getItem(STORAGE_KEYS.SESSION_ID);
                const storedMessages = localStorage.getItem(STORAGE_KEYS.MESSAGES);
                if (storedMessages) {
                    this.messages = JSON.parse(storedMessages);
                }
            } catch (e) {
                console.warn('[ChatWidget] Failed to load from storage:', e);
            }
        }

        saveToStorage() {
            try {
                if (this.sessionId) {
                    localStorage.setItem(STORAGE_KEYS.SESSION_ID, this.sessionId);
                }
                localStorage.setItem(STORAGE_KEYS.MESSAGES, JSON.stringify(this.messages));
            } catch (e) {
                console.warn('[ChatWidget] Failed to save to storage:', e);
            }
        }

        // ==================== API Methods ====================

        async apiCall(endpoint, method = 'GET', body = null) {
            const headers = {
                'Authorization': `Bearer ${this.config.token}`,
                'Content-Type': 'application/json'
            };

            const options = {
                method,
                headers
            };

            if (body) {
                options.body = JSON.stringify(body);
            }

            try {
                const response = await fetch(`${this.config.apiBase}${endpoint}`, options);

                if (response.status === 401) {
                    // Token expired - try to refresh
                    const refreshed = await this.refreshToken();
                    if (refreshed) {
                        // Retry the original request
                        headers.Authorization = `Bearer ${this.config.token}`;
                        const retryResponse = await fetch(`${this.config.apiBase}${endpoint}`, options);
                        return await retryResponse.json();
                    } else {
                        throw new Error('Token expired and refresh failed');
                    }
                }

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Request failed');
                }

                return await response.json();
            } catch (error) {
                console.error('[ChatWidget] API call failed:', error);
                throw error;
            }
        }

        async startSession() {
            try {
                const data = await this.apiCall('/session/start', 'POST', {
                    visitor_identifier: this.getVisitorId()
                });

                this.sessionId = data.session_id;
                this.botName = data.bot_name || 'Assistant';

                // Add welcome message
                if (data.welcome_message) {
                    this.addMessage(data.welcome_message, false);
                }

                this.saveToStorage();
            } catch (error) {
                console.error('[ChatWidget] Failed to start session:', error);
                this.showError('Failed to connect to chat. Please refresh the page.');
            }
        }

        async refreshToken() {
            try {
                const response = await fetch(`${this.config.apiBase}/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        widget_token: this.config.token
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.config.token = data.widget_token;
                    localStorage.setItem(STORAGE_KEYS.TOKEN, data.widget_token);
                    return true;
                }

                return false;
            } catch (error) {
                console.error('[ChatWidget] Token refresh failed:', error);
                return false;
            }
        }

        getVisitorId() {
            // Generate or retrieve a unique visitor ID
            let visitorId = localStorage.getItem('chat_widget_visitor_id');
            if (!visitorId) {
                visitorId = 'visitor_' + Math.random().toString(36).substr(2, 9) + Date.now();
                localStorage.setItem('chat_widget_visitor_id', visitorId);
            }
            return visitorId;
        }

        // ==================== Message Handling ====================

        async sendMessage() {
            const input = this.elements.input;
            const message = input.value.trim();

            if (!message || !this.sessionId) return;

            // Clear input
            input.value = '';

            // Add user message to UI
            this.addMessage(message, true);

            // Show typing indicator
            this.showTypingIndicator();

            try {
                const data = await this.apiCall('/chat', 'POST', {
                    session_id: this.sessionId,
                    message: message
                });

                // Remove typing indicator
                this.hideTypingIndicator();

                // Add bot response
                this.addMessage(data.answer, false);

            } catch (error) {
                this.hideTypingIndicator();
                this.addMessage('Sorry, I encountered an error. Please try again.', false);
            }
        }

        addMessage(text, isUser) {
            const message = { text, isUser, timestamp: Date.now() };
            this.messages.push(message);
            this.saveToStorage();

            if (this.elements.messagesContainer) {
                this.renderMessage(message);
                this.scrollToBottom();
            }
        }

        renderMessage(message, skipAnimation = false) {
            const messageEl = document.createElement('div');
            messageEl.className = `cw-message ${message.isUser ? 'cw-message-user' : 'cw-message-bot'}`;

            const bubble = document.createElement('div');
            bubble.className = 'cw-message-bubble';

            if (message.isUser || skipAnimation) {
                // User messages or loaded messages appear instantly
                bubble.textContent = message.text;
            } else {
                // Bot messages use typewriter effect
                this.typeWriterEffect(bubble, message.text);
            }

            messageEl.appendChild(bubble);
            this.elements.messagesContainer.appendChild(messageEl);
        }

        showTypingIndicator() {
            const indicator = document.createElement('div');
            indicator.className = 'cw-typing-indicator';
            indicator.id = 'cw-typing';
            indicator.innerHTML = '<span></span><span></span><span></span>';
            this.elements.messagesContainer.appendChild(indicator);
            this.scrollToBottom();
        }

        hideTypingIndicator() {
            const indicator = document.getElementById('cw-typing');
            if (indicator) {
                indicator.remove();
            }
        }

        showError(message) {
            this.addMessage(`⚠️ ${message}`, false);
        }

        scrollToBottom() {
            if (this.elements.messagesContainer) {
                this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
            }
        }

        typeWriterEffect(element, text, speed = 30) {
            /**
             * Creates a typewriter effect for bot messages
             * @param {HTMLElement} element - The message bubble element
             * @param {string} text - The full text to display
             * @param {number} speed - Speed in milliseconds per character
             */
            let index = 0;
            element.textContent = '';

            const typeInterval = setInterval(() => {
                if (index < text.length) {
                    element.textContent += text.charAt(index);
                    index++;
                    this.scrollToBottom();
                } else {
                    clearInterval(typeInterval);
                }
            }, speed);
        }

        clearConversation() {
            /**
             * Clears the current conversation and starts a new one
             */
            if (confirm('Start a new conversation? This will clear all messages.')) {
                // Clear messages
                this.messages = [];

                // Clear session
                this.sessionId = null;

                // Clear storage
                localStorage.removeItem(STORAGE_KEYS.SESSION_ID);
                localStorage.removeItem(STORAGE_KEYS.MESSAGES);

                // Clear UI
                if (this.elements.messagesContainer) {
                    this.elements.messagesContainer.innerHTML = '';
                }

                // Start new session
                this.startSession();
            }
        }

        // ==================== UI Creation ====================

        createUI() {
            // Create container
            const container = document.createElement('div');
            container.id = 'chat-widget-container';
            container.className = `cw-container cw-${this.config.position} cw-theme-${this.config.theme}`;

            // Create chat bubble button
            const bubble = this.createBubble();
            container.appendChild(bubble);

            // Create chat window
            const chatWindow = this.createChatWindow();
            container.appendChild(chatWindow);

            // Add styles
            this.injectStyles();

            // Add to page
            document.body.appendChild(container);

            // Store element references
            this.elements = {
                container,
                bubble,
                chatWindow,
                messagesContainer: chatWindow.querySelector('.cw-messages'),
                input: chatWindow.querySelector('.cw-input'),
                sendBtn: chatWindow.querySelector('.cw-send-btn')
            };

            // Render existing messages
            this.messages.forEach(msg => this.renderMessage(msg, true));
            this.scrollToBottom();

            // Attach event listeners
            this.attachEventListeners();
        }

        createBubble() {
            const bubble = document.createElement('div');
            bubble.className = 'cw-bubble';
            bubble.innerHTML = this.config.bubbleIcon;
            bubble.style.backgroundColor = this.config.primaryColor;
            bubble.addEventListener('click', this.toggle);
            return bubble;
        }

        createChatWindow() {
            const chatWindow = document.createElement('div');
            chatWindow.className = 'cw-chat-window';
            chatWindow.style.display = 'none';

            chatWindow.innerHTML = `
                <div class="cw-header" style="background-color: ${this.config.primaryColor}">
                    <div class="cw-header-title">
                        <strong>${this.botName}</strong>
                        <span class="cw-status">● Online</span>
                    </div>
                    <div class="cw-header-actions">
                        <button class="cw-new-chat-btn" title="Start new conversation">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 5v14M5 12h14"/>
                            </svg>
                        </button>
                        <button class="cw-close-btn">×</button>
                    </div>
                </div>
                <div class="cw-messages"></div>
                <div class="cw-input-container">
                    <input type="text" class="cw-input" placeholder="Type your message..." />
                    <button class="cw-send-btn" style="background-color: ${this.config.primaryColor}">
                        Send
                    </button>
                </div>
                <div class="cw-footer">
                    <small>Powered by Your AIdly</small>
                </div>
            `;

            return chatWindow;
        }

        attachEventListeners() {
            // Close button
            const closeBtn = this.elements.chatWindow.querySelector('.cw-close-btn');
            closeBtn.addEventListener('click', this.toggle);

            // New chat button
            const newChatBtn = this.elements.chatWindow.querySelector('.cw-new-chat-btn');
            newChatBtn.addEventListener('click', () => this.clearConversation());

            // Send button
            this.elements.sendBtn.addEventListener('click', this.sendMessage);

            // Enter key in input
            this.elements.input.addEventListener('keypress', this.handleKeyPress);
        }

        handleKeyPress(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        }

        toggle() {
            this.isOpen = !this.isOpen;

            if (this.isOpen) {
                this.elements.chatWindow.style.display = 'flex';
                this.elements.bubble.style.display = 'none';
                this.elements.input.focus();
                this.scrollToBottom();
            } else {
                this.elements.chatWindow.style.display = 'none';
                this.elements.bubble.style.display = 'flex';
            }
        }

        // ==================== Styles ====================

        injectStyles() {
            if (document.getElementById('chat-widget-styles')) return;

            const styles = document.createElement('style');
            styles.id = 'chat-widget-styles';
            styles.textContent = `
                /* Container */
                #chat-widget-container {
                    position: fixed;
                    z-index: 999999;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                }

                .cw-container.cw-bottom-right {
                    bottom: 20px;
                    right: 20px;
                }

                .cw-container.cw-bottom-left {
                    bottom: 20px;
                    left: 20px;
                }

                .cw-container.cw-top-right {
                    top: 20px;
                    right: 20px;
                }

                .cw-container.cw-top-left {
                    top: 20px;
                    left: 20px;
                }

                /* Bubble */
                .cw-bubble {
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 28px;
                    cursor: pointer;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    transition: transform 0.2s, box-shadow 0.2s;
                }

                .cw-bubble:hover {
                    transform: scale(1.05);
                    box-shadow: 0 6px 16px rgba(0,0,0,0.2);
                }

                /* Chat Window */
                .cw-chat-window {
                    width: 380px;
                    height: 600px;
                    max-height: 80vh;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }

                /* Header */
                .cw-header {
                    padding: 16px;
                    color: white;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .cw-header-title {
                    display: flex;
                    flex-direction: column;
                }

                .cw-header-actions {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }

                .cw-status {
                    font-size: 12px;
                    opacity: 0.9;
                }

                .cw-new-chat-btn {
                    background: rgba(255, 255, 255, 0.2);
                    border: none;
                    color: white;
                    font-size: 16px;
                    cursor: pointer;
                    padding: 6px;
                    width: 32px;
                    height: 32px;
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background 0.2s;
                }

                .cw-new-chat-btn:hover {
                    background: rgba(255, 255, 255, 0.3);
                }

                .cw-close-btn {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 28px;
                    cursor: pointer;
                    padding: 0;
                    width: 32px;
                    height: 32px;
                    line-height: 32px;
                    text-align: center;
                    border-radius: 4px;
                    transition: background 0.2s;
                }

                .cw-close-btn:hover {
                    background: rgba(255,255,255,0.2);
                }

                /* Messages */
                .cw-messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 16px;
                    background: #f9fafb;
                }

                .cw-message {
                    margin-bottom: 12px;
                    display: flex;
                }

                .cw-message-user {
                    justify-content: flex-end;
                }

                .cw-message-bot {
                    justify-content: flex-start;
                }

                .cw-message-bubble {
                    max-width: 70%;
                    padding: 10px 14px;
                    border-radius: 18px;
                    word-wrap: break-word;
                }

                .cw-message-user .cw-message-bubble {
                    background: ${this.config.primaryColor};
                    color: white;
                }

                .cw-message-bot .cw-message-bubble {
                    background: white;
                    color: #1f2937;
                    border: 1px solid #e5e7eb;
                }

                /* Typing Indicator */
                .cw-typing-indicator {
                    display: flex;
                    gap: 4px;
                    padding: 12px;
                    background: white;
                    border-radius: 18px;
                    width: fit-content;
                    border: 1px solid #e5e7eb;
                }

                .cw-typing-indicator span {
                    width: 8px;
                    height: 8px;
                    background: #9ca3af;
                    border-radius: 50%;
                    animation: cw-typing 1.4s infinite;
                }

                .cw-typing-indicator span:nth-child(2) {
                    animation-delay: 0.2s;
                }

                .cw-typing-indicator span:nth-child(3) {
                    animation-delay: 0.4s;
                }

                @keyframes cw-typing {
                    0%, 60%, 100% {
                        transform: translateY(0);
                    }
                    30% {
                        transform: translateY(-10px);
                    }
                }

                /* Input Container */
                .cw-input-container {
                    display: flex;
                    gap: 8px;
                    padding: 12px;
                    background: white;
                    border-top: 1px solid #e5e7eb;
                }

                .cw-input {
                    flex: 1;
                    border: 1px solid #d1d5db;
                    border-radius: 20px;
                    padding: 10px 16px;
                    font-size: 14px;
                    outline: none;
                }

                .cw-input:focus {
                    border-color: ${this.config.primaryColor};
                    box-shadow: 0 0 0 3px ${this.config.primaryColor}22;
                }

                .cw-send-btn {
                    border: none;
                    border-radius: 20px;
                    padding: 10px 20px;
                    color: white;
                    font-weight: 500;
                    cursor: pointer;
                    transition: opacity 0.2s;
                }

                .cw-send-btn:hover {
                    opacity: 0.9;
                }

                .cw-send-btn:active {
                    opacity: 0.8;
                }

                /* Footer */
                .cw-footer {
                    padding: 8px;
                    text-align: center;
                    background: #f9fafb;
                    border-top: 1px solid #e5e7eb;
                }

                .cw-footer small {
                    color: #6b7280;
                    font-size: 11px;
                }

                /* Dark Theme */
                .cw-theme-dark .cw-chat-window {
                    background: #1f2937;
                }

                .cw-theme-dark .cw-messages {
                    background: #111827;
                }

                .cw-theme-dark .cw-message-bot .cw-message-bubble {
                    background: #374151;
                    color: #f9fafb;
                    border-color: #4b5563;
                }

                .cw-theme-dark .cw-input-container,
                .cw-theme-dark .cw-footer {
                    background: #1f2937;
                    border-color: #374151;
                }

                .cw-theme-dark .cw-input {
                    background: #374151;
                    border-color: #4b5563;
                    color: #f9fafb;
                }

                /* Mobile Responsive */
                @media (max-width: 480px) {
                    .cw-chat-window {
                        width: 100vw;
                        height: 100vh;
                        max-height: 100vh;
                        border-radius: 0;
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                    }

                    .cw-container {
                        bottom: 10px !important;
                        right: 10px !important;
                    }
                }
            `;

            document.head.appendChild(styles);
        }
    }

    // ==================== Initialize Widget ====================

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }

    function initWidget() {
        const widget = new ChatWidget(CONFIG);
        widget.init();

        // Expose widget instance globally for debugging
        window.ChatWidget = widget;
    }

})();
