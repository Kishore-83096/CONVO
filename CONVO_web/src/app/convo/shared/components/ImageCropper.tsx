import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type CSSProperties,
} from "react"

interface ImageCropperProps {
  file: File
  outputFileName?: string
  outputSize?: number
  onCancel: () => void
  onCrop: (file: File) => void
}

interface CropBox {
  x: number
  y: number
  size: number
}

type DragMode = "move" | "resize"

interface DragState {
  mode: DragMode
  pointerId: number
  startX: number
  startY: number
  startBox: CropBox
  handle?: string
}

const handles = [
  "nw",
  "n",
  "ne",
  "e",
  "se",
  "s",
  "sw",
  "w",
]

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error("Unable to load image."))
    image.src = src
  })
}

function canvasToBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error("Unable to crop image."))
        }
      },
      "image/jpeg",
      0.92,
    )
  })
}

function handlePosition(handle: string) {
  return {
    left: handle.includes("w") ? "0%" : handle.includes("e") ? "100%" : "50%",
    top: handle.includes("n") ? "0%" : handle.includes("s") ? "100%" : "50%",
  }
}

function ImageCropper({
  file,
  outputFileName = "profile-picture.jpg",
  outputSize = 512,
  onCancel,
  onCrop,
}: ImageCropperProps) {
  const imageUrl = useMemo(() => URL.createObjectURL(file), [file])
  const stageRef = useRef<HTMLDivElement | null>(null)
  const imageRef = useRef<HTMLImageElement | null>(null)
  const dragStateRef = useRef<DragState | null>(null)
  const [cropBox, setCropBox] = useState<CropBox | null>(null)
  const [error, setError] = useState("")
  const [isCropping, setIsCropping] = useState(false)

  useEffect(() => {
    return () => URL.revokeObjectURL(imageUrl)
  }, [imageUrl])

  const getBounds = () => {
    const stage = stageRef.current
    const image = imageRef.current

    if (!stage || !image) {
      return null
    }

    const stageRect = stage.getBoundingClientRect()
    const imageRect = image.getBoundingClientRect()

    return {
      x: imageRect.left - stageRect.left,
      y: imageRect.top - stageRect.top,
      width: imageRect.width,
      height: imageRect.height,
    }
  }

  const constrainBox = (box: CropBox) => {
    const bounds = getBounds()

    if (!bounds) {
      return box
    }

    const maxSize = Math.min(bounds.width, bounds.height)
    const size = clamp(box.size, Math.min(96, maxSize), maxSize)
    const x = clamp(box.x, bounds.x, bounds.x + bounds.width - size)
    const y = clamp(box.y, bounds.y, bounds.y + bounds.height - size)

    return { x, y, size }
  }

  const initialiseCropBox = () => {
    const bounds = getBounds()

    if (!bounds) {
      return
    }

    const size = Math.min(bounds.width, bounds.height) * 0.58

    setCropBox({
      x: bounds.x + (bounds.width - size) / 2,
      y: bounds.y + (bounds.height - size) / 2,
      size,
    })
  }

  const beginMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!cropBox) {
      return
    }

    event.currentTarget.setPointerCapture(event.pointerId)
    dragStateRef.current = {
      mode: "move",
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startBox: cropBox,
    }
  }

  const beginResize = (
    event: ReactPointerEvent<HTMLButtonElement>,
    handle: string,
  ) => {
    if (!cropBox) {
      return
    }

    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragStateRef.current = {
      mode: "resize",
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startBox: cropBox,
      handle,
    }
  }

  const updateDrag = (event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragStateRef.current

    if (!dragState || dragState.pointerId !== event.pointerId) {
      return
    }

    const dx = event.clientX - dragState.startX
    const dy = event.clientY - dragState.startY

    if (dragState.mode === "move") {
      setCropBox(
        constrainBox({
          ...dragState.startBox,
          x: dragState.startBox.x + dx,
          y: dragState.startBox.y + dy,
        }),
      )
      return
    }

    const handle = dragState.handle ?? "se"
    const horizontalDelta = handle.includes("w") ? -dx : handle.includes("e") ? dx : 0
    const verticalDelta = handle.includes("n") ? -dy : handle.includes("s") ? dy : 0
    const sizeDelta =
      Math.abs(horizontalDelta) > Math.abs(verticalDelta)
        ? horizontalDelta
        : verticalDelta
    const nextSize = dragState.startBox.size + sizeDelta
    const sizeChange = nextSize - dragState.startBox.size
    const nextBox = {
      size: nextSize,
      x: dragState.startBox.x - (handle.includes("w") ? sizeChange : 0),
      y: dragState.startBox.y - (handle.includes("n") ? sizeChange : 0),
    }

    setCropBox(constrainBox(nextBox))
  }

  const endDrag = (event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragStateRef.current

    if (dragState?.pointerId === event.pointerId) {
      dragStateRef.current = null
    }
  }

  const handleCrop = async () => {
    const bounds = getBounds()
    const imageElement = imageRef.current

    if (!cropBox || !bounds || !imageElement) {
      setError("Choose a crop area first.")
      return
    }

    setIsCropping(true)
    setError("")

    try {
      const image = await loadImage(imageUrl)
      const scaleX = image.naturalWidth / bounds.width
      const scaleY = image.naturalHeight / bounds.height
      const sourceX = (cropBox.x - bounds.x) * scaleX
      const sourceY = (cropBox.y - bounds.y) * scaleY
      const sourceSize = cropBox.size * Math.min(scaleX, scaleY)
      const canvas = document.createElement("canvas")
      canvas.width = outputSize
      canvas.height = outputSize

      const context = canvas.getContext("2d")

      if (!context) {
        throw new Error("Image cropping is not supported in this browser.")
      }

      context.drawImage(
        image,
        sourceX,
        sourceY,
        sourceSize,
        sourceSize,
        0,
        0,
        outputSize,
        outputSize,
      )

      const blob = await canvasToBlob(canvas)
      onCrop(new File([blob], outputFileName, { type: "image/jpeg" }))
    } catch (cropError) {
      setError(
        cropError instanceof Error
          ? cropError.message
          : "Unable to crop image.",
      )
    } finally {
      setIsCropping(false)
    }
  }

  return (
    <section className="image-cropper" aria-label="Image cropper">
      <header className="image-cropper-header">
        <button className="image-cropper-pill" type="button" onClick={onCancel}>
          Cancel
        </button>
        <div className="image-cropper-tools" aria-label="Crop tools">
          <span className="image-cropper-tool active">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 2V18H22" />
              <path d="M2 6H18V22" />
            </svg>
            <span>Crop</span>
          </span>
        </div>
        <button
          className="image-cropper-done"
          type="button"
          disabled={isCropping}
          onClick={() => void handleCrop()}
        >
          {isCropping ? "Cropping..." : "Done"}
        </button>
      </header>

      <div
        className="image-cropper-stage"
        ref={stageRef}
        onPointerMove={updateDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <img
          ref={imageRef}
          className="image-cropper-image"
          src={imageUrl}
          alt=""
          onLoad={initialiseCropBox}
        />

        {cropBox ? (
          <div
            className="image-cropper-box"
            style={{
              width: cropBox.size,
              height: cropBox.size,
              transform: `translate(${cropBox.x}px, ${cropBox.y}px)`,
              "--crop-frame-size": `${cropBox.size}px`,
            } as CSSProperties}
            onPointerDown={beginMove}
          >
            <div className="image-cropper-frame" />
            {handles.map((handle) => (
              <button
                aria-label={`Resize ${handle}`}
                className={`image-cropper-handle image-cropper-handle-${handle}`}
                key={handle}
                style={handlePosition(handle)}
                type="button"
                onPointerDown={(event) => beginResize(event, handle)}
              />
            ))}
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="convo-profile-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}

export default ImageCropper
