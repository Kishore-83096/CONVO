import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  basicProfileUpdateSchema,
  type BasicProfileUpdateFormValues,
} from "../schemas";
import { useMyProfileBasic, useUpdateMyProfileBasic } from "../hooks";
import type { ProfileBasic } from "../types";

type BasicProfileUpdatePanelProps = {
  initialBasicProfile?: ProfileBasic | null;
  onUpdated?: () => void;
};

function toPayload(values: BasicProfileUpdateFormValues) {
  return {
    bio: values.bio.trim() || undefined,
    date_of_birth: values.date_of_birth || undefined,
    gender: values.gender.trim() || undefined,
    occupation: values.occupation.trim() || undefined,
    website: values.website.trim() || undefined,
  };
}

export function BasicProfileUpdatePanel({
  initialBasicProfile,
  onUpdated,
}: BasicProfileUpdatePanelProps) {
  const basicProfileQuery = useMyProfileBasic();
  const updateBasicProfile = useUpdateMyProfileBasic();

  const basicProfileResult = basicProfileQuery.data;
  const queriedBasicProfile = basicProfileResult?.ok
    ? basicProfileResult.data
    : undefined;
  const basicProfile = initialBasicProfile ?? queriedBasicProfile;

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<BasicProfileUpdateFormValues>({
    resolver: zodResolver(basicProfileUpdateSchema),
    defaultValues: {
      bio: "",
      date_of_birth: "",
      gender: "",
      occupation: "",
      website: "",
    },
  });

  useEffect(() => {
    if (!basicProfile) {
      return;
    }

    reset({
      bio: basicProfile.bio ?? "",
      date_of_birth: basicProfile.date_of_birth ?? "",
      gender: basicProfile.gender ?? "",
      occupation: basicProfile.occupation ?? "",
      website: basicProfile.website ?? "",
    });
  }, [basicProfile, reset]);

  async function onSubmit(values: BasicProfileUpdateFormValues) {
    const result = await updateBasicProfile.mutateAsync(toPayload(values));

    if (result.ok) {
      onUpdated?.();
    }
  }

  const isLoadingExistingProfile =
    !initialBasicProfile && basicProfileQuery.isPending;
  const isDisabled =
    isSubmitting || updateBasicProfile.isPending || isLoadingExistingProfile;

  return (
    <section className="account-settings-panel" aria-label="Update basic profile">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.4</p>
        <h2>Edit Basic Profile</h2>
        <p>
          This form updates the existing basic profile using PATCH
          /profiles/me/basic. It is separate from the create form.
        </p>
      </div>

      {isLoadingExistingProfile ? (
        <div className="auth-success" role="status">
          <strong>Loading existing basic profile...</strong>
          <p>The edit form will fill after the profile is loaded.</p>
        </div>
      ) : null}

      {!basicProfileQuery.isPending &&
      basicProfileResult &&
      !basicProfileResult.ok ? (
        <div className="auth-error" role="alert">
          {basicProfileResult.message}
        </div>
      ) : null}

      {!basicProfileQuery.isPending && basicProfileQuery.isError ? (
        <div className="auth-error" role="alert">
          Existing basic profile request failed before the server returned a
          response.
        </div>
      ) : null}

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

        {updateBasicProfile.data && !updateBasicProfile.data.ok ? (
          <div className="auth-error" role="alert">
            {updateBasicProfile.data.message}
          </div>
        ) : null}

        {updateBasicProfile.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Basic profile updated.</strong>
            <p>The read-only profile sections should refresh automatically.</p>
          </div>
        ) : null}

        {updateBasicProfile.isError ? (
          <div className="auth-error" role="alert">
            Basic profile update failed before the server returned a response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? "Updating..." : "Update basic profile"}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={() =>
              reset({
                bio: basicProfile?.bio ?? "",
                date_of_birth: basicProfile?.date_of_birth ?? "",
                gender: basicProfile?.gender ?? "",
                occupation: basicProfile?.occupation ?? "",
                website: basicProfile?.website ?? "",
              })
            }
            type="button"
            variant="secondary"
          >
            Reset to saved values
          </Button>
        </div>
      </form>
    </section>
  );
}
