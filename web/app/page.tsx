"use client";

import { useState } from "react";
import UploadTab from "@/components/UploadTab";
import MondayTab from "@/components/MondayTab";

type Tab = "upload" | "monday";

export default function Page() {
  const [tab, setTab] = useState<Tab>("upload");

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold text-adipa-ink">
          Limpiador de firmas
        </h1>
        <p className="mt-1 text-adipa-ink/60">
          Procesá firmas docentes desde un archivo o directo desde Monday.
        </p>
      </header>

      <nav className="mb-6 flex gap-1 rounded-xl bg-white p-1 shadow-sm w-fit">
        <TabButton active={tab === "upload"} onClick={() => setTab("upload")}>
          Subir archivo
        </TabButton>
        <TabButton active={tab === "monday"} onClick={() => setTab("monday")}>
          Desde Monday
        </TabButton>
      </nav>

      {tab === "upload" ? <UploadTab /> : <MondayTab />}

      <footer className="mt-16 text-xs text-adipa-ink/40">
        ADIPA · Pipeline OpenCV con detección automática de color de tinta
      </footer>
    </main>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
        active
          ? "bg-adipa-primary text-white"
          : "text-adipa-ink/70 hover:bg-adipa-bg"
      }`}
    >
      {children}
    </button>
  );
}
