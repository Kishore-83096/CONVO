import { z } from "zod";

const tenDigitContactNumber = z
  .string()
  .trim()
  .regex(/^\d{10}$/, "Contact number must be exactly 10 digits.");

export const ghostDurationValues = ["1h", "6h", "12h", "24h", "permanent"] as const;

export const contactSearchSchema = z.object({
  contact_number: tenDigitContactNumber,
});

export const addContactSchema = z.object({
  contact_number: tenDigitContactNumber,
  saved_name: z
    .string()
    .trim()
    .min(1, "Saved name is required.")
    .max(100, "Saved name must be 100 characters or less."),
});

export const renameContactSchema = z.object({
  saved_name: z
    .string()
    .trim()
    .min(1, "Saved name is required.")
    .max(100, "Saved name must be 100 characters or less."),
});

export const ghostContactSchema = z
  .object({
    is_ghosted: z.boolean(),
    duration: z.enum(ghostDurationValues).optional(),
  })
  .superRefine((value, ctx) => {
    if (value.is_ghosted && !value.duration) {
      ctx.addIssue({
        code: "custom",
        message: "Choose a ghost duration.",
        path: ["duration"],
      });
    }
  });

export type ContactSearchFormValues = z.infer<typeof contactSearchSchema>;
export type AddContactFormValues = z.infer<typeof addContactSchema>;
export type RenameContactFormValues = z.infer<typeof renameContactSchema>;
export type GhostContactFormValues = z.infer<typeof ghostContactSchema>;
export type GhostDuration = (typeof ghostDurationValues)[number];