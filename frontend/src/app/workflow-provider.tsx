"use client";

import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useState } from "react";

type AlertItem = {
  camera: string;
  timestamp: string;
  video_timestamp?: string;
  score: number;
  euclidean_distance?: number;
  snapshot?: string;
  bounding_box?: [number, number, number, number] | null;
  track_id?: number | null;
};

type UploadProgress = {
  missingImage: number;
  cam1: number;
  cam2: number;
  total: number;
};

type LiveBox = {
  camera: "CAM-1" | "CAM-2";
  frame_index: number;
  bbox: [number, number, number, number] | null;
  track_id?: number | null;
  score?: number | null;
};

type SessionWsPayload = {
  state?: string;
  progress_percent?: number;
  alerts?: AlertItem[];
  latest_boxes?: Partial<Record<"CAM-1" | "CAM-2", LiveBox | null>>;
  profile?: string;
  error?: string | null;
};

type SystemStatus = "booting" | "online" | "offline";

type WorkflowStep = 0 | 1 | 2 | 3;
type AnalysisProfile = "fast" | "balanced" | "accurate";

type WorkflowState = {
  step: WorkflowStep;
  setStep: (step: WorkflowStep) => void;
  missingImage: File | null;
  setMissingImage: (file: File | null) => void;
  cam1: File | null;
  setCam1: (file: File | null) => void;
  cam2: File | null;
  setCam2: (file: File | null) => void;
  sessionId: string | null;
  setSessionId: (value: string | null) => void;
  alerts: AlertItem[];
  setAlerts: (value: AlertItem[]) => void;
  loading: boolean;
  setLoading: (value: boolean) => void;
  error: string | null;
  setError: (value: string | null) => void;
  backendError: string | null;
  setBackendError: (value: string | null) => void;
  resetInfo: string | null;
  setResetInfo: (value: string | null) => void;
  resetting: boolean;
  setResetting: (value: boolean) => void;
  status: SystemStatus;
  setStatus: (value: SystemStatus) => void;
  lastChecked: string;
  setLastChecked: (value: string) => void;
  uploadKey: number;
  bumpUploadKey: () => void;
  readyToRun: boolean;
  uploadCount: number;
  progress: number;
  backendProgress: number;
  jobState: string;
  wsConnected: boolean;
  wsReconnecting: boolean;
  latestBoxes: Partial<Record<"CAM-1" | "CAM-2", LiveBox | null>>;
  uploadProgress: UploadProgress;
  analysisProfile: AnalysisProfile;
  setAnalysisProfile: (profile: AnalysisProfile) => void;
  missingPreview: string | null;
  cam1Preview: string | null;
  cam2Preview: string | null;
  resetSession: () => void;
  handleRunAnalysis: () => Promise<void>;
  handleResetPlatform: () => Promise<boolean>;
  handleExportEvidence: () => Promise<void>;
  streamUrl: (camera: "CAM-1" | "CAM-2") => string;
  snapshotUrl: (filename: string) => string;
};

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001"
).replace(/\/+$/, "");
const API_TIMEOUT_MS = 8000;

const WorkflowContext = createContext<WorkflowState | null>(null);

async function fetchWithTimeout(
  url: string,
  options?: RequestInit,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

function useObjectUrl(file: File | null) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  return url;
}

function formatTime(value?: string) {
  if (!value) return "--:--:--";
  return value;
}

function formatPercent(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}

function formatDecimal(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return value.toFixed(4);
}

function getWorkflowProgress(
  step: WorkflowStep,
  status: SystemStatus,
  loading: boolean,
  sessionId: string | null,
  alertCount: number,
  uploadCount: number,
) {
  if (step === 0) return 12;
  if (step === 1) return 28 + uploadCount * 4;
  if (step === 2) return 55 + uploadCount * 5;
  if (!sessionId) return 72 + uploadCount * 3;
  if (loading) return 84;
  if (alertCount > 0) return 100;
  if (status === "offline") return 78;
  return 90;
}

function normalizeProfile(value: string | null | undefined): AnalysisProfile {
  if (value === "fast" || value === "accurate") return value;
  return "balanced";
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [step, setStep] = useState<WorkflowStep>(0);
  const [missingImage, setMissingImage] = useState<File | null>(null);
  const [cam1, setCam1] = useState<File | null>(null);
  const [cam2, setCam2] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [resetInfo, setResetInfo] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [status, setStatus] = useState<SystemStatus>("booting");
  const [lastChecked, setLastChecked] = useState<string>("");
  const [uploadKey, setUploadKey] = useState(0);
  const [analysisProfile, setAnalysisProfile] =
    useState<AnalysisProfile>("balanced");
  const [backendProgress, setBackendProgress] = useState(0);
  const [jobState, setJobState] = useState<string>("idle");
  const [wsConnected, setWsConnected] = useState(false);
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [latestBoxes, setLatestBoxes] = useState<
    Partial<Record<"CAM-1" | "CAM-2", LiveBox | null>>
  >({
    "CAM-1": null,
    "CAM-2": null,
  });
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({
    missingImage: 0,
    cam1: 0,
    cam2: 0,
    total: 0,
  });

  const missingPreview = useObjectUrl(missingImage);
  const cam1Preview = useObjectUrl(cam1);
  const cam2Preview = useObjectUrl(cam2);

  const readyToRun = Boolean(missingImage && cam1 && cam2 && !loading);
  const uploadCount = [missingImage, cam1, cam2].filter(Boolean).length;
  const fallbackProgress = getWorkflowProgress(
    step,
    status,
    loading,
    sessionId,
    alerts.length,
    uploadCount,
  );
  const progress = sessionId
    ? Math.max(backendProgress, fallbackProgress)
    : fallbackProgress;

  useEffect(() => {
    let mounted = true;

    const checkHealth = async () => {
      try {
        const response = await fetchWithTimeout(`${BACKEND_URL}/health`);
        if (!mounted) return;

        if (response.ok) {
          const data = await response.json();
          setStatus(data.status === "Online" ? "online" : "offline");
          setBackendError(null);
        } else {
          setStatus("offline");
          setBackendError(
            "Backend health check failed. Confirm the API is running on port 8001.",
          );
        }
      } catch {
        if (mounted) {
          setStatus("offline");
          setBackendError(
            "Cannot reach backend. Start the backend service and retry.",
          );
        }
      } finally {
        if (mounted) setLastChecked(new Date().toLocaleTimeString());
      }
    };

    checkHealth();
    const interval = window.setInterval(checkHealth, 5000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    const wsUrl = `${BACKEND_URL.replace(/^http/, "ws")}/ws/session/${sessionId}`;
    let socket: WebSocket | null = null;
    let reconnectTimeoutId: number | null = null;
    let reconnectAttempts = 0;
    let closedByEffect = false;

    const maxBackoffMs = 15000;

    const clearReconnectTimer = () => {
      if (reconnectTimeoutId !== null) {
        window.clearTimeout(reconnectTimeoutId);
        reconnectTimeoutId = null;
      }
    };

    const scheduleReconnect = () => {
      if (closedByEffect) {
        return;
      }
      reconnectAttempts += 1;
      setWsConnected(false);
      setWsReconnecting(true);

      const jitterMs = Math.floor(Math.random() * 250);
      const backoffMs =
        Math.min(maxBackoffMs, 500 * 2 ** Math.max(0, reconnectAttempts - 1)) +
        jitterMs;

      reconnectTimeoutId = window.setTimeout(() => {
        connect();
      }, backoffMs);
    };

    const onPayload = (data: SessionWsPayload) => {
      setBackendProgress(Number(data.progress_percent ?? 0));
      setJobState(String(data.state ?? "running"));
      if (Array.isArray(data.alerts)) {
        setAlerts(data.alerts);
      }
      if (data.latest_boxes) {
        setLatestBoxes({
          "CAM-1": data.latest_boxes["CAM-1"] ?? null,
          "CAM-2": data.latest_boxes["CAM-2"] ?? null,
        });
      }
      if (typeof data.profile === "string") {
        setAnalysisProfile(normalizeProfile(data.profile));
      }
      if (data.error) {
        setBackendError(String(data.error));
      } else {
        setBackendError(null);
      }
    };

    const connect = () => {
      clearReconnectTimer();
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        reconnectAttempts = 0;
        setWsConnected(true);
        setWsReconnecting(false);
        setStatus("online");
        setBackendError(null);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SessionWsPayload;
          onPayload(data);
        } catch {
          setBackendError("WebSocket payload parse failed.");
        }
      };

      socket.onerror = () => {
        setWsConnected(false);
      };

      socket.onclose = () => {
        setWsConnected(false);
        scheduleReconnect();
      };
    };

    connect();

    const pollAlerts = async () => {
      try {
        const response = await fetchWithTimeout(
          `${BACKEND_URL}/api/alerts/${sessionId}`,
        );
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        setAlerts(Array.isArray(data.alerts) ? data.alerts : []);
      } catch {
        // Alerts continue over websocket; polling is fallback only.
      }
    };

    pollAlerts();
    const interval = window.setInterval(pollAlerts, 2500);
    return () => {
      closedByEffect = true;
      clearReconnectTimer();
      setWsReconnecting(false);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
      window.clearInterval(interval);
    };
  }, [sessionId]);

  const resetSession = () => {
    setSessionId(null);
    setAlerts([]);
    setError(null);
    setBackendError(null);
    setResetInfo(null);
    setBackendProgress(0);
    setJobState("idle");
    setWsConnected(false);
    setWsReconnecting(false);
    setLatestBoxes({ "CAM-1": null, "CAM-2": null });
    setUploadProgress({ missingImage: 0, cam1: 0, cam2: 0, total: 0 });
  };

  const handleResetPlatform = async () => {
    setResetting(true);
    setError(null);
    setResetInfo(null);

    try {
      const response = await fetchWithTimeout(
        `${BACKEND_URL}/api/system/reset-workspace`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ session_id: sessionId, prune_outputs: true }),
        },
      );

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Reset operation failed.");
      }

      resetSession();
      setMissingImage(null);
      setCam1(null);
      setCam2(null);
      setUploadKey((value) => value + 1);
      setStep(0);
      setBackendProgress(0);
      setJobState("idle");
      setResetInfo(
        "Platform reset completed. Temporary files were cleaned and session state was cleared.",
      );
      setStatus("online");
      return true;
    } catch (resetError) {
      setStatus("offline");
      setError(
        resetError instanceof Error
          ? resetError.message
          : "Failed to reset platform.",
      );
      return false;
    } finally {
      setResetting(false);
    }
  };

  const handleRunAnalysis = async () => {
    if (!missingImage || !cam1 || !cam2) {
      setError(
        "Upload the missing person image plus both camera feeds before starting.",
      );
      return;
    }

    setLoading(true);
    setError(null);
    setAlerts([]);
    setUploadProgress({ missingImage: 0, cam1: 0, cam2: 0, total: 0 });

    const formData = new FormData();
    formData.append("missing_image", missingImage);
    formData.append("cam1_video", cam1);
    formData.append("cam2_video", cam2);
    formData.append("profile", analysisProfile);

    try {
      const totalPayloadBytes = Math.max(
        1,
        missingImage.size + cam1.size + cam2.size,
      );
      const data = await uploadAnalyzeRequest(
        `${BACKEND_URL}/api/analyze`,
        formData,
        (loaded, total) => {
          const safeTotal = Math.max(
            totalPayloadBytes,
            total || totalPayloadBytes,
          );
          const normalized = Math.max(0, Math.min(1, loaded / safeTotal));
          const missingRatio = missingImage.size / totalPayloadBytes;
          const cam1Ratio = cam1.size / totalPayloadBytes;
          const cam2Ratio = cam2.size / totalPayloadBytes;

          setUploadProgress({
            missingImage: Math.min(
              100,
              Math.round(
                ((normalized * missingRatio * totalPayloadBytes) /
                  Math.max(1, missingImage.size)) *
                  100,
              ),
            ),
            cam1: Math.min(
              100,
              Math.round(
                ((normalized * cam1Ratio * totalPayloadBytes) /
                  Math.max(1, cam1.size)) *
                  100,
              ),
            ),
            cam2: Math.min(
              100,
              Math.round(
                ((normalized * cam2Ratio * totalPayloadBytes) /
                  Math.max(1, cam2.size)) *
                  100,
              ),
            ),
            total: Math.min(100, Math.round(normalized * 100)),
          });
        },
      );

      setSessionId(data.session_id);
      setBackendProgress(0);
      setJobState(String(data.job_state ?? "pending"));
      setAnalysisProfile(normalizeProfile(data.profile));
      setBackendError(null);
      setStatus("online");
      setStep(3);
      setUploadProgress({
        missingImage: 100,
        cam1: 100,
        cam2: 100,
        total: 100,
      });
    } catch (runError) {
      setStatus("offline");
      setError(
        runError instanceof Error
          ? runError.message
          : "Unexpected frontend error.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleExportEvidence = async () => {
    if (!alerts.length) {
      setError("No alerts are available to export.");
      return;
    }

    setError(null);
    const logoDataUrl = await fetch("/logo.png")
      .then(async (response) =>
        response.ok ? blobToDataUrl(await response.blob()) : null,
      )
      .catch(() => null);

    const snapshotEntries = await Promise.all(
      alerts.map(async (alert) => {
        if (!sessionId || !alert.snapshot) {
          return { ...alert, snapshotDataUrl: null as string | null };
        }

        try {
          const response = await fetch(
            `${BACKEND_URL}/api/snapshots/${sessionId}/${encodeURIComponent(alert.snapshot)}`,
          );
          if (!response.ok) {
            return { ...alert, snapshotDataUrl: null as string | null };
          }

          const blob = await response.blob();
          return {
            ...alert,
            snapshotDataUrl: await blobToDataUrl(blob),
          };
        } catch {
          return { ...alert, snapshotDataUrl: null as string | null };
        }
      }),
    );

    const { jsPDF } = await import("jspdf");
    const document = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
      compress: true,
    });

    const pageWidth = 210;
    const pageHeight = 297;
    const margin = 14;
    const contentWidth = pageWidth - margin * 2;
    const lineHeight = 6;

    const drawHeader = () => {
      document.setFillColor(20, 20, 20);
      document.rect(0, 0, pageWidth, 12, "F");
      if (logoDataUrl) {
        try {
          document.saveGraphicsState();
          document
            .circle(margin + 4.5, 6, 4.15, null)
            .clip()
            .discardPath();
          document.addImage(
            logoDataUrl,
            "PNG",
            margin - 0.2,
            1.3,
            9.4,
            9.4,
            undefined,
            "FAST",
          );
          document.restoreGraphicsState();
          document.setDrawColor(255, 255, 255);
          document.circle(margin + 4.5, 6, 4.15, "S");
        } catch {
          // Ignore image decode issues and continue with text header.
        }
      }
      document.setTextColor(255, 255, 255);
      document.setFont("helvetica", "bold");
      document.setFontSize(10);
      document.text("SURVEILLANCE EVIDENCE REPORT", margin + 12, 8);
      document.setFont("helvetica", "normal");
      document.text("Prepared by Ayush Kathil", pageWidth - margin - 52, 8);
      document.setTextColor(0, 0, 0);
    };

    const drawFooter = () => {
      const page = document.getCurrentPageInfo().pageNumber;
      document.setDrawColor(120, 120, 120);
      document.line(
        margin,
        pageHeight - 12,
        pageWidth - margin,
        pageHeight - 12,
      );
      document.setFont("helvetica", "normal");
      document.setFontSize(9);
      document.text(
        `Generated: ${new Date().toLocaleString()}`,
        margin,
        pageHeight - 7,
      );
      document.text(`Page ${page}`, pageWidth - margin - 12, pageHeight - 7);
    };

    const safeWrite = (
      text: string,
      x: number,
      y: number,
      maxWidth = contentWidth,
    ) => {
      const lines = document.splitTextToSize(text, maxWidth);
      document.text(lines, x, y);
      return y + lines.length * lineHeight;
    };

    const ensureSpace = (cursorY: number, requiredHeight: number) => {
      if (cursorY + requiredHeight <= pageHeight - margin) {
        return cursorY;
      }
      drawFooter();
      document.addPage();
      drawHeader();
      return margin + 4;
    };

    drawHeader();
    let y = margin + 6;
    document.setFont("helvetica", "bold");
    document.setFontSize(19);
    y = safeWrite("Surveillance Evidence Report", margin, y, contentWidth) + 2;

    document.setFont("helvetica", "normal");
    document.setFontSize(10);
    y = safeWrite(`Session ID: ${sessionId ?? "N/A"}`, margin, y) + 1;
    y = safeWrite(`Backend URL: ${BACKEND_URL}`, margin, y) + 1;
    y =
      safeWrite(`Generated At: ${new Date().toLocaleString()}`, margin, y) + 1;
    y = safeWrite(`Total Alerts: ${snapshotEntries.length}`, margin, y) + 1;

    const avgScore =
      snapshotEntries.reduce((acc, item) => acc + item.score, 0) /
      snapshotEntries.length;
    y =
      safeWrite(
        `Average Similarity Score: ${formatPercent(avgScore)}`,
        margin,
        y,
      ) + 5;

    document.setFont("helvetica", "bold");
    document.setFontSize(12);
    y = safeWrite("Alert Details", margin, y) + 2;

    for (let index = 0; index < snapshotEntries.length; index += 1) {
      const alert = snapshotEntries[index];
      y = ensureSpace(y, 74);

      document.setDrawColor(20, 20, 20);
      document.setLineWidth(0.2);
      document.roundedRect(margin, y, contentWidth, 52, 2, 2);

      document.setFont("helvetica", "bold");
      document.setFontSize(11);
      document.text(`Alert ${index + 1}`, margin + 3, y + 7);

      document.setFont("helvetica", "normal");
      document.setFontSize(10);
      document.text(`Camera: ${alert.camera}`, margin + 3, y + 14);
      document.text(`Timestamp: ${alert.timestamp}`, margin + 3, y + 20);
      document.text(
        `Video Time: ${formatTime(alert.video_timestamp)}`,
        margin + 3,
        y + 26,
      );
      document.text(
        `Similarity Score: ${formatPercent(alert.score)}`,
        margin + 3,
        y + 32,
      );
      document.text(
        `Euclidean Distance: ${formatDecimal(alert.euclidean_distance)}`,
        margin + 3,
        y + 38,
      );
      document.text(`Snapshot: ${alert.snapshot ?? "--"}`, margin + 3, y + 44);

      const imageX = margin + contentWidth - 58;
      const imageY = y + 4;
      const imageW = 54;
      const imageH = 44;

      if (alert.snapshotDataUrl) {
        try {
          document.addImage(
            alert.snapshotDataUrl,
            "JPEG",
            imageX,
            imageY,
            imageW,
            imageH,
            undefined,
            "FAST",
          );
        } catch {
          document.setFont("helvetica", "normal");
          document.setFontSize(9);
          document.text(
            "Snapshot unavailable",
            imageX + 4,
            imageY + imageH / 2,
          );
        }
      } else {
        document.setFont("helvetica", "normal");
        document.setFontSize(9);
        document.text("Snapshot unavailable", imageX + 4, imageY + imageH / 2);
      }

      y += 58;
    }

    y = ensureSpace(y, 34);
    document.setFont("helvetica", "bold");
    document.setFontSize(11);
    document.text("Investigator Signature", margin, y + 6);
    document.setFont("helvetica", "normal");
    document.setFontSize(10);
    document.line(margin, y + 16, margin + 80, y + 16);
    document.text("Name / Signature", margin, y + 21);
    document.line(margin + 95, y + 16, pageWidth - margin, y + 16);
    document.text("Date", margin + 95, y + 21);

    drawFooter();

    document.setProperties({
      title: "Surveillance Evidence Report",
      subject: "Missing Person Detection Export",
      creator: "Surveillance System Frontend",
      author: "Ayush Kathil",
      keywords: "surveillance,evidence,alerts,facial-match",
    });

    document.save(
      `surveillance_evidence_${sessionId?.slice(0, 8) ?? "session"}.pdf`,
    );
  };

  const streamUrl = (camera: "CAM-1" | "CAM-2") =>
    `${BACKEND_URL}/api/stream/${sessionId}/${camera}`;

  const value: WorkflowState = {
    step,
    setStep,
    missingImage,
    setMissingImage,
    cam1,
    setCam1,
    cam2,
    setCam2,
    sessionId,
    setSessionId,
    alerts,
    setAlerts,
    loading,
    setLoading,
    error,
    setError,
    backendError,
    setBackendError,
    resetInfo,
    setResetInfo,
    resetting,
    setResetting,
    status,
    setStatus,
    lastChecked,
    setLastChecked,
    uploadKey,
    bumpUploadKey: () => setUploadKey((value) => value + 1),
    readyToRun,
    uploadCount,
    progress,
    backendProgress,
    jobState,
    wsConnected,
    wsReconnecting,
    latestBoxes,
    uploadProgress,
    analysisProfile,
    setAnalysisProfile,
    missingPreview,
    cam1Preview,
    cam2Preview,
    resetSession,
    handleRunAnalysis,
    handleResetPlatform,
    handleExportEvidence,
    streamUrl,
    snapshotUrl: (filename: string) =>
      `${BACKEND_URL}/api/snapshots/${sessionId}/${encodeURIComponent(filename)}`,
  };

  return (
    <WorkflowContext.Provider value={value}>
      {children}
    </WorkflowContext.Provider>
  );
}

export function useWorkflow() {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error("useWorkflow must be used within WorkflowProvider");
  }
  return context;
}

async function blobToDataUrl(blob: Blob) {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Failed to read snapshot image."));
    reader.readAsDataURL(blob);
  });
}

async function uploadAnalyzeRequest(
  url: string,
  formData: FormData,
  onUploadProgress: (loaded: number, total: number) => void,
): Promise<{ session_id: string; profile: string; job_state: string }> {
  return await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        onUploadProgress(event.loaded, 0);
        return;
      }
      onUploadProgress(event.loaded, event.total);
    };

    xhr.onerror = () =>
      reject(new Error("Upload failed due to a network error."));
    xhr.onabort = () => reject(new Error("Upload aborted."));

    xhr.onload = () => {
      const payload = (xhr.response ?? {}) as {
        session_id?: string;
        profile?: string;
        job_state?: string;
        detail?: string;
      };
      if (xhr.status < 200 || xhr.status >= 300 || !payload.session_id) {
        reject(
          new Error(
            payload.detail || "The backend could not start the analysis.",
          ),
        );
        return;
      }
      resolve({
        session_id: payload.session_id,
        profile: payload.profile ?? "balanced",
        job_state: payload.job_state ?? "pending",
      });
    };

    xhr.send(formData);
  });
}

export function useWorkflowState() {
  return useWorkflow();
}
