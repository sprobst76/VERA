import { describe, it, expect } from "vitest";
import { buildSkipSet, buildRecurringEventsForShift, buildAllRecurringEvents } from "@/lib/recurringEventUtils";
import type { RecurringShift, VacationData } from "@/lib/recurringEventUtils";

// ── Hilfsdaten ────────────────────────────────────────────────────────────────

/** Montag bis Freitag, KW15 2026 (06.04.–10.04. – Osterferien!) */
const EASTER_WEEK_START = new Date("2026-04-06T00:00:00");
const EASTER_WEEK_END   = new Date("2026-04-10T00:00:00");

/** Normwoche KW14 2026 (30.03.–03.04. – auch noch Osterferien) */
/** Normwoche KW16 2026 (13.04.–17.04. – nach Osterferien) */
const NORMAL_WEEK_START = new Date("2026-04-13T00:00:00");
const NORMAL_WEEK_END   = new Date("2026-04-17T00:00:00");

const MONTAG_RS: RecurringShift = {
  id: "rs-1",
  weekday: 0,          // Montag
  start_time: "07:30:00",
  end_time: "13:30:00",
  label: "Schule",
  valid_from: "2026-01-01",
  valid_until: "2026-07-31",
  skip_public_holidays: true,
};

const VACATION_DATA: VacationData = {
  vacation_periods: [
    { start_date: "2026-03-30", end_date: "2026-04-11" }, // Osterferien
  ],
  public_holidays: [
    { date: "2026-04-03" }, // Karfreitag
    { date: "2026-05-01" }, // Tag der Arbeit
  ],
};

const EMPTY_SHIFT_DATES = new Set<string>();

// ── buildSkipSet ──────────────────────────────────────────────────────────────

describe("buildSkipSet", () => {
  it("enthält alle Ferientage", () => {
    const skip = buildSkipSet(VACATION_DATA, false);
    expect(skip.has("2026-03-30")).toBe(true);
    expect(skip.has("2026-04-06")).toBe(true);
    expect(skip.has("2026-04-11")).toBe(true);
    expect(skip.has("2026-04-12")).toBe(false); // Tag nach Ferien
  });

  it("enthält Feiertage wenn skipHolidays=true", () => {
    const skip = buildSkipSet(VACATION_DATA, true);
    expect(skip.has("2026-04-03")).toBe(true);
    expect(skip.has("2026-05-01")).toBe(true);
  });

  it("enthält keine Feiertage wenn skipHolidays=false", () => {
    const skip = buildSkipSet(VACATION_DATA, false);
    // 01.05. ist Feiertag aber KEIN Ferientag → soll nicht im Set sein
    expect(skip.has("2026-05-01")).toBe(false);
  });

  it("gibt leeres Set für undefined vacationData zurück", () => {
    const skip = buildSkipSet(undefined, true);
    expect(skip.size).toBe(0);
  });
});

// ── buildRecurringEventsForShift ──────────────────────────────────────────────

describe("buildRecurringEventsForShift", () => {
  it("zeigt Montags-Regeltermin in normaler Woche", () => {
    const events = buildRecurringEventsForShift(
      MONTAG_RS, NORMAL_WEEK_START, NORMAL_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events).toHaveLength(1);
    expect(events[0].id).toContain("2026-04-13"); // Montag der Normalwoche
    expect(events[0].title).toBe("↻ Schule");
  });

  it("zeigt KEINEN Regeltermin in der Osterferienwoche", () => {
    const events = buildRecurringEventsForShift(
      MONTAG_RS, EASTER_WEEK_START, EASTER_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events).toHaveLength(0);
  });

  it("zeigt KEINEN Regeltermin wenn echter Dienst an dem Tag existiert", () => {
    const shiftDates = new Set(["2026-04-13"]); // Montag der Normalwoche belegt
    const events = buildRecurringEventsForShift(
      MONTAG_RS, NORMAL_WEEK_START, NORMAL_WEEK_END,
      shiftDates, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events).toHaveLength(0);
  });

  it("zeigt KEINEN Regeltermin an Feiertagen (skip_public_holidays=true)", () => {
    const freitagRS: RecurringShift = {
      ...MONTAG_RS,
      id: "rs-fr",
      weekday: 4, // Freitag
    };
    // Karfreitag 2026-04-03 ist ein Freitag, aber in den Osterferien
    // Nehmen wir Maifeiertag (01.05.2026 = Freitag)
    const maiwoche_start = new Date("2026-04-27T00:00:00");
    const maiwoche_end   = new Date("2026-05-01T00:00:00");
    const events = buildRecurringEventsForShift(
      freitagRS, maiwoche_start, maiwoche_end,
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    // 01.05 ist Feiertag → kein Event
    const dates = events.map(e => e.id);
    expect(dates.some(d => d.includes("2026-05-01"))).toBe(false);
  });

  it("respektiert valid_from: kein Event vor Gültigkeit", () => {
    const rs: RecurringShift = { ...MONTAG_RS, valid_from: "2026-04-20" };
    const events = buildRecurringEventsForShift(
      rs, NORMAL_WEEK_START, NORMAL_WEEK_END, // 13.04.–17.04. → vor valid_from
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events).toHaveLength(0);
  });

  it("respektiert valid_until: kein Event nach Ablauf", () => {
    const rs: RecurringShift = { ...MONTAG_RS, valid_until: "2026-04-10" };
    const events = buildRecurringEventsForShift(
      rs, NORMAL_WEEK_START, NORMAL_WEEK_END, // 13.04.–17.04. → nach valid_until
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events).toHaveLength(0);
  });

  it("Event hat korrekte Start-/Endzeit", () => {
    const events = buildRecurringEventsForShift(
      MONTAG_RS, NORMAL_WEEK_START, NORMAL_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
      "#1E3A5F", "Schule", null,
    );
    expect(events[0].start.getHours()).toBe(7);
    expect(events[0].start.getMinutes()).toBe(30);
    expect(events[0].end.getHours()).toBe(13);
    expect(events[0].end.getMinutes()).toBe(30);
  });
});

// ── buildAllRecurringEvents ───────────────────────────────────────────────────

describe("buildAllRecurringEvents", () => {
  const ALL_WEEKDAYS: RecurringShift[] = [0, 1, 2, 3, 4].map(wd => ({
    ...MONTAG_RS,
    id: `rs-${wd}`,
    weekday: wd,
  }));

  it("gibt 5 Events für Mo–Fr in einer Normalwoche zurück", () => {
    const events = buildAllRecurringEvents(
      ALL_WEEKDAYS, {},
      NORMAL_WEEK_START, NORMAL_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
    );
    expect(events).toHaveLength(5);
  });

  it("gibt 0 Events für Mo–Fr in der Osterferienwoche zurück", () => {
    const events = buildAllRecurringEvents(
      ALL_WEEKDAYS, {},
      EASTER_WEEK_START, EASTER_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
    );
    expect(events).toHaveLength(0);
  });

  it("überspringt Tage mit echten Diensten", () => {
    const shiftDates = new Set(["2026-04-13", "2026-04-15"]); // Mo + Mi belegt
    const events = buildAllRecurringEvents(
      ALL_WEEKDAYS, {},
      NORMAL_WEEK_START, NORMAL_WEEK_END,
      shiftDates, VACATION_DATA,
    );
    expect(events).toHaveLength(3); // Di, Do, Fr
  });

  it("verwendet Templatefarbe wenn vorhanden", () => {
    const rs: RecurringShift = { ...MONTAG_RS, template_id: "tpl-1" };
    const templateMap = { "tpl-1": { name: "Schulbegleitung", color: "#ff0000" } };
    const events = buildAllRecurringEvents(
      [rs], templateMap,
      NORMAL_WEEK_START, NORMAL_WEEK_END,
      EMPTY_SHIFT_DATES, VACATION_DATA,
    );
    expect(events[0].resource.color).toBe("#ff0000");
  });
});
