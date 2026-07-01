import { z } from "zod";

function isValidOptionalUrl(value: string) {
  const trimmedValue = value.trim();

  if (!trimmedValue) {
    return true;
  }

  try {
    const url = new URL(trimmedValue);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export const basicProfileCreateSchema = z
  .object({
    bio: z.string().max(500, "Bio must be 500 characters or less."),
    date_of_birth: z.string(),
    gender: z.string().max(50, "Gender must be 50 characters or less."),
    occupation: z
      .string()
      .max(100, "Occupation must be 100 characters or less."),
    website: z
      .string()
      .refine(isValidOptionalUrl, "Website must be a valid URL."),
  })
  .refine(
    (value) =>
      Boolean(
        value.bio.trim() ||
          value.date_of_birth ||
          value.gender.trim() ||
          value.occupation.trim() ||
          value.website.trim(),
      ),
    {
      message: "Add at least one basic profile field.",
      path: ["bio"],
    },
  );

export const basicProfileUpdateSchema = z
  .object({
    bio: z.string().max(500, "Bio must be 500 characters or less."),
    date_of_birth: z.string(),
    gender: z.string().max(50, "Gender must be 50 characters or less."),
    occupation: z
      .string()
      .max(100, "Occupation must be 100 characters or less."),
    website: z
      .string()
      .refine(isValidOptionalUrl, "Website must be a valid URL."),
  })
  .refine(
    (value) =>
      Boolean(
        value.bio.trim() ||
          value.date_of_birth ||
          value.gender.trim() ||
          value.occupation.trim() ||
          value.website.trim(),
      ),
    {
      message: "Add at least one basic profile field before updating.",
      path: ["bio"],
    },
  );

export const addressProfileCreateSchema = z.object({
  address_line_1: z
    .string()
    .trim()
    .min(1, "Address line 1 is required."),
  address_line_2: z.string(),
  city: z.string().trim().min(1, "City is required."),
  state: z.string(),
  postal_code: z.string(),
  country: z.string().trim().min(1, "Country is required."),
});

export const addressProfileUpdateSchema = z
  .object({
    address_line_1: z.string(),
    address_line_2: z.string(),
    city: z.string(),
    state: z.string(),
    postal_code: z.string(),
    country: z.string(),
  })
  .refine(
    (value) =>
      Boolean(
        value.address_line_1.trim() ||
          value.address_line_2.trim() ||
          value.city.trim() ||
          value.state.trim() ||
          value.postal_code.trim() ||
          value.country.trim(),
      ),
    {
      message: "Add at least one address field before updating.",
      path: ["address_line_1"],
    },
  );

export const profileEventCreateSchema = z.object({
  event_name: z
    .string()
    .trim()
    .min(1, "Event name is required.")
    .max(80, "Event name must be 80 characters or less."),
  event_date: z.string().trim().min(1, "Event date is required."),
  description: z
    .string()
    .max(300, "Description must be 300 characters or less."),
  recurring: z.boolean(),
});

export const profileEventUpdateSchema = z
  .object({
    event_id: z.string().trim().min(1, "Event ID is required."),
    event_name: z
      .string()
      .max(80, "Event name must be 80 characters or less."),
    event_date: z.string(),
    description: z
      .string()
      .max(300, "Description must be 300 characters or less."),
    update_recurring: z.boolean(),
    recurring: z.boolean(),
  })
  .refine(
    (value) =>
      Boolean(
        value.event_name.trim() ||
          value.event_date.trim() ||
          value.description.trim() ||
          value.update_recurring,
      ),
    {
      message: "Add at least one event field before updating.",
      path: ["event_name"],
    },
  );

export type BasicProfileCreateFormValues = z.infer<
  typeof basicProfileCreateSchema
>;

export type BasicProfileUpdateFormValues = z.infer<
  typeof basicProfileUpdateSchema
>;

export type AddressProfileCreateFormValues = z.infer<
  typeof addressProfileCreateSchema
>;

export type AddressProfileUpdateFormValues = z.infer<
  typeof addressProfileUpdateSchema
>;

export type ProfileEventCreateFormValues = z.infer<
  typeof profileEventCreateSchema
>;

export type ProfileEventUpdateFormValues = z.infer<
  typeof profileEventUpdateSchema
>;