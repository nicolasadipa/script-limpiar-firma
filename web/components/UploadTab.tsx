"use client";

import { useCallback, useRef, useState } from "react";

const ACCEPTED = ".pdf,.jpg,.jpeg,.png,.docx,.doc";

type State =
  | { kind: "idle" }
  | { kind: "processing"; fileName: string }
  | { kind: "done"; fileName: string; pngUrl: string }
  | { kind: "error"; message: string };

export default function UploadTab() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const processFile = useCallback(async (file: File) => {
    setState({ kind: "processing", fileName: file.name });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/process", { method: "POST", body: formData });

      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail ?? text;
        } catch {}
        setState({ kind: "error", message: detail });
        return;
      }

      const blob = await res.blob();
      const pngUrl = URL.createObjectURL(blob);
      setState({ kind: "done", fileName: file.name, pngUrl });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Error desconocido",
      });
    }
  }, []);

  const onPick = () => inputRef.current?.click();

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={onPick}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition ${
          dragOver
            ? "border-adipa-primary bg-adipa-light-purple"
            : "border-adipa-primary/40 bg-white hover:border-adipa-primary hover:bg-adipa-bg"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          onChange={onChange}
          className="hidden"
        />
        <p className="text-lg font-medium text-adipa-ink">
          Arrastrá un archivo o hacé click para elegir
        </p>
        <p className="mt-2 text-sm text-adipa-ink/60">
          PDF, JPG, PNG, DOCX o DOC
        </p>
      </div>

      {state.kind === "processing" && (
        <StatusCard tone="info">
          <Spinner /> Procesando <strong>{state.fileName}</strong>…
        </StatusCard>
      )}

      {state.kind === "error" && (
        <StatusCard tone="error">
          <p className="font-medium">No se pudo procesar</p>
          <p className="text-sm opacity-80 mt-1">{state.message}</p>
          <button
            onClick={() => setState({ kind: "idle" })}
            className="mt-3 text-sm underline"
          >
            Probar otro archivo
          </button>
        </StatusCard>
      )}

      {state.kind === "done" && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-sm">
            <div className="checkerboard rounded-xl border border-adipa-bg p-6">
              <img
                src={state.pngUrl}
                alt="Firma procesada"
                className="mx-auto max-h-72 object-contain"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <a
              href={state.pngUrl}
              download={state.fileName.replace(/\.[^.]+$/, "") + "_clean.png"}
              className="rounded-lg bg-adipa-primary px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
            >
              Descargar PNG
            </a>
            <button
              onClick={() => {
                URL.revokeObjectURL(state.pngUrl);
                setState({ kind: "idle" });
              }}
              className="rounded-lg border border-adipa-primary/30 bg-white px-5 py-2.5 text-sm font-medium text-adipa-ink hover:bg-adipa-bg"
            >
              Procesar otra
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusCard({
  tone,
  children,
}: {
  tone: "info" | "error";
  children: React.ReactNode;
}) {
  const palette =
    tone === "error"
      ? "bg-red-50 text-red-900 border-red-200"
      : "bg-adipa-light-purple text-adipa-ink border-adipa-primary/20";
  return (
    <div className={`rounded-xl border p-4 ${palette}`}>{children}</div>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent align-[-2px] mr-2" />
  );
}
