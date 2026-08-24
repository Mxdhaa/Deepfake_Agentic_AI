"use client";

import { useState, useRef, useEffect, useCallback } from "react";

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  const [isActive, setIsActive] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [countdown, setCountdown] = useState<number>(5);
  const [error, setError] = useState<string | null>(null);

  /**
   * Explicitly stop all media tracks and release camera/mic resources immediately.
   */
  const stopCamera = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setIsActive(false);
    setIsRecording(false);
  }, []);

  /**
   * Request user media and attach to video ref.
   */
  const startCamera = useCallback(async () => {
    stopCamera(); // Clean any previous session
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false, // Do not request mic unless required for AV sync
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }

      setIsActive(true);
    } catch (err: any) {
      setError("Camera permission denied or device not found.");
      setIsActive(false);
    }
  }, [stopCamera]);

  /**
   * Start 5-second liveness capture and auto-stop camera upon completion.
   */
  const startRecording = useCallback(() => {
    if (!streamRef.current) return;

    recordedChunksRef.current = [];
    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
      ? "video/webm;codecs=vp9"
      : "video/webm";

    const recorder = new MediaRecorder(streamRef.current, { mimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        recordedChunksRef.current.push(e.data);
      }
    };

    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: "video/webm" });
      setRecordedBlob(blob);
      setIsRecording(false);
      // Immediately stop hardware camera stream
      stopCamera();
    };

    recorder.start(100);
    setIsRecording(true);
    setCountdown(5);

    let count = 5;
    const interval = setInterval(() => {
      count--;
      setCountdown(count);
      if (count <= 0) {
        clearInterval(interval);
        if (recorder.state === "recording") {
          recorder.stop();
        }
      }
    }, 1000);
  }, [stopCamera]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  return {
    videoRef,
    isActive,
    isRecording,
    recordedBlob,
    countdown,
    error,
    startCamera,
    stopCamera,
    startRecording,
    setRecordedBlob,
  };
}
