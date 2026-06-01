/**
 * Helper para llamar al backend Python.
 * En servidor (route handlers) usa API_BASE_URL directo.
 * En cliente usa /api/* (proxy de Next.js).
 */

export const SERVER_API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export type Teacher = {
  id: string;
  name: string;
};

export type MondayProcessResponse = {
  item_id: string;
  teacher_name: string;
  output_filename: string;
  uploaded_to_monday: boolean;
};
