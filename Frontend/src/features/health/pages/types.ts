export type IdentityHealthAllResponse = {
  service?: unknown;
  database?: unknown;
  cloudinary?: unknown;
  status?: string;
  message?: string;
  environment?: string;
  [key: string]: unknown;
};