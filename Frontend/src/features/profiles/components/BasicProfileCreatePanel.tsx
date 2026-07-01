import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  basicProfileCreateSchema,
  type BasicProfileCreateFormValues,
} from "../schemas";
import { useCreateMyProfileBasic } from "../hooks";

type BasicProfileCreatePanelProps = {
  onCreated?: () => void;
};

function toPayload(values: BasicProfileCreateFormValues) {
  return {
    bio: values.bio.trim() || undefined,
    date_of_birth: values.date_of_birth || undefined,
    gender: values.gender.trim() || undefined,
    occupation: values.occupation.trim() || undefined,
    website: values.website.trim() || undefined,
  };
}

export function BasicProfileCreatePanel({
  onCreated,
}: BasicProfileCreatePanelProps = {}) {
  const createBasicProfile = useCreateMyProfileBasic();

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<BasicProfileCreateFormValues>({
    resolver: zodResolver(basicProfileCreateSchema),
    defaultValues: {
      bio: "",
      date_of_birth: "",
      gender: "",
      occupation: "",
      website: "",
    },
  });

  async function onSubmit(values: BasicProfileCreateFormValues) {
    const result = await createBasicProfile.mutateAsync(toPayload(values));

    if (result.ok) {
      reset();
      onCreated?.();
    }
  }

  const isDisabled = isSubmitting || createBasicProfile.isPending;

  return (
    <section
      className="account-settings-panel"
      aria-label="Create basic profile"
    >
      <div className="section-heading">
        <p className="eyebrow">Phase 2.3</p>
        <h2>Create Basic Profile</h2>
        <p>
          This form creates the basic profile using POST /profiles/me/basic.
          Update and delete are not included in this phase.
        </p>
      </div>

      <form className="settings-form" onSubmit={handleSubmit(onSubmit)}>
        <label className="field-group">
          <span>Bio</span>
          <textarea
            {...register("bio")}
            className="text-input"
            disabled={isDisabled}
            maxLength={500}
            placeholder="Write a short bio"
            rows={4}
          />
          {errors.bio ? (
            <small className="field-error">{errors.bio.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Date of birth</span>
          <input
            {...register("date_of_birth")}
            className="text-input"
            disabled={isDisabled}
            type="date"
          />
          {errors.date_of_birth ? (
            <small className="field-error">
              {errors.date_of_birth.message}
            </small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Gender</span>
          <input
            {...register("gender")}
            className="text-input"
            disabled={isDisabled}
            maxLength={50}
            placeholder="Example: male, female, non-binary"
            type="text"
          />
          {errors.gender ? (
            <small className="field-error">{errors.gender.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Occupation</span>
          <input
            {...register("occupation")}
            className="text-input"
            disabled={isDisabled}
            maxLength={100}
            placeholder="Example: Software Engineer"
            type="text"
          />
          {errors.occupation ? (
            <small className="field-error">{errors.occupation.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Website</span>
          <input
            {...register("website")}
            className="text-input"
            disabled={isDisabled}
            placeholder="https://example.com"
            type="url"
          />
          {errors.website ? (
            <small className="field-error">{errors.website.message}</small>
          ) : null}
        </label>

        {createBasicProfile.data && !createBasicProfile.data.ok ? (
          <div className="auth-error" role="alert">
            {createBasicProfile.data.message}
          </div>
        ) : null}

        {createBasicProfile.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Basic profile created.</strong>
            <p>The read-only profile sections should refresh automatically.</p>
          </div>
        ) : null}

        {createBasicProfile.isError ? (
          <div className="auth-error" role="alert">
            Basic profile request failed before the server returned a response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? "Creating..." : "Create basic profile"}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={() => reset()}
            type="button"
            variant="secondary"
          >
            Clear form
          </Button>
        </div>
      </form>
    </section>
  );
}
