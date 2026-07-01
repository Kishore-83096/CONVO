import { useRef, useState } from "react";

import { Button } from "../../../shared/ui/Button";
import { useCreateMyProfilePicture } from "../hooks";

function isAllowedImage(file: File) {
  return file.type === "image/jpeg" || file.type === "image/png";
}

export function ProfilePictureCreatePanel() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const createPicture = useCreateMyProfilePicture();

  const isDisabled = createPicture.isPending;

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

  async function handleCreatePicture() {
    setClientError("");

    if (!selectedFile) {
      setClientError("Choose a JPEG or PNG image first.");
      return;
    }

    const formData = new FormData();
    formData.append("image", selectedFile);

    const result = await createPicture.mutateAsync(formData);

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
      aria-label="Create profile picture"
    >
      <div className="section-heading">
        <p className="eyebrow">Phase 2.16</p>
        <h2>Create Profile Picture</h2>
        <p>
          This uploads a new profile picture using POST /profiles/me/picture.
          Use this when no profile picture exists yet.
        </p>
      </div>

      <label className="field-group">
        <span>Image file</span>
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
          <strong>Selected file</strong>
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

      {createPicture.data && !createPicture.data.ok ? (
        <div className="auth-error" role="alert">
          {createPicture.data.message}
        </div>
      ) : null}

      {createPicture.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Profile picture uploaded.</strong>
          <p>The profile picture section should refresh automatically.</p>
        </div>
      ) : null}

      {createPicture.isError ? (
        <div className="auth-error" role="alert">
          Profile picture upload failed before the server returned a response.
        </div>
      ) : null}

      <div className="actions">
        <Button
          disabled={isDisabled || !selectedFile}
          onClick={() => void handleCreatePicture()}
          type="button"
        >
          {isDisabled ? "Uploading..." : "Create profile picture"}
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