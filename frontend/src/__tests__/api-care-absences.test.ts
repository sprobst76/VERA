/**
 * Tests für careAbsencesApi und employeesApi.vacationBalances (src/lib/api.ts)
 *
 * Verifies correct HTTP method + endpoint for new features:
 * - careAbsencesApi.list / create / delete
 * - employeesApi.vacationBalances
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockGet, mockPost, mockDel } = vi.hoisted(() => ({
  mockGet:  vi.fn().mockResolvedValue({ data: [] }),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
  mockDel:  vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({
      get:    mockGet,
      post:   mockPost,
      put:    vi.fn().mockResolvedValue({ data: {} }),
      delete: mockDel,
      interceptors: {
        request:  { use: vi.fn() },
        response: { use: vi.fn() },
      },
    }),
  },
}));

import { careAbsencesApi, employeesApi } from "@/lib/api";

beforeEach(() => {
  vi.clearAllMocks();
});

// ── careAbsencesApi ───────────────────────────────────────────────────────────

describe("careAbsencesApi", () => {
  it("list() calls GET /care-absences", async () => {
    await careAbsencesApi.list();
    expect(mockGet).toHaveBeenCalledWith("/care-absences");
  });

  it("create() calls POST /care-absences with payload", async () => {
    const payload = {
      type: "vacation",
      start_date: "2025-07-01",
      end_date: "2025-07-14",
      shift_handling: "cancelled_unpaid",
      notify_employees: true,
    };
    await careAbsencesApi.create(payload);
    expect(mockPost).toHaveBeenCalledWith("/care-absences", payload);
  });

  it("delete() calls DELETE /care-absences/{id}", async () => {
    const id = "abc-123";
    await careAbsencesApi.delete(id);
    expect(mockDel).toHaveBeenCalledWith(`/care-absences/${id}`);
  });
});

// ── employeesApi.vacationBalances ─────────────────────────────────────────────

describe("employeesApi.vacationBalances", () => {
  it("calls GET /employees/vacation-balances without params by default", async () => {
    await employeesApi.vacationBalances();
    expect(mockGet).toHaveBeenCalledWith(
      "/employees/vacation-balances",
      { params: {} }
    );
  });

  it("calls GET /employees/vacation-balances with year param", async () => {
    await employeesApi.vacationBalances(2024);
    expect(mockGet).toHaveBeenCalledWith(
      "/employees/vacation-balances",
      { params: { year: 2024 } }
    );
  });
});

// ── Shift-Handling-Optionen ───────────────────────────────────────────────────

describe("careAbsencesApi create payload structure", () => {
  it("accepts all shift_handling values", async () => {
    for (const handling of ["cancelled_unpaid", "carry_over", "paid_anyway"]) {
      vi.clearAllMocks();
      await careAbsencesApi.create({ type: "sick", start_date: "2025-01-01", end_date: "2025-01-02", shift_handling: handling });
      const call = mockPost.mock.calls[0];
      expect(call[1].shift_handling).toBe(handling);
    }
  });

  it("accepts all care absence types", async () => {
    for (const type of ["vacation", "rehab", "hospital", "sick", "other"]) {
      vi.clearAllMocks();
      await careAbsencesApi.create({ type, start_date: "2025-01-01", end_date: "2025-01-02", shift_handling: "carry_over" });
      const call = mockPost.mock.calls[0];
      expect(call[1].type).toBe(type);
    }
  });
});
