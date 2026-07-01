export type MessengerWhoamiResponse = {
  authenticated: boolean;
  user_id: string;
  token_type: string;
  expires_at: number;
};