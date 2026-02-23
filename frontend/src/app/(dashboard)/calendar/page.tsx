"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, dateFnsLocalizer, View } from "react-big-calendar";
import { format, parse, startOfWeek, getDay, startOfMonth, endOfMonth, addMonths, subMonths } from "date-fns";
import { de } from "date-fns/locale";
import { shiftsApi, templatesApi, employeesApi } from "@/lib/api";
import { ChevronLeft, ChevronRight, AlertCircle, Plus } from "lucide-react";
import { useAuthStore } from "@/store/auth";
import { CreateShiftModal } from "@/components/shared/CreateShiftModal";
import "react-big-calendar/lib/css/react-big-calendar.css";

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales: { de },
});

const VIEWS: { key: View; label: string }[] = [
  { key: "month", label: "Monat" },
  { key: "week",  label: "Woche" },
  { key: "day",   label: "Tag" },
];

const STATUS_OPACITY: Record<string, string> = {
  completed:          "opacity-60",
  cancelled:          "opacity-30 line-through",
  cancelled_absence:  "opacity-30 line-through",
  planned:            "opacity-100",
  confirmed:          "opacity-100",
};

export default function CalendarPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();

  const [view, setView] = useState<View>("week");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedShift, setSelectedShift] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createDate, setCreateDate] = useState("");

  // Datumsbereich für API-Anfrage
  const rangeStart = format(subMonths(startOfMonth(currentDate), 0), "yyyy-MM-dd");
  const rangeEnd   = format(endOfMonth(addMonths(currentDate, 0)), "yyyy-MM-dd");

  const { data: shifts = [] } = useQuery({
    queryKey: ["shifts", rangeStart, rangeEnd],
    queryFn: () => shiftsApi.list({ from_date: rangeStart, to_date: rangeEnd }).then(r => r.data),
  });

  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then(r => r.data),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then(r => r.data),
  });

  // Lookup-Maps
  const templateMap = useMemo(() =>
    Object.fromEntries(templates.map((t: any) => [t.id, t])), [templates]);
  const employeeMap = useMemo(() =>
    Object.fromEntries(employees.map((e: any) => [e.id, e])), [employees]);

  // Shifts → Calendar Events
  const events = useMemo(() => shifts.map((s: any) => {
    const tpl = templateMap[s.template_id];
    const emp = employeeMap[s.employee_id];
    const empName = emp ? `${emp.first_name} ${emp.last_name[0]}.` : "Offen";
    return {
      id: s.id,
      title: tpl ? `${tpl.name} – ${empName}` : empName,
      start: new Date(`${s.date}T${s.start_time}`),
      end:   new Date(`${s.date}T${s.end_time}`),
      resource: { shift: s, template: tpl, employee: emp },
    };
  }), [shifts, templateMap, employeeMap]);

  // Farbe je Template, grau für offene Dienste
  const eventPropGetter = useCallback((event: any) => {
    const { shift, template } = event.resource;
    const isOpen = !shift.employee_id;
    const color = isOpen ? "#ef4444" : (template?.color ?? "#1E3A5F");
    const isCancelled = shift.status.startsWith("cancelled");
    return {
      style: {
        backgroundColor: color,
        borderColor: color,
        opacity: isCancelled ? 0.35 : 1,
        textDecoration: isCancelled ? "line-through" : "none",
        fontSize: "0.75rem",
        border: shift.notes ? `2px dashed ${color}` : `1px solid ${color}`,
      },
    };
  }, []);

  const handleNavigate = (dir: "prev" | "next" | "today") => {
    if (dir === "today") { setCurrentDate(new Date()); return; }
    const delta = view === "month" ? 1 : view === "week" ? 7 : 1;
    setCurrentDate(prev => {
      const d = new Date(prev);
      if (view === "month") {
        return dir === "next" ? addMonths(d, 1) : subMonths(d, 1);
      }
      d.setDate(d.getDate() + (dir === "next" ? delta : -delta));
      return d;
    });
  };

  // Legende
  const legend = templates.map((t: any) => ({ name: t.name, color: t.color }));

  return (
    <div className="space-y-4 h-full">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold flex-1">Kalender</h1>
        {isPrivileged && (
          <button onClick={() => { setCreateDate(format(currentDate, "yyyy-MM-dd")); setShowCreate(true); }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
            <Plus size={16} />
            <span className="hidden sm:inline">Neuer Dienst</span>
          </button>
        )}

        {/* Navigation */}
        <div className="flex items-center gap-1 bg-card rounded-lg border border-border p-1">
          <button onClick={() => handleNavigate("prev")} className="p-2.5 hover:bg-accent rounded">
            <ChevronLeft size={16} />
          </button>
          <button onClick={() => handleNavigate("today")} className="px-3 py-2 text-sm hover:bg-accent rounded font-medium">
            Heute
          </button>
          <button onClick={() => handleNavigate("next")} className="p-2.5 hover:bg-accent rounded">
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Ansicht */}
        <div className="flex gap-1 bg-card rounded-lg border border-border p-1">
          {VIEWS.map(v => (
            <button key={v.key} onClick={() => setView(v.key)}
              className={`px-3 py-2 text-sm rounded font-medium transition-colors ${
                view === v.key
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent"
              }`}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Legende */}
      <div className="flex flex-wrap gap-2 text-xs">
        {legend.map((l: any) => (
          <span key={l.name} className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
            {l.name}
          </span>
        ))}
        <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "rgb(var(--ctp-red))" }} />
          Offener Dienst
        </span>
      </div>

      {/* Kalender */}
      <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ height: "calc(100svh - 220px)", minHeight: 380 }}>
        <Calendar
          localizer={localizer}
          events={events}
          view={view}
          date={currentDate}
          onNavigate={setCurrentDate}
          onView={setView}
          eventPropGetter={eventPropGetter}
          onSelectEvent={(e: any) => setSelectedShift(e.resource)}
          onSelectSlot={isPrivileged ? (slot: any) => {
            setCreateDate(format(slot.start, "yyyy-MM-dd"));
            setShowCreate(true);
          } : undefined}
          selectable={isPrivileged}
          culture="de"
          toolbar={false}
          messages={{
            noEventsInRange: "Keine Dienste in diesem Zeitraum",
            showMore: (n) => `+${n} weitere`,
          }}
        />
      </div>

      {/* Detail-Overlay */}
      {/* Create Shift Modal */}
      {showCreate && (
        <CreateShiftModal
          templates={templates as any[]}
          employees={employees as any[]}
          defaultDate={createDate}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ["shifts"] }); }}
        />
      )}

      {selectedShift && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelectedShift(null)}>
          <div className="bg-card rounded-xl shadow-xl p-5 max-w-sm w-full border border-border"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-semibold text-lg text-foreground">
                  {selectedShift.template?.name ?? "Dienst"}
                </div>
                <div className="text-sm text-muted-foreground">
                  {selectedShift.shift.date} · {selectedShift.shift.start_time?.slice(0,5)} – {selectedShift.shift.end_time?.slice(0,5)} Uhr
                </div>
              </div>
              <span className="w-3 h-3 rounded-full mt-1.5 shrink-0"
                style={{ backgroundColor: selectedShift.template?.color ?? "rgb(var(--ctp-overlay1))" }} />
            </div>

            <div className="space-y-1.5 text-sm">
              <Row label="Mitarbeiter"
                value={selectedShift.employee
                  ? `${selectedShift.employee.first_name} ${selectedShift.employee.last_name}`
                  : <span className="text-ctp-red font-medium flex items-center gap-1"><AlertCircle size={13}/>Offen</span>} />
              <Row label="Ort" value={selectedShift.shift.location ?? "–"} />
              <Row label="Pause" value={selectedShift.shift.break_minutes ? `${selectedShift.shift.break_minutes} Min` : "keine"} />
              <Row label="Status" value={selectedShift.shift.status} />
              {selectedShift.shift.notes && (
                <Row label="Notiz" value={<span className="text-ctp-yellow">{selectedShift.shift.notes}</span>} />
              )}
              {selectedShift.shift.is_sunday && <Row label="" value={<span className="text-ctp-peach">Sonntagszuschlag +50%</span>} />}
              {selectedShift.shift.is_weekend && !selectedShift.shift.is_sunday && <Row label="" value={<span className="text-ctp-yellow">Samstagsz. +25%</span>} />}
            </div>

            <button onClick={() => setSelectedShift(null)}
              className="mt-4 w-full text-sm text-center py-2 rounded-lg bg-accent hover:bg-accent/80 text-foreground transition-colors">
              Schließen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      {label && <span className="text-muted-foreground w-24 shrink-0">{label}</span>}
      <span className="text-foreground">{value}</span>
    </div>
  );
}
