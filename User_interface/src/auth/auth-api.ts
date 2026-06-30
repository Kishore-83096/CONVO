import identityClient from "@/api/identity-client";
import { request } from "@/api/http-client";

import type {
  ApiEnvelope,
} from "@/api/api-types";

import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  IdentityUser,
} from "./auth-types";

export const authApi = {
  /**
   * Register a new account.
   */
  register(payload: RegisterRequest) {
    return request<ApiEnvelope<IdentityUser>>(
      identityClient,
      {
        method: "POST",
        url: "/auth/register",
        data: payload,
      },
    );
  },

  /**
   * Login using username/email/contact number.
   */
  login(payload: LoginRequest) {
    return request<ApiEnvelope<LoginResponse>>(
      identityClient,
      {
        method: "POST",
        url: "/auth/login",
        data: payload,
      },
    );
  },

  /**
   * Logout current session.
   */
  logout() {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "POST",
        url: "/auth/logout",
      },
    );
  },
};