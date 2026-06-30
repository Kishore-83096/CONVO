import { z } from "zod";

const usernameRegex = /^[a-z0-9_]+$/;

export const registerSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(2, "Full name must be at least 2 characters.")
      .max(100, "Full name cannot exceed 100 characters.")
      .transform((value) =>
        value.replace(/\s+/g, " ").trim(),
      ),

    username: z
      .string()
      .trim()
      .min(3, "Username must be at least 3 characters.")
      .max(30, "Username cannot exceed 30 characters.")
      .transform((value) =>
        value.startsWith("@")
          ? value.substring(1)
          : value,
      )
      .transform((value) => value.toLowerCase())
      .refine(
        (value: string) =>
          usernameRegex.test(value),
        {
          message:
            "Username may only contain lowercase letters, numbers, and underscores.",
        },
      ),

    password: z
      .string()
      .min(
        8,
        "Password must be at least 8 characters.",
      )
      .max(
        128,
        "Password cannot exceed 128 characters.",
      ),

    confirm_password: z
      .string()
      .min(
        1,
        "Please confirm your password.",
      ),
  })
  .refine(
    (data) =>
      data.password === data.confirm_password,
    {
      path: ["confirm_password"],
      message: "Passwords do not match.",
    },
  );

export type RegisterFormValues = z.infer<
  typeof registerSchema
>;