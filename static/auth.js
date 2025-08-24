/**
 * Universal Authentication Helper for RAG Application
 * 
 * Features:
 * - Automatic token refresh
 * - Secure token storage
 * - Request interceptor for API calls
 * - Logout functionality
 * 
 * Usage:
 * Include this script in all admin pages and use makeAuthenticatedRequest() for API calls
 */

class AuthManager {
    constructor() {
        this.isRefreshing = false;
        this.refreshPromise = null;
    }

    // Get current access token
    getAccessToken() {
        return localStorage.getItem('access_token');
    }

    // Get refresh token
    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    }

    // Store tokens
    setTokens(accessToken, refreshToken) {
        localStorage.setItem('access_token', accessToken);
        if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
        }
    }

    // Clear all tokens
    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.getAccessToken() || !!this.getRefreshToken();
    }

    // Refresh access token
    async refreshToken() {
        if (this.isRefreshing) {
            return this.refreshPromise;
        }

        this.isRefreshing = true;
        this.refreshPromise = this._performRefresh();

        try {
            const result = await this.refreshPromise;
            return result;
        } finally {
            this.isRefreshing = false;
            this.refreshPromise = null;
        }
    }

    async _performRefresh() {
        const refreshToken = this.getRefreshToken();

        if (!refreshToken) {
            this.clearTokens();
            return false;
        }

        try {
            const response = await fetch('/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshToken }),
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token);
                return true;
            } else {
                this.clearTokens();
                return false;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.clearTokens();
            return false;
        }
    }

    // Make authenticated API request with automatic token refresh
    async makeAuthenticatedRequest(url, options = {}) {
        let accessToken = this.getAccessToken();

        // If no access token, try to refresh
        if (!accessToken) {
            const refreshed = await this.refreshToken();
            if (!refreshed) {
                throw new Error('Authentication required');
            }
            accessToken = this.getAccessToken();
        }

        // Set up headers
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
            'Authorization': `Bearer ${accessToken}`
        };

        // Make the request
        let response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include'
        });

        // If unauthorized, try to refresh token and retry once
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                // Retry the request with new token
                headers['Authorization'] = `Bearer ${this.getAccessToken()}`;
                response = await fetch(url, {
                    ...options,
                    headers,
                    credentials: 'include'
                });
            } else {
                // Refresh failed, redirect to login
                this.redirectToLogin();
                throw new Error('Authentication failed');
            }
        }

        return response;
    }

    // Logout user
    async logout() {
        try {
            // Call logout endpoint to invalidate refresh token
            await this.makeAuthenticatedRequest('/auth/logout', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: this.getRefreshToken() })
            });
        } catch (error) {
            console.error('Logout request failed:', error);
        }

        this.clearTokens();
        this.redirectToLogin();
    }

    // Logout from all devices
    async logoutAll() {
        try {
            await this.makeAuthenticatedRequest('/auth/logout-all', {
                method: 'POST'
            });
        } catch (error) {
            console.error('Logout all request failed:', error);
        }

        this.clearTokens();
        this.redirectToLogin();
    }

    // Redirect to login page
    redirectToLogin() {
        // Don't redirect if already on login page
        if (!window.location.pathname.includes('login')) {
            window.location.href = '/login.html';
        }
    }

    // Check authentication and redirect if needed
    requireAuth() {
        if (!this.isAuthenticated()) {
            this.redirectToLogin();
            return false;
        }
        return true;
    }

    // Initialize auth manager and check token validity
    async init() {
        if (this.isAuthenticated()) {
            // Try to refresh token to check validity
            const isValid = await this.refreshToken();
            if (!isValid && !window.location.pathname.includes('login')) {
                this.redirectToLogin();
            }
        }
    }
}

// Create global auth manager instance
const authManager = new AuthManager();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    authManager.init();
});

// Expose globally for easy access
window.authManager = authManager;

// Helper function for backward compatibility
window.makeAuthenticatedRequest = (url, options) => authManager.makeAuthenticatedRequest(url, options);
window.requireAuth = () => authManager.requireAuth();
window.logout = () => authManager.logout();
