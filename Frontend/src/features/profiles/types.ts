export type ProfileBasic = {
  id?: number | string;
  user_id?: number | string;
  bio?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  occupation?: string | null;
  website?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProfileAddress = {
  id?: number | string;
  user_id?: number | string;
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProfilePicture = {
  id?: number | string;
  user_id?: number | string;
  image_url?: string | null;
  secure_url?: string | null;
  public_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProfileEvent = {
  id?: number | string;
  event_id?: number | string;
  user_id?: number | string;
  event_name?: string | null;
  event_date?: string | null;
  description?: string | null;
  recurring?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MyProfile = {
  identity?: {
    full_name?: string | null;
    username?: string | null;
    email?: string | null;
    contact_number?: number | string | null;
  } | null;
  basic?: ProfileBasic | null;
  basic_data?: ProfileBasic | null;
  address?: ProfileAddress | null;
  picture?: ProfilePicture | null;
  profile_picture?: ProfilePicture | null;
  events?: ProfileEvent[];
};
