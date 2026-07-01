export type ContactProfilePicture = {
  id?: number | string;
  image_url?: string | null;
  secure_url?: string | null;
  url?: string | null;
  picture_url?: string | null;
  profile_picture_url?: string | null;
  cloudinary_url?: string | null;
  file_url?: string | null;
  image?: string | null;
};

export type ContactPublicUser = {
  id?: number | string;
  user_id?: number | string;
  saved_name?: string | null;
  full_name?: string | null;
  username?: string | null;
  email?: string | null;
  contact_number?: number | string | null;
  profile_picture?: ContactProfilePicture | null;
  picture?: ContactProfilePicture | null;
};

export type ContactDeliveryPolicy = {
  owner_user_id?: number | string | null;
  target_user_id?: number | string | null;
  is_blocked?: boolean | null;
  blocked_at?: string | null;
  is_ghosted?: boolean | null;
  ghost_until?: string | null;
  ghost_permanent?: boolean | null;
  ghost_duration_option?: string | null;
  policy_version?: number | string | null;
  updated_at?: string | null;
};

export type ContactSearchResult = ContactPublicUser & {
  contact_id?: number | string | null;
  saved_name?: string | null;
  is_self?: boolean | null;
  already_saved?: boolean | null;
  message?: string | null;
  user?: ContactPublicUser | null;
  contact?: ContactPublicUser | null;
  contact_user?: ContactPublicUser | null;
  target_user?: ContactPublicUser | null;
};

export type ContactSummary = {
  id?: number | string;
  contact_id?: number | string;
  saved_name?: string | null;
  full_name?: string | null;
  username?: string | null;
  contact_number?: number | string | null;
  profile_picture?: ContactProfilePicture | null;
  picture?: ContactProfilePicture | null;
  user?: ContactPublicUser | null;
  contact?: ContactPublicUser | null;
  contact_user?: ContactPublicUser | null;
  target_user?: ContactPublicUser | null;
  policy?: ContactDeliveryPolicy | null;
  delivery_policy?: ContactDeliveryPolicy | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ContactDetail = ContactSummary & {
  delivery_policy?: ContactDeliveryPolicy | null;
  policy?: ContactDeliveryPolicy | null;
};

export type ContactListResponse =
  | ContactSummary[]
  | {
      contacts?: ContactSummary[];
      results?: ContactSummary[];
      items?: ContactSummary[];
    };