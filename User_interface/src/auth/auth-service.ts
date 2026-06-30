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
  DeleteAccountRequest,
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
  ResetPasswordRequest,
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
      await this.clearAuthenticatedState();
    }
  }

  async resetPassword(
    request: ResetPasswordRequest,
  ): Promise<void> {
    await authApi.resetPassword(request);
    await this.clearAuthenticatedState();
  }

  async deleteAccount(
    request: DeleteAccountRequest,
  ): Promise<void> {
    await authApi.deleteAccount(request);
    await this.clearAuthenticatedState({
      clearAllLocalAppData: true,
    });
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

  private async clearAuthenticatedState(
    options: {
      clearAllLocalAppData?: boolean;
    } = {},
  ): Promise<void> {
    clearSession();

    setAccessToken(null);

    useAuthStore
      .getState()
      .clearSession();

    if (options.clearAllLocalAppData) {
      clearMynaLocalStorage();
      await clearMynaIndexedDatabases().catch(() => undefined);
    }
  }
}

export const authService = new AuthService();

function clearMynaLocalStorage(): void {
  const keys = Array.from(
    { length: localStorage.length },
    (_, index) => localStorage.key(index),
  ).filter((key): key is string => Boolean(key));

  keys
    .filter((key) => key.startsWith("myna."))
    .forEach((key) => localStorage.removeItem(key));
}

async function clearMynaIndexedDatabases(): Promise<void> {
  if (typeof indexedDB === "undefined") {
    return;
  }

  const factory = indexedDB as IDBFactory & {
    databases?: () => Promise<Array<{ name?: string }>>;
  };

  if (!factory.databases) {
    return;
  }

  const databases = await factory.databases();

  await Promise.all(
    databases
      .map((database) => database.name)
      .filter((name): name is string =>
        Boolean(name && name.toLowerCase().includes("myna")),
      )
      .map(deleteIndexedDatabase),
  );
}

function deleteIndexedDatabase(name: string): Promise<void> {
  return new Promise((resolve) => {
    const request = indexedDB.deleteDatabase(name);

    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
    request.onblocked = () => resolve();
  });
}
