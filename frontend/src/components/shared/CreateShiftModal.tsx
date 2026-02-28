"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { shiftsApi } from "@/lib/api";
import { addDays } from "date-fns";
import { X, CalendarRange } from "lucide-react";
import toast from "react-hot-toast";
import { TimeInput } from "@/components/shared/TimeInput";

const WEEKDAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function countBulkShifts(weekdays: number[], from: string, to: string): number {
  if (!from || !to || weekdays.length === 0) return 0;
  let count = 0;
  let d = new Date(from);
  const end = new Date(to);
  while (d <= end) {
    const wd = (d.getDay() + 6) % 7; // convert Sun=0 to Mo=0
    if (weekdays.includes(wd)) count++;
    d = addDays(d, 1);
  }
  return count;
}

type Tab = "single" | "bulk";

interface Props {
  templates: any[];
  employees: any[];
  defaultDate?: string;
  onClose: () => void;
  onCreated: () => void;
}

export function CreateShiftModal({ templates, employees, defaultDate, onClose, onCreated }: Props) {
  const today = defaultDate ?? new Date().toISOString().slice(0, 10);
  const [tab, setTab] = useState<Tab>("single");

  // ── Single form ───────────────────────────────────────────────────────────
  const [sDate,     setSDate]     = useState(today);
  const [sTplId,    setSTplId]    = useState(templates[0]?.id ?? "");
  const [sEmpId,    setSEmpId]    = useState("");
  const [sStart,    setSStart]    = useState("");
  const [sEnd,      setSEnd]      = useState("");
  const [sBreak,    setSBreak]    = useState(0);
  const [sLocation, setSLocation] = useState("");
  const [sNotes,    setSNotes]    = useState("");

  const selectedSingleTpl = templates.find((t: any) => t.id === sTplId);

  useEffect(() => {
    if (selectedSingleTpl) {
      setSStart(selectedSingleTpl.start_time?.slice(0, 5) ?? "");
      setSEnd(selectedSingleTpl.end_time?.slice(0, 5) ?? "");
      setSBreak(selectedSingleTpl.break_minutes ?? 0);
      setSLocation(selectedSingleTpl.location ?? "");
    }
  }, [sTplId]);

  // ── Bulk form ─────────────────────────────────────────────────────────────
  const [bTplId,  setBTplId]  = useState(templates[0]?.id ?? "");
  const [bFrom,   setBFrom]   = useState(today);
  const [bTo,     setBTo]     = useState(today);
  const [bEmpId,  setBEmpId]  = useState("");
  const [bStart,  setBStart]  = useState("");   // override – empty = use template
  const [bEnd,    setBEnd]    = useState("");

  const selectedBulkTpl = templates.find((t: any) => t.id === bTplId);
  const bulkCount = selectedBulkTpl ? countBulkShifts(selectedBulkTpl.weekdays, bFrom, bTo) : 0;

  // ── Mutations ─────────────────────────────────────────────────────────────
  const createSingle = useMutation({
    mutationFn: () =>
      shiftsApi.create({
        template_id: sTplId || undefined,
        employee_id: sEmpId || undefined,
        date: sDate,
        start_time: sStart,
        end_time: sEnd,
        break_minutes: sBreak,
        location: sLocation || undefined,
        notes: sNotes || undefined,
      }),
    onSuccess: () => { toast.success("Dienst angelegt"); onCreated(); },
    onError:   () => toast.error("Fehler beim Anlegen"),
  });

  const createBulk = useMutation({
    mutationFn: () =>
      shiftsApi.bulk({
        template_id: bTplId,
        from_date: bFrom,
        to_date: bTo,
        employee_id: bEmpId || undefined,
        start_time_override: bStart || undefined,
        end_time_override:   bEnd   || undefined,
      }),
    onSuccess: (res) => {
      toast.success(`${res.data?.length ?? bulkCount} Dienste angelegt`);
      onCreated();
    },
    onError: () => toast.error("Fehler beim Anlegen"),
  });

  // ── Styles ────────────────────────────────────────────────────────────────
  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const labelCls = "block text-xs font-medium text-muted-foreground mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-md max-h-[90dvh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 shrink-0">
          <h2 className="text-lg font-semibold text-foreground">Dienst anlegen</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground">
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-5 mb-3 shrink-0">
          {(["single", "bulk"] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? "bg-primary text-primary-foreground" : "bg-accent/50 text-muted-foreground hover:bg-accent"
              }`}>
              {t === "single" ? "Einzeldienst" : "Bulk anlegen"}
            </button>
          ))}
        </div>

        <div className="overflow-y-auto flex-1 px-5 pb-5 space-y-3">

          {/* ── Single tab ── */}
          {tab === "single" && (<>
            <div>
              <label className={labelCls}>Dienst-Template</label>
              <select className={inputCls} value={sTplId} onChange={e => setSTplId(e.target.value)}>
                <option value="">– Kein Template –</option>
                {templates.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>

            <div>
              <label className={labelCls}>Datum *</label>
              <input type="date" className={inputCls} value={sDate} onChange={e => setSDate(e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Von *</label>
                <TimeInput value={sStart} onChange={setSStart} />
              </div>
              <div>
                <label className={labelCls}>Bis *</label>
                <TimeInput value={sEnd} onChange={setSEnd} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Pause (Min.)</label>
                <input type="number" min={0} step={5} className={inputCls} value={sBreak}
                  onChange={e => setSBreak(Number(e.target.value))} />
              </div>
              <div>
                <label className={labelCls}>Ort</label>
                <input type="text" className={inputCls} value={sLocation}
                  onChange={e => setSLocation(e.target.value)} placeholder="optional" />
              </div>
            </div>

            <div>
              <label className={labelCls}>Mitarbeiter</label>
              <select className={inputCls} value={sEmpId} onChange={e => setSEmpId(e.target.value)}>
                <option value="">– Offen / nicht zugewiesen –</option>
                {employees.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
              </select>
            </div>

            <div>
              <label className={labelCls}>Notiz</label>
              <textarea className={`${inputCls} resize-none`} rows={2} value={sNotes}
                onChange={e => setSNotes(e.target.value)} placeholder="optional" />
            </div>

            <button
              onClick={() => createSingle.mutate()}
              disabled={!sDate || !sStart || !sEnd || createSingle.isPending}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {createSingle.isPending ? "Wird gespeichert…" : "Dienst anlegen"}
            </button>
          </>)}

          {/* ── Bulk tab ── */}
          {tab === "bulk" && (<>
            <div>
              <label className={labelCls}>Dienst-Template *</label>
              <select className={inputCls} value={bTplId} onChange={e => { setBTplId(e.target.value); setBStart(""); setBEnd(""); }}>
                <option value="">– Template wählen –</option>
                {templates.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {selectedBulkTpl && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Wochentage: {selectedBulkTpl.weekdays.map((d: number) => WEEKDAY_SHORT[d]).join(", ")}
                  {" · "}
                  {selectedBulkTpl.start_time?.slice(0, 5)} – {selectedBulkTpl.end_time?.slice(0, 5)} Uhr
                  (Standard)
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Von</label>
                <input type="date" className={inputCls} value={bFrom}
                  onChange={e => { setBFrom(e.target.value); if (e.target.value > bTo) setBTo(e.target.value); }} />
              </div>
              <div>
                <label className={labelCls}>Bis</label>
                <input type="date" className={inputCls} value={bTo} min={bFrom}
                  onChange={e => setBTo(e.target.value)} />
              </div>
            </div>

            {/* Optional time override */}
            <div>
              <label className={labelCls}>Abweichende Uhrzeiten <span className="font-normal">(optional – überschreibt Template)</span></label>
              <div className="grid grid-cols-2 gap-3">
                <TimeInput value={bStart} onChange={setBStart} />
                <TimeInput value={bEnd} onChange={setBEnd} />
              </div>
              {(bStart || bEnd) && (
                <p className="mt-1 text-xs" style={{ color: "rgb(var(--ctp-peach))" }}>
                  Überschreibt Template-Zeiten für alle angelegten Dienste
                </p>
              )}
            </div>

            <div>
              <label className={labelCls}>Mitarbeiter</label>
              <select className={inputCls} value={bEmpId} onChange={e => setBEmpId(e.target.value)}>
                <option value="">– Offen / nicht zugewiesen –</option>
                {employees.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
              </select>
            </div>

            {bTplId && bFrom && bTo && (
              <div className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm"
                style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.10)", color: "rgb(var(--ctp-blue))" }}>
                <CalendarRange size={15} className="shrink-0" />
                {bulkCount > 0
                  ? `${bulkCount} Dienste werden angelegt`
                  : "Keine passenden Tage im gewählten Zeitraum"}
              </div>
            )}

            <button
              onClick={() => createBulk.mutate()}
              disabled={!bTplId || !bFrom || !bTo || bulkCount === 0 || createBulk.isPending}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {createBulk.isPending ? "Wird angelegt…"
                : bulkCount > 0 ? `${bulkCount} Dienste anlegen`
                : "Dienste anlegen"}
            </button>
          </>)}
        </div>
      </div>
    </div>
  );
}
