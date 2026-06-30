import { z } from "zod";

export const searchContactSchema = z.object({
  contact_number: z
    .string()
    .trim()
    .min(
      1,
      "Contact number is required.",
    )
    .refine(
      (value) => /^\d+$/.test(value),
      {
        message:
          "Contact number may contain numbers only.",
      },
    )
    .refine(
      (value) => value.length === 10,
      {
        message:
          "Contact number must contain exactly 10 digits.",
      },
    ),
});

export type SearchContactFormValues =
  z.infer<typeof searchContactSchema>;