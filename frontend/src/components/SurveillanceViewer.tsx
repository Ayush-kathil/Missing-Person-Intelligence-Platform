"use client";

import React, { useEffect, useRef, useState } from "react";

interface SurveillanceViewerProps {
  sessionId: string;
  cameraId: string;
  videoUrl: string;
  wsUrl: string;
}

export default function SurveillanceViewer({
  sessionId,
  cameraId,
  videoUrl,
  wsUrl,
}: SurveillanceViewerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Store the latest box in a ref so the render loop can access it without re-renders
  const latestBoxRef = useRef<number[] | null>(null);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.latest_boxes && data.latest_boxes[cameraId]) {
          latestBoxRef.current = data.latest_boxes[cameraId];
        } else {
          latestBoxRef.current = null;
        }
      } catch (e) {
        console.error("Failed to parse WS telemetry", e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [wsUrl, cameraId, sessionId]);

  useEffect(() => {
    let animationFrameId: number;

    const renderCanvas = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          // Match canvas size to video display size
          canvas.width = video.clientWidth;
          canvas.height = video.clientHeight;

          ctx.clearRect(0, 0, canvas.width, canvas.height);

          const box = latestBoxRef.current;
          if (box && box.length === 4) {
            // The backend processes at a max width of 960 (or intrinsic if smaller).
            // We assume the bounding box is relative to the processed size.
            // For robustness, we map the box to the video's intrinsic dimensions,
            // then scale to the display dimensions.
            // (Assuming backend scaled the video to min(intrinsic_width, 960)).
            const scaleX =
              canvas.width / Math.min(video.videoWidth || 960, 960);
            const scaleY =
              canvas.height /
              (video.videoHeight *
                (Math.min(video.videoWidth || 960, 960) /
                  (video.videoWidth || 1)) || 1);

            const [x1, y1, x2, y2] = box;
            const sx1 = x1 * scaleX;
            const sy1 = y1 * scaleY;
            const sx2 = x2 * scaleX;
            const sy2 = y2 * scaleY;

            ctx.strokeStyle = "rgba(0, 255, 0, 0.8)";
            ctx.lineWidth = 3;
            ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

            // Draw label background
            ctx.fillStyle = "rgba(0, 255, 0, 0.8)";
            ctx.fillRect(sx1, sy1 - 20, 100, 20);

            // Draw label text
            ctx.fillStyle = "#000";
            ctx.font = "12px sans-serif";
            ctx.fillText("TARGET", sx1 + 5, sy1 - 5);
          }
        }
      }
      animationFrameId = requestAnimationFrame(renderCanvas);
    };

    renderCanvas();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="relative w-full h-full rounded-[1.5rem] overflow-hidden soft-container p-0">
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full h-full object-cover"
        autoPlay
        muted
        loop
        playsInline
      />
      <canvas
        ref={canvasRef}
        className="absolute top-0 left-0 w-full h-full pointer-events-none"
      />
      {!isConnected && (
        <div className="absolute top-4 right-4 glass-overlay px-3 py-1 flex items-center gap-2 text-xs font-semibold text-red-500">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          Offline
        </div>
      )}
      {isConnected && (
        <div className="absolute top-4 right-4 glass-overlay px-3 py-1 flex items-center gap-2 text-xs font-semibold text-green-600">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live Telemetry
        </div>
      )}
    </div>
  );
}
