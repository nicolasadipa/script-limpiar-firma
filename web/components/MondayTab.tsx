"use client";

import { useEffect, useMemo, useState } from "react";
import type { Teacher, MondayProcessResponse } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; teachers: Teacher[] }
  | { kind: "error"; message: string };

type ActionState =
  | { kind: "idle" }
  | { kind: "processing"; uploading: boolean }
  | { kind: "done"; result: MondayProcessResponse; pngUrl: string }
  | { kind: "error"; message: string };

export default function MondayTab() {
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Teacher | null>(null);
  const [action, setAction] = useState<ActionState>({ kind: "idle" });

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setLoad({ kind: "loading" });
    try {
      const res = await fetch("/api/monday/teachers");
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail ?? text;
        } catch {}
        setLoad({ kind: "error", message: detail });
        return;
      }
      const teachers = (await res.json()) as Teacher[];
      setLoad({ kind: "ready", teachers });
    } catch (err) {
      setLoad({
        kind: "error",
        message: err instanceof Error ? err.message : "Error desconocido",
      });
    }
  }

  const filtered = useMemo(() => {
    if (load.kind !== "ready") return [];
    if (!query.trim()) return load.teachers.slice(0, 50);
    const q = query.toLowerCase();
    return load.teachers
      .filter((t) => t.name.toLowerCase().includes(q))
      .slice(0, 50);
  }, [load, query]);

  async function processTeacher(uploadBack: boolean) {
    if (!selected) return;
    setAction({ kind: "processing", uploading: uploadBack });
    try {
      const res = await fetch("/api/monday/process", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ item_id: selected.id, upload_back: uploadBack }),
      });

      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail ?? text;
        } catch {}
        setAction({ kind: "error", message: detail });
        return;
      }

      const result = (await res.json()) as MondayProcessResponse;
      const pngUrl = `/api/monday/result/${encodeURIComponent(selected.id)}?t=${Date.now()}`;
      setAction({ kind: "done", result, pngUrl });
    } catch (err) {
      setAction({
        kind: "error",
        message: err instanceof Error ? err.message : "Error desconocido",
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-adipa-ink mb-2">
          Buscar docente
        </label>
        <input
          type="text"
          placeholder="Ej: Rocío Troncoso"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
            setAction({ kind: "idle" });
          }}
          className="w-full rounded-lg border border-adipa-primary/30 bg-white px-4 py-2.5 text-adipa-ink outline-none focus:border-adipa-primary focus:ring-2 focus:ring-adipa-primary/20"
        />
      </div>

      {load.kind === "loading" && (
        <p className="text-sm text-adipa-ink/60">Cargando docentes desde Monday…</p>
      )}

      {load.kind === "error" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
          <p className="font-medium">No se pudo conectar con Monday</p>
          <p className="text-sm mt-1 opacity-80">{load.message}</p>
          <p className="text-sm mt-2 opacity-80">
            Verificá que <code className="rounded bg-red-100 px-1">MONDAY_API_TOKEN</code> y{" "}
            <code className="rounded bg-red-100 px-1">MONDAY_BOARD_ID</code> estén configurados
            en el backend.
          </p>
          <button onClick={() => void refresh()} className="mt-3 text-sm underline">
            Reintentar
          </button>
        </div>
      )}

      {load.kind === "ready" && (
        <div className="rounded-xl border border-adipa-primary/20 bg-white max-h-64 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-sm text-adipa-ink/60">Sin resultados</p>
          ) : (
            <ul className="divide-y divide-adipa-bg">
              {filtered.map((t) => (
                <li key={t.id}>
                  <button
                    onClick={() => {
                      setSelected(t);
                      setAction({ kind: "idle" });
                    }}
                    className={`w-full text-left px-4 py-2.5 text-sm transition ${
                      selected?.id === t.id
                        ? "bg-adipa-light-purple text-adipa-ink"
                        : "hover:bg-adipa-bg text-adipa-ink"
                    }`}
                  >
                    {t.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {selected && (
        <div className="rounded-2xl bg-white p-5 shadow-sm space-y-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-adipa-ink/50">Seleccionado</p>
            <p className="text-lg font-medium text-adipa-ink">{selected.name}</p>
            <p className="text-xs text-adipa-ink/40 mt-0.5">Item ID: {selected.id}</p>
          </div>

          {action.kind === "idle" && (
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                onClick={() => void processTeacher(false)}
                className="rounded-lg border border-adipa-primary/30 bg-white px-5 py-2.5 text-sm font-medium text-adipa-ink hover:bg-adipa-bg"
              >
                Procesar (solo preview)
              </button>
              <button
                onClick={() => void processTeacher(true)}
                className="rounded-lg bg-adipa-primary px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
              >
                Procesar y subir a Monday
              </button>
            </div>
          )}

          {action.kind === "processing" && (
            <p className="text-sm text-adipa-ink/70">
              <Spinner />
              {action.uploading
                ? "Procesando y subiendo a Monday…"
                : "Procesando firma…"}
            </p>
          )}

          {action.kind === "error" && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-900 text-sm">
              <p className="font-medium">Error</p>
              <p className="opacity-80 mt-1">{action.message}</p>
              <button
                onClick={() => setAction({ kind: "idle" })}
                className="mt-2 underline"
              >
                Reintentar
              </button>
            </div>
          )}

          {action.kind === "done" && (
            <div className="space-y-3">
              <div className="checkerboard rounded-xl border border-adipa-bg p-6">
                <img
                  src={action.pngUrl}
                  alt="Firma procesada"
                  className="mx-auto max-h-64 object-contain"
                />
              </div>

              {action.result.uploaded_to_monday ? (
                <div className="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-900">
                  PNG subido a Monday en la columna Firma
                </div>
              ) : (
                <div className="rounded-lg bg-adipa-light-purple border border-adipa-primary/20 px-3 py-2 text-sm text-adipa-ink">
                  Solo preview (no se subió a Monday)
                </div>
              )}

              <div className="flex flex-wrap gap-3 pt-1">
                <a
                  href={action.pngUrl}
                  download={action.result.output_filename}
                  className="rounded-lg border border-adipa-primary/30 bg-white px-5 py-2.5 text-sm font-medium text-adipa-ink hover:bg-adipa-bg"
                >
                  Descargar PNG
                </a>
                {!action.result.uploaded_to_monday && (
                  <button
                    onClick={() => void processTeacher(true)}
                    className="rounded-lg bg-adipa-primary px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
                  >
                    Subir esta versión a Monday
                  </button>
                )}
                <button
                  onClick={() => {
                    setAction({ kind: "idle" });
                    setSelected(null);
                  }}
                  className="rounded-lg px-5 py-2.5 text-sm text-adipa-ink/70 hover:underline"
                >
                  Otro docente
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent align-[-2px] mr-2" />
  );
}
