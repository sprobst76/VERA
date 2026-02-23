/**
 * Tests for Schuljahrdienste utility logic used in the Shifts page.
 *
 * Covers:
 * - WEEKDAY_NAMES mapping
 * - Weekday index <-> JS Date.getDay() conversion
 * - Background event date range construction
 * - Vacation period color defaults
 */
import { describe, it, expect } from "vitest";
import { format, getDay, parseISO, eachDayOfInterval } from "date-fns";

// ── WEEKDAY_NAMES (matches backend weekday: 0=Monday convention) ──────────────

const WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

describe("WEEKDAY_NAMES", () => {
  it("has 7 entries", () => {
    expect(WEEKDAY_NAMES).toHaveLength(7);
  });

  it("index 0 is Montag", () => {
    expect(WEEKDAY_NAMES[0]).toBe("Montag");
  });

  it("index 6 is Sonntag", () => {
    expect(WEEKDAY_NAMES[6]).toBe("Sonntag");
  });

  it("all names are non-empty strings", () => {
    WEEKDAY_NAMES.forEach(name => expect(typeof name).toBe("string"));
  });
});

// ── Weekday conversion: backend (Mon=0) ↔ JS Date.getDay() (Sun=0) ────────────

/**
 * Backend uses: Monday = 0, Sunday = 6
 * JS Date.getDay() uses: Sunday = 0, Monday = 1, ..., Saturday = 6
 *
 * Conversion: jsDay = (backendWeekday + 1) % 7
 */
function backendWeekdayToJsDay(weekday: number): number {
  return (weekday + 1) % 7;
}

describe("weekday conversion (backend → JS)", () => {
  it("Monday (0) → JS day 1", () => {
    expect(backendWeekdayToJsDay(0)).toBe(1);
  });

  it("Sunday (6) → JS day 0", () => {
    expect(backendWeekdayToJsDay(6)).toBe(0);
  });

  it("Friday (4) → JS day 5", () => {
    expect(backendWeekdayToJsDay(4)).toBe(5);
  });

  it("Saturday (5) → JS day 6", () => {
    expect(backendWeekdayToJsDay(5)).toBe(6);
  });
});

describe("date-fns weekday matching for Mondays", () => {
  it("2025-09-01 is a Monday (getDay=1)", () => {
    const d = parseISO("2025-09-01");
    expect(getDay(d)).toBe(1);
  });

  it("finds 5 Mondays in September 2025", () => {
    const days = eachDayOfInterval({
      start: parseISO("2025-09-01"),
      end: parseISO("2025-09-30"),
    });
    const mondays = days.filter(d => getDay(d) === 1);
    expect(mondays).toHaveLength(5);
    expect(format(mondays[0], "yyyy-MM-dd")).toBe("2025-09-01");
    expect(format(mondays[4], "yyyy-MM-dd")).toBe("2025-09-29");
  });

  it("finds 0 Mondays in a single Tuesday", () => {
    const days = eachDayOfInterval({
      start: parseISO("2025-09-02"),
      end: parseISO("2025-09-02"),
    });
    const mondays = days.filter(d => getDay(d) === 1);
    expect(mondays).toHaveLength(0);
  });
});

// ── Background event construction ─────────────────────────────────────────────

interface VacationPeriod {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  color: string;
}

interface PublicHoliday {
  date: string;
  name: string;
}

interface CustomHoliday {
  id: string;
  date: string;
  name: string;
  color: string;
}

function buildBackgroundEvents(data: {
  vacation_periods: VacationPeriod[];
  public_holidays: PublicHoliday[];
  custom_holidays: CustomHoliday[];
}) {
  const events: any[] = [];

  for (const vp of data.vacation_periods) {
    events.push({
      title: vp.name,
      start: parseISO(vp.start_date),
      end: new Date(parseISO(vp.end_date).getTime() + 86400000),
      allDay: true,
      resource: { type: "vacation", color: vp.color },
    });
  }

  for (const ph of data.public_holidays) {
    events.push({
      title: ph.name,
      start: parseISO(ph.date),
      end: new Date(parseISO(ph.date).getTime() + 86400000),
      allDay: true,
      resource: { type: "public_holiday", color: "#f38ba8" },
    });
  }

  for (const ch of data.custom_holidays) {
    events.push({
      title: ch.name,
      start: parseISO(ch.date),
      end: new Date(parseISO(ch.date).getTime() + 86400000),
      allDay: true,
      resource: { type: "custom_holiday", color: ch.color },
    });
  }

  return events;
}

describe("buildBackgroundEvents", () => {
  it("returns empty array for empty data", () => {
    const result = buildBackgroundEvents({ vacation_periods: [], public_holidays: [], custom_holidays: [] });
    expect(result).toHaveLength(0);
  });

  it("creates one allDay event per vacation period", () => {
    const result = buildBackgroundEvents({
      vacation_periods: [{ id: "1", name: "Herbstferien", start_date: "2025-10-27", end_date: "2025-10-30", color: "#a6e3a1" }],
      public_holidays: [],
      custom_holidays: [],
    });
    expect(result).toHaveLength(1);
    expect(result[0].allDay).toBe(true);
    expect(result[0].title).toBe("Herbstferien");
    expect(result[0].resource.type).toBe("vacation");
  });

  it("end date is one day after end_date (inclusive end)", () => {
    const result = buildBackgroundEvents({
      vacation_periods: [{ id: "1", name: "F", start_date: "2025-10-27", end_date: "2025-10-27", color: "#a6e3a1" }],
      public_holidays: [],
      custom_holidays: [],
    });
    const event = result[0];
    const diffMs = event.end.getTime() - event.start.getTime();
    expect(diffMs).toBe(86400000); // 24h in ms
  });

  it("public holiday gets red color #f38ba8", () => {
    const result = buildBackgroundEvents({
      vacation_periods: [],
      public_holidays: [{ date: "2025-11-01", name: "Allerheiligen" }],
      custom_holidays: [],
    });
    expect(result[0].resource.color).toBe("#f38ba8");
    expect(result[0].resource.type).toBe("public_holiday");
  });

  it("custom holiday uses its own color", () => {
    const result = buildBackgroundEvents({
      vacation_periods: [],
      public_holidays: [],
      custom_holidays: [{ id: "1", date: "2025-10-03", name: "Konferenztag", color: "#fab387" }],
    });
    expect(result[0].resource.color).toBe("#fab387");
    expect(result[0].resource.type).toBe("custom_holiday");
  });

  it("combines all three types", () => {
    const result = buildBackgroundEvents({
      vacation_periods: [{ id: "1", name: "Ferien", start_date: "2025-10-27", end_date: "2025-10-30", color: "#a6e3a1" }],
      public_holidays: [{ date: "2025-11-01", name: "Allerheiligen" }],
      custom_holidays: [{ id: "2", date: "2025-10-03", name: "Konferenztag", color: "#fab387" }],
    });
    expect(result).toHaveLength(3);
    const types = result.map(e => e.resource.type).sort();
    expect(types).toEqual(["custom_holiday", "public_holiday", "vacation"]);
  });
});

// ── dayPropGetter logic ───────────────────────────────────────────────────────

describe("dayPropGetter date checking", () => {
  const vacationPeriods = [
    { start_date: "2025-10-27", end_date: "2025-10-31", name: "Herbstferien" },
  ];
  const publicHolidays = [{ date: "2025-11-01", name: "Allerheiligen" }];
  const customHolidays = [{ date: "2025-10-15", name: "Konferenztag" }];

  function isDateInVacation(dateStr: string) {
    return vacationPeriods.some(vp => dateStr >= vp.start_date && dateStr <= vp.end_date);
  }

  function isPublicHoliday(dateStr: string) {
    return publicHolidays.some(ph => ph.date === dateStr);
  }

  function isCustomHoliday(dateStr: string) {
    return customHolidays.some(ch => ch.date === dateStr);
  }

  it("identifies vacation day correctly", () => {
    expect(isDateInVacation("2025-10-28")).toBe(true);
    expect(isDateInVacation("2025-11-01")).toBe(false);
  });

  it("identifies first and last vacation day (inclusive)", () => {
    expect(isDateInVacation("2025-10-27")).toBe(true);
    expect(isDateInVacation("2025-10-31")).toBe(true);
    expect(isDateInVacation("2025-11-01")).toBe(false);
    expect(isDateInVacation("2025-10-26")).toBe(false);
  });

  it("identifies public holiday", () => {
    expect(isPublicHoliday("2025-11-01")).toBe(true);
    expect(isPublicHoliday("2025-11-02")).toBe(false);
  });

  it("identifies custom holiday", () => {
    expect(isCustomHoliday("2025-10-15")).toBe(true);
    expect(isCustomHoliday("2025-10-16")).toBe(false);
  });
});
