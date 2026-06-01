import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Limpiador de Firmas — ADIPA",
  description: "Procesá firmas docentes y subilas directo a Monday",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
