# Luna AI Client-Side Authentication Integration Guide

## Overview

This document provides a comprehensive guide for implementing client-side authentication to integrate with the Luna AI Server's JWT-based authentication system. The server provides secure user account management with automatic token refresh capabilities.

## Server Authentication Endpoints

### Base URL Structure

```
http://localhost:8765/auth/
```

### Available Endpoints

| Endpoint              | Method | Purpose                      | Authentication Required |
| --------------------- | ------ | ---------------------------- | ----------------------- |
| `/auth/register`      | POST   | Create new user account      | No                      |
| `/auth/login`         | POST   | Authenticate existing user   | No                      |
| `/auth/refresh`       | POST   | Refresh JWT token            | No (uses current token) |
| `/auth/me`            | GET    | Get current user info        | Yes (Bearer token)      |
| `/auth/check-refresh` | GET    | Check if token needs refresh | Yes (Bearer token)      |

## Implementation Steps

### Phase 1: Basic Authentication Setup

#### Step 1.1: Create Authentication Service

Create a centralized authentication service that handles all auth operations:

```typescript
// services/AuthService.ts
interface User {
    id: number;
    username: string;
    tier: string;
    email?: string;
    is_active: boolean;
    created_at: string;
}

interface AuthResponse {
    access_token: string;
    token_type: string;
    user_id: number;
    username: string;
    tier: string;
}

interface LoginCredentials {
    username: string;
    password: string;
}

interface RegisterData {
    username: string;
    password: string;
    email?: string;
    tier?: "free" | "premium" | "enterprise";
}

class AuthService {
    private baseUrl = "http://localhost:8765/auth";
    private token: string | null = null;
    private refreshTimer: NodeJS.Timeout | null = null;

    // Implement methods in steps below...
}
```

#### Step 1.2: Implement Core Auth Methods

```typescript
class AuthService {
    // ... previous code ...

    async register(userData: RegisterData): Promise<AuthResponse> {
        const response = await fetch(`${this.baseUrl}/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                username: userData.username,
                password: userData.password,
                email: userData.email,
                tier: userData.tier || "free",
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Registration failed");
        }

        const authData: AuthResponse = await response.json();
        this.setToken(authData.access_token);
        return authData;
    }

    async login(credentials: LoginCredentials): Promise<AuthResponse> {
        const response = await fetch(`${this.baseUrl}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(credentials),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Login failed");
        }

        const authData: AuthResponse = await response.json();
        this.setToken(authData.access_token);
        return authData;
    }

    async getCurrentUser(): Promise<User> {
        if (!this.token) {
            throw new Error("No authentication token available");
        }

        const response = await fetch(`${this.baseUrl}/me`, {
            headers: {
                Authorization: `Bearer ${this.token}`,
            },
        });

        if (!response.ok) {
            throw new Error("Failed to get user info");
        }

        return await response.json();
    }

    logout(): void {
        this.token = null;
        this.clearRefreshTimer();
        // Clear from storage (implement in Step 1.3)
        this.clearTokenFromStorage();
    }
}
```

#### Step 1.3: Implement Token Storage

```typescript
class AuthService {
    // ... previous code ...

    private setToken(token: string): void {
        this.token = token;
        this.saveTokenToStorage(token);
        this.startTokenRefreshTimer();
    }

    private saveTokenToStorage(token: string): void {
        // Use Electron's secure storage (keytar recommended)
        // For development, localStorage is acceptable
        if (typeof window !== "undefined") {
            localStorage.setItem("luna_auth_token", token);
        }
        // TODO: Implement keytar for production
    }

    private loadTokenFromStorage(): string | null {
        if (typeof window !== "undefined") {
            return localStorage.getItem("luna_auth_token");
        }
        return null;
        // TODO: Load from keytar for production
    }

    private clearTokenFromStorage(): void {
        if (typeof window !== "undefined") {
            localStorage.removeItem("luna_auth_token");
        }
        // TODO: Clear from keytar for production
    }

    initialize(): void {
        const storedToken = this.loadTokenFromStorage();
        if (storedToken) {
            this.token = storedToken;
            this.startTokenRefreshTimer();
        }
    }

    getToken(): string | null {
        return this.token;
    }

    isAuthenticated(): boolean {
        return this.token !== null;
    }
}
```

### Phase 2: Silent Token Refresh

#### Step 2.1: Implement Token Refresh Logic

```typescript
class AuthService {
    // ... previous code ...

    async refreshToken(): Promise<boolean> {
        if (!this.token) {
            return false;
        }

        try {
            const response = await fetch(`${this.baseUrl}/refresh`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    token: this.token,
                }),
            });

            if (!response.ok) {
                // Token is invalid/expired, user needs to re-login
                this.logout();
                return false;
            }

            const authData: AuthResponse = await response.json();
            this.setToken(authData.access_token);
            console.log("Token refreshed successfully");
            return true;
        } catch (error) {
            console.error("Token refresh failed:", error);
            this.logout();
            return false;
        }
    }

    async checkTokenRefresh(): Promise<boolean> {
        if (!this.token) {
            return false;
        }

        try {
            const response = await fetch(`${this.baseUrl}/check-refresh`, {
                headers: {
                    Authorization: `Bearer ${this.token}`,
                },
            });

            if (!response.ok) {
                return false;
            }

            const result = await response.json();
            return result.needs_refresh || false;
        } catch (error) {
            console.error("Error checking token refresh:", error);
            return true; // Assume refresh needed on error
        }
    }
}
```

#### Step 2.2: Implement Automatic Refresh Timer

```typescript
class AuthService {
    // ... previous code ...

    private startTokenRefreshTimer(): void {
        this.clearRefreshTimer();

        // Check every 30 minutes
        this.refreshTimer = setInterval(async () => {
            if (await this.checkTokenRefresh()) {
                console.log("Token expiring soon, refreshing...");
                await this.refreshToken();
            }
        }, 30 * 60 * 1000); // 30 minutes
    }

    private clearRefreshTimer(): void {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    // Call this when app starts
    async initializeAndRefresh(): Promise<void> {
        this.initialize();

        if (this.isAuthenticated()) {
            // Check immediately on startup
            if (await this.checkTokenRefresh()) {
                await this.refreshToken();
            }
        }
    }
}
```

### Phase 3: WebSocket Authentication Integration

#### Step 3.1: Modify WebSocket Connection

Update your existing WebSocket connection to include JWT token:

```typescript
// In your StreamingService or equivalent
class StreamingService {
    private authService: AuthService;

    constructor(authService: AuthService) {
        this.authService = authService;
    }

    async connectToServer(): Promise<boolean> {
        const token = this.authService.getToken();

        if (!token) {
            throw new Error("No authentication token available");
        }

        // Include token as query parameter for WebSocket authentication
        const wsUrl = `ws://localhost:8765/ws?token=${encodeURIComponent(
            token
        )}`;

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log("Authenticated WebSocket connection established");
                this.isConnected = true;
            };

            this.websocket.onerror = (error) => {
                console.error("WebSocket authentication failed:", error);
                // May indicate token is invalid - trigger refresh
                this.handleAuthenticationError();
            };

            // ... rest of WebSocket setup

            return true;
        } catch (error) {
            console.error("Failed to connect with authentication:", error);
            return false;
        }
    }

    private async handleAuthenticationError(): Promise<void> {
        console.log(
            "WebSocket authentication failed, attempting token refresh..."
        );

        if (await this.authService.refreshToken()) {
            console.log("Token refreshed, reconnecting...");
            await this.connectToServer();
        } else {
            console.log("Token refresh failed, user needs to re-login");
            // Trigger re-authentication UI
            this.onAuthenticationRequired?.();
        }
    }
}
```

#### Step 3.2: Update Session Start Messages

Modify your voice and text session start logic:

```typescript
// Voice session start
async startVoiceSession(initialMessage?: string, memories?: any[]): Promise<void> {
  if (!this.authService.isAuthenticated()) {
    throw new Error('User must be authenticated to start voice session');
  }

  const message = {
    type: "voice_session_start",
    initial_message: initialMessage,
    memories: memories || [],
    // Token is already included in WebSocket connection
  };

  this.websocket.send(JSON.stringify(message));
}

// Text session start
async startTextSession(action: string, selectedText: string, additionalPrompt?: string): Promise<void> {
  if (!this.authService.isAuthenticated()) {
    throw new Error('User must be authenticated to start text session');
  }

  const message = {
    type: "text_session_start",
    action: action,
    selected_text: selectedText,
    additional_prompt: additionalPrompt,
    memories: [], // Include memories if needed
  };

  this.websocket.send(JSON.stringify(message));
}
```

### Phase 4: User Interface Integration

#### Step 4.1: Create Authentication Components

```typescript
// components/AuthenticationModal.tsx
interface AuthModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAuthenticated: (user: User) => void;
}

const AuthenticationModal: React.FC<AuthModalProps> = ({
    isOpen,
    onClose,
    onAuthenticated,
}) => {
    const [mode, setMode] = useState<"login" | "register">("login");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleLogin = async (credentials: LoginCredentials) => {
        setLoading(true);
        setError(null);

        try {
            const authData = await authService.login(credentials);
            const user = await authService.getCurrentUser();
            onAuthenticated(user);
            onClose();
        } catch (error) {
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (userData: RegisterData) => {
        setLoading(true);
        setError(null);

        try {
            const authData = await authService.register(userData);
            const user = await authService.getCurrentUser();
            onAuthenticated(user);
            onClose();
        } catch (error) {
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    // ... UI implementation
};
```

#### Step 4.2: App-Level Authentication State

```typescript
// App.tsx or main component
const App: React.FC = () => {
    const [user, setUser] = useState<User | null>(null);
    const [authModalOpen, setAuthModalOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        initializeAuth();
    }, []);

    const initializeAuth = async () => {
        setLoading(true);

        try {
            await authService.initializeAndRefresh();

            if (authService.isAuthenticated()) {
                const currentUser = await authService.getCurrentUser();
                setUser(currentUser);
            }
        } catch (error) {
            console.error("Auth initialization failed:", error);
            // User will need to login
        } finally {
            setLoading(false);
        }
    };

    const handleLogout = () => {
        authService.logout();
        setUser(null);
    };

    const handleAuthRequired = () => {
        setAuthModalOpen(true);
    };

    if (loading) {
        return <LoadingScreen />;
    }

    if (!user) {
        return (
            <AuthenticationModal
                isOpen={true}
                onClose={() => {}} // Don't allow closing without auth
                onAuthenticated={setUser}
            />
        );
    }

    return (
        <div>
            {/* Your authenticated app UI */}
            <UserInfo user={user} onLogout={handleLogout} />
            <StreamingInterface authService={authService} />

            {/* Auth modal for re-authentication */}
            <AuthenticationModal
                isOpen={authModalOpen}
                onClose={() => setAuthModalOpen(false)}
                onAuthenticated={setUser}
            />
        </div>
    );
};
```

## Data Flow Architecture

### Authentication Flow

```
1. App Start → Initialize AuthService → Load stored token
2. If token exists → Validate with server → Start refresh timer
3. If no token/invalid → Show login UI
4. User login/register → Store token → Initialize WebSocket with token
5. WebSocket connection → Server validates token → Connection established
6. Every 30 minutes → Check if refresh needed → Auto-refresh if needed
```

### Session Flow

```
1. User triggers session (voice/text) → Check authentication
2. If authenticated → Send session start with token context
3. Server receives message → Token already validated from WebSocket
4. Server creates AgentRunner with user context → Session proceeds
5. All session messages flow normally with user context available
```

### Error Handling Flow

```
1. WebSocket auth error → Attempt token refresh
2. If refresh succeeds → Reconnect WebSocket
3. If refresh fails → Show re-authentication UI
4. API calls with 401 → Attempt refresh → Retry original call
5. If refresh fails → Force re-authentication
```

## Implementation Priority

1. **Phase 1** (Essential): Basic auth service with login/register
2. **Phase 2** (Critical): Token refresh and storage
3. **Phase 3** (Required): WebSocket authentication integration
4. **Phase 4** (Polish): UI components and error handling

## Security Considerations

-   Store tokens securely using keytar in production
-   Never log tokens in console/files
-   Clear tokens on app shutdown
-   Validate token before all authenticated operations
-   Handle network errors gracefully
-   Implement proper logout flow

## Testing Checklist

-   [ ] Register new user account
-   [ ] Login with existing account
-   [ ] Token automatically refreshes
-   [ ] WebSocket connects with valid token
-   [ ] WebSocket rejects invalid token
-   [ ] Voice session starts with authentication
-   [ ] Text session starts with authentication
-   [ ] Logout clears all stored data
-   [ ] App recovers from auth errors gracefully
-   [ ] Token refresh works on app restart

This implementation will provide seamless authentication with the Luna AI Server while maintaining security and user experience.
