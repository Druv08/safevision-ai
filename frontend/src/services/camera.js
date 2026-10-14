// navigator.mediaDevices is undefined outside a secure context (https or localhost).
export async function openCamera(constraints) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera access needs HTTPS or localhost, and a browser that supports it.");
  }
  try {
    return await navigator.mediaDevices.getUserMedia(constraints);
  } catch (e) {
    const msg = {
      NotAllowedError: "Camera permission was denied. Allow it in the browser's site settings.",
      NotFoundError: "No camera was found on this device.",
      NotReadableError: "The camera is in use by another application.",
    }[e.name];
    throw new Error(msg || `Could not open the camera: ${e.message}`, { cause: e });
  }
}
