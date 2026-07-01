import { useMutation } from "@tanstack/react-query";

import {
  deleteAccount,
  loginUser,
  logoutUser,
  registerUser,
  resetPassword,
} from "./api";
import type {
  DeleteAccountRequest,
  LoginRequest,
  RegisterRequest,
  ResetPasswordRequest,
} from "./types";

export function useRegisterUser() {
  return useMutation({
    mutationFn: (payload: RegisterRequest) => registerUser(payload),
  });
}

export function useLoginUser() {
  return useMutation({
    mutationFn: (payload: LoginRequest) => loginUser(payload),
  });
}

export function useLogoutUser() {
  return useMutation({
    mutationFn: () => logoutUser(),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (payload: ResetPasswordRequest) => resetPassword(payload),
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: (payload: DeleteAccountRequest) => deleteAccount(payload),
  });
}