import { z } from "zod";

export const loginSchema = z.object({
  method: z.enum([
    "username",
    "email",
    "contact_number",
  ]),

  identifier: z
    .string()
    .trim()
    .min(1, "Please enter your username, email, or contact number."),

  password: z
  .string()
  .min(
    8,
    "Password must be at least 8 characters.",
  )
  .max(
    128,
    "Password cannot exceed 128 characters.",
  )
});

export type LoginFormValues = z.infer<typeof loginSchema>;