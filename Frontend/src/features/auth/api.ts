import { identityRequest } from "../../shared/api/identityClient";

import type {
  DeleteAccountRequest,
  LoginRequest,
  LoginResponseData,
  RegisterRequest,
  RegisterResponseData,
  ResetPasswordRequest,
} from "./types";

export function registerUser(payload: RegisterRequest) {
  return identityRequest<RegisterResponseData>({
    method: "POST",
    url: "/auth/register",
    data: payload,
  });
}

export function loginUser(payload: LoginRequest) {
  return identityRequest<LoginResponseData>({
    method: "POST",
    url: "/auth/login",
    data: payload,
  });
}

export function logoutUser() {
  return identityRequest<null>({
    method: "POST",
    url: "/auth/logout",
  });
}

export function resetPassword(payload: ResetPasswordRequest) {
  return identityRequest<null>({
    method: "POST",
    url: "/auth/reset-password",
    data: payload,
  });
}

export function deleteAccount(payload: DeleteAccountRequest) {
  return identityRequest<null>({
    method: "DELETE",
    url: "/auth/delete-account",
    data: payload,
  });
}