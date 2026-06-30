export type LoginMethod =
    | "username"
    | "email"
    | "contact_number";

export interface IdentityUser {
    full_name: string;
    username: string;
    email: string;
    contact_number: number;
}

export interface LoginRequest {
    method: LoginMethod;
    identifier: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    expires_at: string;
    user: IdentityUser;
}

export interface RegisterRequest {
    full_name: string;
    username: string;
    password: string;
    confirm_password: string;
}

export interface RegisterResponse {
  full_name: string;
  username: string;
  email: string;
  contact_number: number;
}

export interface ResetPasswordRequest {
    username: string;
    email: string;
    contact_number: string;
    current_password: string;
    new_password: string;
    confirm_new_password: string;
}

export interface DeleteAccountRequest {
    username: string;
    email: string;
    contact_number: string;
    current_password: string;
}

export interface AuthSession {
    accessToken: string;
    tokenType: string;
    expiresAt: string;
    user: IdentityUser;
}

export interface AuthContextValue {
    session: AuthSession | null;
    isAuthenticated: boolean;
    isLoading: boolean;

    login(
        request: LoginRequest,
    ): Promise<void>;

    logout(): Promise<void>;
}
