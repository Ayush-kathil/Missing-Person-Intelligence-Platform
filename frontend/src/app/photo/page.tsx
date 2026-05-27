"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BackArrow } from "../back-arrow";
import { BrandMark } from "../brand-mark";
import { useWorkflow } from "../workflow-provider";

export default function PhotoPage() {
  const router = useRouter();
  const {
    missingImage,
    setMissingImage,
    missingPreview,
    setStep,
    uploadKey,
    uploadProgress,
    loading,
  } = useWorkflow();
  const [dragActive, setDragActive] = useState(false);
  const [previewReady, setPreviewReady] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewReady(false);
  }, [missingPreview]);

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    if (file && file.type.startsWith("image/")) {
      setMissingImage(file);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_15%_0%,#fff8ed_0%,transparent_44%),radial-gradient(circle_at_90%_5%,#dfe8f0_0%,transparent_42%),linear-gradient(180deg,#fefcf8_0%,#f4eee6_60%,#ece5db_100%)] text-black">
      <div className="pointer-events-none absolute inset-0 opacity-50">
        <div className="photo-step-grid absolute inset-0" />
      </div>

      <div className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-6 py-8 sm:px-10 lg:px-12">
        <section className="w-full space-y-6 reveal">
          <div className="flex items-center justify-start">
            <BackArrow fallbackHref="/" />
          </div>

          <div className="flex justify-center reveal-delay-1">
            <BrandMark compact />
          </div>

          <div className="text-center space-y-4 reveal-delay-1">
            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-black px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.28em] text-white shadow-[0_8px_20px_rgba(0,0,0,0.2)]">
              Step 1
            </div>
            <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
              Upload the missing person photo.
            </h1>
            <p className="mx-auto max-w-2xl text-sm leading-7 text-black/65 sm:text-base">
              Add a clear frontal image and preview it here before moving to the
              camera upload step.
            </p>
          </div>

          <div className="grid gap-5 rounded-[2rem] border border-black/10 bg-white/95 p-5 shadow-[0_24px_64px_rgba(0,0,0,0.08)] backdrop-blur sm:p-6 lg:grid-cols-[1.1fr_1fr] reveal-delay-2">
            <div className="space-y-5">
              <div className="text-left">
                <p className="text-xs uppercase tracking-[0.24em] text-black/45">
                  Photo upload
                </p>
                <h2 className="mt-2 text-2xl font-bold text-black">
                  Missing person image
                </h2>
                <p className="mt-2 text-sm text-black/55">
                  Use a frontal image with clear lighting for higher match
                  confidence.
                </p>
              </div>

              <label
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                className={`group relative block overflow-hidden rounded-[1.5rem] border border-dashed p-4 transition duration-300 ${dragActive ? "scale-[1.01] border-black/55 bg-black/[0.06] shadow-[0_16px_34px_rgba(0,0,0,0.15)]" : "border-black/15 bg-black/[0.02] hover:border-black/35 hover:bg-black/[0.03]"}`}
              >
                <div className="pointer-events-none absolute -right-12 -top-12 h-28 w-28 rounded-full bg-[radial-gradient(circle,#f0d7b4_0%,rgba(240,215,180,0)_72%)] opacity-70 transition duration-300 group-hover:scale-110" />
                <p className="text-sm font-semibold text-black">
                  Choose reference image
                </p>
                <p className="mt-1 text-xs leading-5 text-black/55">
                  Drop image here or click to browse. The backend uses this
                  photo to generate the facial embedding.
                </p>
                <input
                  key={`missing-image-${uploadKey}`}
                  type="file"
                  accept="image/*"
                  onChange={(event) =>
                    setMissingImage(event.target.files?.[0] ?? null)
                  }
                  className="mt-4 block w-full text-sm text-black/70 file:mr-3 file:rounded-full file:border-0 file:bg-black file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white"
                />
                <p className="mt-3 truncate text-xs text-black/55">
                  {missingImage?.name ?? "No file selected"}
                </p>

                {missingImage && (
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-black/55">
                      <span>Staging</span>
                      <span>{uploadProgress.missingImage}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full border border-black/10 bg-white">
                      <div
                        className="photo-progress h-full rounded-full bg-[linear-gradient(90deg,#111_0%,#333_35%,#0f0f0f_100%)] transition-all duration-300"
                        style={{ width: `${uploadProgress.missingImage}%` }}
                      />
                    </div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-black/45">
                      {loading
                        ? "Uploading bytes to backend"
                        : "Upload starts when analysis begins"}
                    </p>
                  </div>
                )}
              </label>

              <div className="rounded-2xl border border-black/10 bg-black/[0.015] p-3 text-xs leading-6 text-black/60">
                Detection quality improves when the face is centered and
                unobstructed.
              </div>
            </div>

            <div className="overflow-hidden rounded-[1.5rem] border border-black/10 bg-black/[0.02] reveal-delay-3">
              <div className="border-b border-black/10 px-4 py-3">
                <p className="text-sm font-semibold text-black">
                  Preview window
                </p>
                <p className="mt-1 text-xs text-black/50">
                  A live preview of the selected photo.
                </p>
              </div>
              <div className="relative aspect-[4/3] bg-white">
                {missingPreview ? (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={missingPreview}
                      alt="Missing person preview"
                      onLoad={() => setPreviewReady(true)}
                      className={`h-full w-full object-cover transition duration-500 ${previewReady ? "scale-100 opacity-100" : "scale-[1.02] opacity-0"}`}
                    />
                    <div className="pointer-events-none absolute inset-0 scan-overlay" />
                    <div className="pointer-events-none absolute inset-0 rounded-[1.2rem] ring-1 ring-black/10" />
                  </>
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-[linear-gradient(135deg,rgba(0,0,0,0.04),rgba(255,255,255,0.8))] text-sm text-black/45">
                    Photo preview will appear here.
                  </div>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:justify-center lg:col-span-2">
              <Link
                href="/"
                className="inline-flex items-center justify-center rounded-full border border-black/15 bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-black/[0.03]"
              >
                Back
              </Link>
              <button
                type="button"
                onClick={() => {
                  setStep(2);
                  router.push("/videos");
                }}
                disabled={!missingImage}
                className="inline-flex items-center justify-center rounded-full bg-black px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(0,0,0,0.18)] transition hover:-translate-y-[1px] hover:bg-black/90 disabled:cursor-not-allowed disabled:bg-black/20"
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
