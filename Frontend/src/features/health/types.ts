export type IdentityHealthAllResponse = {
  service?: unknown;
  database?: unknown;
  cloudinary?: unknown;
  status?: string;
  message?: string;
  environment?: string;
  [key: string]: unknown;
};

export type MessengerHealthResponse = {
  message?: string;
  service?: string;
  environment?: string;
  status?: string;
  [key: string]: unknown;
};