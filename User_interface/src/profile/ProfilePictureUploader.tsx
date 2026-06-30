import { useState, type ChangeEvent } from "react";
import { ImageUp, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import Button from "@/ui/Button";
import { isApiError } from "@/api/api-errors";

import {
  profileApi,
  type ProfilePicture,
} from "./profile-api";

interface ProfilePictureUploaderProps {
  picture: ProfilePicture;
  initials: string;
}

const allowedTypes = new Set([
  "image/jpeg",
  "image/png",
]);

export function ProfilePictureUploader({
  picture,
  initials,
}: ProfilePictureUploaderProps) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasPicture = picture !== null;

  const invalidateProfile = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["profile", "complete"],
    });
  };

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      hasPicture
        ? profileApi.patchPicture(file)
        : profileApi.createPicture(file),
    onSuccess: async () => {
      setSelectedFile(null);
      setError(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setError(errorMessage(mutationError));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => profileApi.deletePicture(),
    onSuccess: invalidateProfile,
    onError: (mutationError) => {
      setError(errorMessage(mutationError));
    },
  });

  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0] ?? null;
    setError(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!allowedTypes.has(file.type)) {
      setSelectedFile(null);
      setError("Choose a JPEG or PNG image.");
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  }

  function handleUpload() {
    if (!selectedFile) {
      setError("Choose an image before uploading.");
      return;
    }

    uploadMutation.mutate(selectedFile);
  }

  return (
    <section className="profile-panel">
      <div className="profile-panel__header">
        <div>
          <h2>Profile Picture</h2>
          <p>Upload, replace, or remove your JPEG/PNG profile image.</p>
        </div>
      </div>

      {error && <div className="profile-error">{error}</div>}

      <div className="profile-picture-row">
        <div className="profile-picture" aria-label="Profile picture">
          {picture?.url ? (
            <img src={picture.url} alt="" />
          ) : (
            <span>{initials}</span>
          )}
        </div>

        <div className="profile-form">
          <label className="profile-field">
            <span>Image</span>
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={handleFileChange}
            />
            <small>
              {picture
                ? `${picture.format.toUpperCase()} - ${picture.width} x ${picture.height}`
                : "No profile image has been uploaded."}
            </small>
          </label>

          <div className="profile-actions">
            <Button
              type="button"
              variant="secondary"
              leftIcon={<ImageUp size={16} />}
              loading={uploadMutation.isPending}
              onClick={handleUpload}
            >
              {hasPicture ? "Replace" : "Upload"}
            </Button>

            {hasPicture && (
              <Button
                type="button"
                variant="danger"
                leftIcon={<Trash2 size={16} />}
                loading={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                Remove
              </Button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.getFieldError("image") ?? error.message;
  }

  return "Profile picture could not be updated.";
}
