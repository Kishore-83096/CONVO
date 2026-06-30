import { setAccessToken } from "@/api/http-client";

import { authApi } from "./auth-api";
import { useAuthStore } from "./auth-store";
import {
  clearSession,
  loadSession,
  saveSession,
} from "./auth-storage";

import type {
  AuthSession,
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
} from "./auth-types";


class AuthService {

  async register(
    request: RegisterRequest,
  ): Promise<RegisterResponse> {
    const { data } =
      await authApi.register(request);

    if (!data) {
      throw new Error(
        "Registration response did not contain user data.",
      );
    }

    return data;
  }



  async login(
    request: LoginRequest,
  ): Promise<AuthSession> {
    const { data } = await authApi.login(request);

    if (!data) {
      throw new Error(
        "Login response did not contain session data.",
      );
    }

    const session: AuthSession = {
      accessToken: data.access_token,
      tokenType: data.token_type,
      expiresAt: data.expires_at,
      user: data.user,
    };

    saveSession(session);

    setAccessToken(session.accessToken);

    useAuthStore
      .getState()
      .setSession(session);

    return session;
  }

  async logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      clearSession();

      setAccessToken(null);

      useAuthStore
        .getState()
        .clearSession();
    }
  }

  restoreSession(): void {
    const session = loadSession();

    if (!session) {
      return;
    }

    setAccessToken(session.accessToken);

    useAuthStore
      .getState()
      .setSession(session);
  }
}

export const authService = new AuthService();