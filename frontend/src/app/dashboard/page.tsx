"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import SurveillanceViewer from "@/components/SurveillanceViewer";
import { ErrorBoundary } from "@/components/ErrorBoundary";

// Define the shape of our alert objects coming from the backend
interface Alert {
  timestamp: string;
  camera: string;
  score: number;
  snapshot: string;
}

export default function DashboardCommandCenter() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [backendUrl, setBackendUrl] = useState("http://localhost:8001");
  const [wsUrl, setWsUrl] = useState("ws://localhost:8001");

  useEffect(() => {
    const storedSession = sessionStorage.getItem("current_session_id");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (storedSession) setSessionId(storedSession);

    const baseUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

    setBackendUrl(baseUrl.replace(/\/+$/, ""));

    setWsUrl(baseUrl.replace(/^http/, "ws").replace(/\/+$/, ""));
  }, []);

  // Poll for alerts periodically
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${backendUrl}/api/alerts/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setAlerts(data.alerts || []);
        }
      } catch (err) {
        console.error("Failed to fetch alerts", err);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [sessionId, backendUrl]);

  if (!sessionId) {
    return (
      <div className="w-full min-h-screen flex items-center justify-center soft-container m-4">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-700">
            No Active Session
          </h2>
          <p className="text-gray-500 mt-2">
            Please upload media to begin surveillance.
          </p>
          <button className="soft-button mt-6" onClick={() => router.push("/")}>
            Go to Upload
          </button>
        </div>
      </div>
    );
  }

  // Filter alerts for high-confidence DeepFace matches (>0.85)
  const confirmedMatches = alerts.filter((a) => a.score > 0.85);

  return (
    <div className="min-h-screen w-full bg-[#F8F9FA] p-6 flex gap-6">
      {/* Floating Sidebar */}
      <aside className="w-64 soft-container flex flex-col justify-between shrink-0 h-[calc(100vh-3rem)] sticky top-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#2D3748]">
            Command Center
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Session: {sessionId.substring(0, 8)}...
          </p>
          <div className="mt-8 space-y-4">
            <div className="p-4 bg-white/40 rounded-2xl border border-white/60 shadow-sm">
              <p className="text-xs font-semibold text-gray-500 uppercase">
                System Status
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
                <span className="text-sm font-medium">YOLOv12 Active</span>
              </div>
            </div>
            <div className="p-4 bg-white/40 rounded-2xl border border-white/60 shadow-sm">
              <p className="text-xs font-semibold text-gray-500 uppercase">
                Total Matches
              </p>
              <p className="text-2xl font-bold text-[#3182CE] mt-1">
                {confirmedMatches.length}
              </p>
            </div>
          </div>
        </div>

        <button
          className="soft-button w-full text-red-500 hover:text-red-600"
          onClick={() => {
            sessionStorage.removeItem("current_session_id");
            router.push("/");
          }}
        >
          End Session
        </button>
      </aside>

      {/* Main Grid & Event Log */}
      <main className="flex-1 flex flex-col gap-6">
        {/* 2x2 Grid for Cameras */}
        <div className="grid grid-cols-2 gap-6 h-[60vh]">
          <ErrorBoundary>
            <SurveillanceViewer
              sessionId={sessionId}
              cameraId="CAM-1"
              videoUrl={`${backendUrl}/api/video/${sessionId}/CAM-1`}
              wsUrl={`${wsUrl}/ws/session/${sessionId}`}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <SurveillanceViewer
              sessionId={sessionId}
              cameraId="CAM-2"
              videoUrl={`${backendUrl}/api/video/${sessionId}/CAM-2`}
              wsUrl={`${wsUrl}/ws/session/${sessionId}`}
            />
          </ErrorBoundary>

          {/* Placeholders for scaling to 4 cameras */}
          <div className="soft-container flex items-center justify-center opacity-50 bg-gray-100">
            <span className="font-semibold text-gray-400">CAM-3 (Offline)</span>
          </div>
          <div className="soft-container flex items-center justify-center opacity-50 bg-gray-100">
            <span className="font-semibold text-gray-400">CAM-4 (Offline)</span>
          </div>
        </div>

        {/* Real-time Event Log */}
        <div className="soft-container flex-1 overflow-y-auto">
          <h3 className="font-semibold text-lg mb-4">
            Confirmed Matches (&gt; 85%)
          </h3>
          {confirmedMatches.length === 0 ? (
            <p className="text-gray-500 text-sm">
              No confirmed matches yet. Awaiting telemetry...
            </p>
          ) : (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {confirmedMatches.map((alert, idx) => (
                <div
                  key={idx}
                  className="shrink-0 w-64 p-3 glass-overlay animate-in slide-in-from-right-4"
                >
                  <div className="aspect-video bg-gray-200 rounded-xl mb-3 overflow-hidden relative">
                    {alert.snapshot ? (
                      <img
                        src={`${backendUrl}/api/snapshots/${sessionId}/${alert.snapshot}`}
                        alt="Match Snapshot"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                        No Image
                      </div>
                    )}
                  </div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-bold bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
                      {alert.camera}
                    </span>
                    <span className="text-xs text-gray-500">
                      {alert.timestamp.split(" ")[1]}
                    </span>
                  </div>
                  <p className="text-sm font-semibold">
                    Similarity: {(alert.score * 100).toFixed(1)}%
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
