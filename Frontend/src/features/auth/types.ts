export type RegisterRequest = {
  full_name: string;
  username: string;
  password: string;
  confirm_password: string;
};

export type RegisterResponseData = {
  full_name: string;
  username: string;
  email: string;
  contact_number: string;
};

export type RegisterFieldName = keyof RegisterRequest;

export type LoginMethod = "username" | "email" | "contact_number";

export type LoginRequest = {
  method: LoginMethod;
  identifier: string;
  password: string;
};

export type LoginUser = {
  id: string;
  full_name: string;
  username: string;
  email: string;
  contact_number: string;
};

export type LoginResponseData = {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
  user: LoginUser;
};

export type LoginFieldName = keyof LoginRequest;

export type ResetPasswordRequest = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
  new_password: string;
  confirm_new_password: string;
};

export type ResetPasswordFormValues = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
  new_password: string;
  confirm_new_password: string;
};

export type ResetPasswordFieldName = keyof ResetPasswordFormValues;

export type DeleteAccountRequest = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
};

export type DeleteAccountFormValues = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
  confirmation_text: string;
};

export type DeleteAccountFieldName = keyof DeleteAccountFormValues;