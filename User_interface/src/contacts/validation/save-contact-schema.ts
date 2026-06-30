import { z } from "zod";

export const saveContactSchema = z.object({
  saved_name: z
    .string()
    .trim()
    .min(
      1,
      "Saved name is required.",
    )
    .min(
      2,
      "Saved name must be at least 2 characters.",
    )
    .max(
      100,
      "Saved name cannot exceed 100 characters.",
    )
    .transform((value) =>
      value.replace(/\s+/g, " "),
    ),
});

export type SaveContactFormValues =
  z.infer<typeof saveContactSchema>;