import { z } from "zod";

const usernameRegex = /^[a-z0-9_]+$/;
const contactNumberRegex = /^\d{10}$/;
const deleteConfirmationText = "DELETE MY ACCOUNT";

const manualUsernameSchema = z
  .string()
  .trim()
  .transform((value) => value.replace(/^@+/, "").toLowerCase())
  .pipe(
    z
      .string()
      .min(3, "Username must be at least 3 characters.")
      .max(30, "Username must be at most 30 characters.")
      .regex(
        usernameRegex,
        "Use only lowercase letters, numbers, and underscores.",
      ),
  );

const manualEmailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .email("Enter your generated email address.");

const manualContactNumberSchema = z
  .string()
  .trim()
  .regex(contactNumberRegex, "Contact number must be exactly 10 digits.");

export const registerSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(2, "Full name must be at least 2 characters.")
      .max(100, "Full name must be at most 100 characters."),

    username: manualUsernameSchema,

    password: z
      .string()
      .min(8, "Password must be at least 8 characters.")
      .max(128, "Password must be at most 128 characters."),

    confirm_password: z.string().min(1, "Confirm your password."),
  })
  .superRefine((values, ctx) => {
    if (values.password !== values.confirm_password) {
      ctx.addIssue({
        code: "custom",
        message: "Passwords do not match.",
        path: ["confirm_password"],
      });
    }
  });

export const loginSchema = z
  .object({
    method: z.enum(["username", "email", "contact_number"], {
      message: "Choose a login method.",
    }),

    identifier: z.string().trim().min(1, "Enter your login identifier."),

    password: z.string().min(1, "Enter your password."),
  })
  .superRefine((values, ctx) => {
    const identifier = values.identifier.trim();

    if (values.method === "username") {
      const normalizedUsername = identifier.replace(/^@+/, "").toLowerCase();

      if (normalizedUsername.length < 3 || normalizedUsername.length > 30) {
        ctx.addIssue({
          code: "custom",
          message: "Username must be 3–30 characters.",
          path: ["identifier"],
        });

        return;
      }

      if (!usernameRegex.test(normalizedUsername)) {
        ctx.addIssue({
          code: "custom",
          message: "Use only lowercase letters, numbers, and underscores.",
          path: ["identifier"],
        });
      }
    }

    if (values.method === "email") {
      const emailResult = z.string().email().safeParse(identifier);

      if (!emailResult.success) {
        ctx.addIssue({
          code: "custom",
          message: "Enter a valid email address.",
          path: ["identifier"],
        });
      }
    }

    if (values.method === "contact_number") {
      if (!contactNumberRegex.test(identifier)) {
        ctx.addIssue({
          code: "custom",
          message: "Contact number must be exactly 10 digits.",
          path: ["identifier"],
        });
      }
    }
  });

export const resetPasswordSchema = z
  .object({
    username: manualUsernameSchema,

    email: manualEmailSchema,

    contact_number: manualContactNumberSchema,

    current_password: z.string().min(1, "Enter your current password."),

    new_password: z
      .string()
      .min(8, "New password must be at least 8 characters.")
      .max(128, "New password must be at most 128 characters."),

    confirm_new_password: z.string().min(1, "Confirm your new password."),
  })
  .superRefine((values, ctx) => {
    if (values.new_password !== values.confirm_new_password) {
      ctx.addIssue({
        code: "custom",
        message: "New passwords do not match.",
        path: ["confirm_new_password"],
      });
    }

    if (values.current_password === values.new_password) {
      ctx.addIssue({
        code: "custom",
        message: "New password must be different from current password.",
        path: ["new_password"],
      });
    }
  });

export const deleteAccountSchema = z.object({
  username: manualUsernameSchema,

  email: manualEmailSchema,

  contact_number: manualContactNumberSchema,

  current_password: z.string().min(1, "Enter your current password."),

  confirmation_text: z
    .string()
    .trim()
    .refine((value) => value === deleteConfirmationText, {
      message: `Type ${deleteConfirmationText} exactly to confirm.`,
    }),
});

export type RegisterFormValues = z.infer<typeof registerSchema>;
export type LoginFormValues = z.infer<typeof loginSchema>;
export type ResetPasswordSchemaValues = z.infer<typeof resetPasswordSchema>;
export type DeleteAccountSchemaValues = z.infer<typeof deleteAccountSchema>;