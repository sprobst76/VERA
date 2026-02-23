/**
 * Tests for the Schuljahrdienste API module (src/lib/api.ts)
 *
 * Verifies that each API function calls the correct HTTP method + endpoint
 * with the expected payload / query parameters.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// vi.hoisted ensures these are available when vi.mock() factory runs (which is hoisted)
const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet:  vi.fn().mockResolvedValue({ data: {} }),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
  mockPut:  vi.fn().mockResolvedValue({ data: {} }),
  mockDel:  vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({
      get:  mockGet,
      post: mockPost,
      put:  mockPut,
      delete: mockDel,
      interceptors: {
        request:  { use: vi.fn() },
        response: { use: vi.fn() },
      },
    }),
  },
}));

// Import AFTER mock
import { holidayProfilesApi, recurringShiftsApi, calendarDataApi } from "@/lib/api";

beforeEach(() => {
  vi.clearAllMocks();
});

// ── holidayProfilesApi ────────────────────────────────────────────────────────

describe("holidayProfilesApi", () => {
  it("list() → GET /holiday-profiles", () => {
    holidayProfilesApi.list();
    expect(mockGet).toHaveBeenCalledWith("/holiday-profiles");
  });

  it("create() → POST /holiday-profiles with body", () => {
    const body = { name: "BW 2025/26", state: "BW", preset_bw: true };
    holidayProfilesApi.create(body);
    expect(mockPost).toHaveBeenCalledWith("/holiday-profiles", body);
  });

  it("get(id) → GET /holiday-profiles/{id}", () => {
    holidayProfilesApi.get("abc-123");
    expect(mockGet).toHaveBeenCalledWith("/holiday-profiles/abc-123");
  });

  it("update(id, data) → PUT /holiday-profiles/{id}", () => {
    holidayProfilesApi.update("abc-123", { is_active: true });
    expect(mockPut).toHaveBeenCalledWith("/holiday-profiles/abc-123", { is_active: true });
  });

  it("delete(id) → DELETE /holiday-profiles/{id}", () => {
    holidayProfilesApi.delete("abc-123");
    expect(mockDel).toHaveBeenCalledWith("/holiday-profiles/abc-123");
  });

  it("addPeriod(profileId, data) → POST /holiday-profiles/{id}/periods", () => {
    const data = { name: "Herbstferien", start_date: "2025-10-27", end_date: "2025-10-30" };
    holidayProfilesApi.addPeriod("pid-1", data);
    expect(mockPost).toHaveBeenCalledWith("/holiday-profiles/pid-1/periods", data);
  });

  it("updatePeriod(profileId, periodId, data) → PUT /holiday-profiles/{pid}/periods/{vpid}", () => {
    holidayProfilesApi.updatePeriod("pid-1", "vp-1", { name: "Neu" });
    expect(mockPut).toHaveBeenCalledWith("/holiday-profiles/pid-1/periods/vp-1", { name: "Neu" });
  });

  it("deletePeriod(profileId, periodId) → DELETE /holiday-profiles/{pid}/periods/{vpid}", () => {
    holidayProfilesApi.deletePeriod("pid-1", "vp-1");
    expect(mockDel).toHaveBeenCalledWith("/holiday-profiles/pid-1/periods/vp-1");
  });

  it("addCustomDay(profileId, data) → POST /holiday-profiles/{id}/custom-days", () => {
    const data = { name: "Konferenztag", date: "2025-10-03" };
    holidayProfilesApi.addCustomDay("pid-1", data);
    expect(mockPost).toHaveBeenCalledWith("/holiday-profiles/pid-1/custom-days", data);
  });

  it("deleteCustomDay(profileId, dayId) → DELETE /holiday-profiles/{pid}/custom-days/{did}", () => {
    holidayProfilesApi.deleteCustomDay("pid-1", "day-1");
    expect(mockDel).toHaveBeenCalledWith("/holiday-profiles/pid-1/custom-days/day-1");
  });
});

// ── recurringShiftsApi ────────────────────────────────────────────────────────

describe("recurringShiftsApi", () => {
  it("list() → GET /recurring-shifts", () => {
    recurringShiftsApi.list();
    expect(mockGet).toHaveBeenCalledWith("/recurring-shifts");
  });

  it("preview(data) → POST /recurring-shifts/preview", () => {
    const data = { weekday: 0, valid_from: "2025-09-01", valid_until: "2025-09-30" };
    recurringShiftsApi.preview(data);
    expect(mockPost).toHaveBeenCalledWith("/recurring-shifts/preview", data);
  });

  it("create(data) → POST /recurring-shifts", () => {
    const data = { weekday: 0, start_time: "08:00", end_time: "13:00", valid_from: "2025-09-01", valid_until: "2025-09-30" };
    recurringShiftsApi.create(data);
    expect(mockPost).toHaveBeenCalledWith("/recurring-shifts", data);
  });

  it("update(id, data) → PUT /recurring-shifts/{id}", () => {
    recurringShiftsApi.update("rs-1", { label: "Morgendienst" });
    expect(mockPut).toHaveBeenCalledWith("/recurring-shifts/rs-1", { label: "Morgendienst" });
  });

  it("updateFrom(id, data) → POST /recurring-shifts/{id}/update-from", () => {
    const data = { from_date: "2025-10-01", start_time: "09:00" };
    recurringShiftsApi.updateFrom("rs-1", data);
    expect(mockPost).toHaveBeenCalledWith("/recurring-shifts/rs-1/update-from", data);
  });

  it("delete(id) → DELETE /recurring-shifts/{id}", () => {
    recurringShiftsApi.delete("rs-1");
    expect(mockDel).toHaveBeenCalledWith("/recurring-shifts/rs-1");
  });
});

// ── calendarDataApi ───────────────────────────────────────────────────────────

describe("calendarDataApi", () => {
  it("vacationData(from, to) → GET /calendar/vacation-data with params", () => {
    calendarDataApi.vacationData("2025-09-01", "2025-09-30");
    expect(mockGet).toHaveBeenCalledWith(
      "/calendar/vacation-data",
      { params: { from: "2025-09-01", to: "2025-09-30" } },
    );
  });

  it("vacationData passes correct date range", () => {
    calendarDataApi.vacationData("2026-01-01", "2026-01-31");
    const call = mockGet.mock.calls[0];
    expect(call[1].params.from).toBe("2026-01-01");
    expect(call[1].params.to).toBe("2026-01-31");
  });
});
