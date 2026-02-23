import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date, pattern = "dd.MM.yyyy"): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, pattern, { locale: de });
}

export function formatTime(time: string): string {
  return time.substring(0, 5); // "HH:MM:SS" -> "HH:MM"
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(amount);
}

export function formatHours(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  minijob: "Minijob",
  part_time: "Teilzeit",
  full_time: "Vollzeit",
};

export const SHIFT_STATUS_LABELS: Record<string, string> = {
  planned: "Geplant",
  confirmed: "Bestätigt",
  completed: "Abgeschlossen",
  cancelled: "Abgesagt",
  cancelled_absence: "Abgesagt (Abwesenheit)",
};

export const SHIFT_STATUS_COLORS: Record<string, string> = {
  planned: "bg-blue-100 text-blue-800",
  confirmed: "bg-green-100 text-green-800",
  completed: "bg-gray-100 text-gray-800",
  cancelled: "bg-red-100 text-red-800",
  cancelled_absence: "bg-orange-100 text-orange-800",
};

export const ABSENCE_TYPE_LABELS: Record<string, string> = {
  vacation: "Urlaub",
  sick: "Krank",
  school_holiday: "Schulferien",
  other: "Sonstiges",
};
