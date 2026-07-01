import { useRef, useState } from "react";

import { Button } from "../../../shared/ui/Button";
import { useUpdateMyProfilePicture } from "../hooks";

function isAllowedImage(file: File) {
  return file.type === "image/jpeg" || file.type === "image/png";
}

export function ProfilePictureUpdatePanel() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const updatePicture = useUpdateMyProfilePicture();

  const isDisabled = updatePicture.isPending;

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    setClientError("");
    setSelectedFile(null);

    if (!file) {
      return;
    }

    if (!isAllowedImage(file)) {
      setClientError("Only JPEG and PNG images are allowed.");
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  }

  async function handleUpdatePicture() {
    setClientError("");

    if (!selectedFile) {
      setClientError("Choose a JPEG or PNG image first.");
      return;
    }

    const formData = new FormData();
    formData.append("image", selectedFile);

    const result = await updatePicture.mutateAsync(formData);

    if (result.ok) {
      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  return (
    <section
      className="account-settings-panel"
      aria-label="Update profile picture"
    >
      <div className="section-heading">
        <p className="eyebrow">Phase 2.17</p>
        <h2>Replace Profile Picture</h2>
        <p>
          This replaces the existing profile picture using PATCH
          /profiles/me/picture.
        </p>
      </div>

      <label className="field-group">
        <span>New image file</span>
        <input
          accept="image/jpeg,image/png"
          className="text-input"
          disabled={isDisabled}
          onChange={handleFileChange}
          ref={fileInputRef}
          type="file"
        />
      </label>

      {selectedFile ? (
        <div className="auth-success" role="status">
          <strong>Selected replacement file</strong>
          <p>
            {selectedFile.name} — {Math.ceil(selectedFile.size / 1024)} KB
          </p>
        </div>
      ) : null}

      {clientError ? (
        <div className="auth-error" role="alert">
          {clientError}
        </div>
      ) : null}

      {updatePicture.data && !updatePicture.data.ok ? (
        <div className="auth-error" role="alert">
          {updatePicture.data.message}
        </div>
      ) : null}

      {updatePicture.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Profile picture replaced.</strong>
          <p>The profile picture section should refresh automatically.</p>
        </div>
      ) : null}

      {updatePicture.isError ? (
        <div className="auth-error" role="alert">
          Profile picture replacement failed before the server returned a
          response.
        </div>
      ) : null}

      <div className="actions">
        <Button
          disabled={isDisabled || !selectedFile}
          onClick={() => void handleUpdatePicture()}
          type="button"
        >
          {isDisabled ? "Replacing..." : "Replace profile picture"}
        </Button>

        <Button
          disabled={isDisabled}
          onClick={() => {
            setSelectedFile(null);
            setClientError("");

            if (fileInputRef.current) {
              fileInputRef.current.value = "";
            }
          }}
          type="button"
          variant="secondary"
        >
          Clear file
        </Button>
      </div>
    </section>
  );
}