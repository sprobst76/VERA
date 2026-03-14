import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://192.168.0.144:31367";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: JWT Token anhängen
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: Token-Refresh bei 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");

      if (refreshToken) {
        try {
          const response = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          localStorage.setItem("access_token", access_token);
          localStorage.setItem("refresh_token", refresh_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }
    }

    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  register: (data: {
    email: string;
    password: string;
    tenant_name: string;
    tenant_slug: string;
    state?: string;
  }) => api.post("/auth/register", data),
  me: () => api.get("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    api.post("/auth/change-password", { current_password, new_password }),
};

// Employees
export const employeesApi = {
  list: (activeOnly = true) =>
    api.get("/employees", { params: { active_only: activeOnly } }),
  me: () => api.get("/employees/me"),           // vollständiges eigenes Profil
  updateMe: (data: { phone?: string | null; email?: string | null }) =>
    api.put("/employees/me", data),
  get: (id: string) => api.get(`/employees/${id}`),
  create: (data: Record<string, unknown>) => api.post("/employees", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/employees/${id}`, data),
  deactivate: (id: string) => api.delete(`/employees/${id}`),
  vacationBalances: (year?: number) =>
    api.get("/employees/vacation-balances", { params: year ? { year } : {} }),
};

// Shifts
export const shiftsApi = {
  list: (params?: {
    from_date?: string;
    to_date?: string;
    employee_id?: string;
  }) => api.get("/shifts", { params }),
  get: (id: string) => api.get(`/shifts/${id}`),
  create: (data: Record<string, unknown>) => api.post("/shifts", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/shifts/${id}`, data),
  delete: (id: string) => api.delete(`/shifts/${id}`),
  bulk: (data: {
    template_id: string;
    from_date: string;
    to_date: string;
    employee_id?: string;
    start_time_override?: string;
    end_time_override?: string;
  }) => api.post("/shifts/bulk", data),
  confirm: (id: string, data: {
    actual_start?: string;
    actual_end?: string;
    confirmation_note?: string;
  }) => api.post(`/shifts/${id}/confirm`, data),
  claim: (id: string) => api.post(`/shifts/${id}/claim`, {}),
  suggestions: (id: string) => api.get(`/shifts/${id}/suggestions`),
};

// Shift Templates
export const templatesApi = {
  list: () => api.get("/shift-templates"),
  create: (data: Record<string, unknown>) => api.post("/shift-templates", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/shift-templates/${id}`, data),
};

// Absences
export const absencesApi = {
  list: (params?: { employee_id?: string; status?: string }) =>
    api.get("/absences", { params }),
  create: (data: Record<string, unknown>) => api.post("/absences", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/absences/${id}`, data),
};

// Care Absences
export const careAbsencesApi = {
  list: () => api.get("/care-absences"),
  create: (data: Record<string, unknown>) => api.post("/care-absences", data),
  delete: (id: string) => api.delete(`/care-absences/${id}`),
};

// Users (Admin only)
export const usersApi = {
  list: () => api.get("/users"),
  create: (data: { email: string; password: string; role?: string }) =>
    api.post("/users", data),
  update: (id: string, data: { role?: string; is_active?: boolean; password?: string }) =>
    api.put(`/users/${id}`, data),
};

// Payroll
export const payrollApi = {
  list: (params?: { month?: string; employee_id?: string }) =>
    api.get("/payroll", { params }),
  calculate: (data: { employee_id: string; month: string }) =>
    api.post("/payroll/calculate", data),
  calculateAll: (month: string) =>
    api.post("/payroll/calculate-all", null, { params: { month } }),
  get: (id: string) => api.get(`/payroll/${id}`),
  update: (id: string, data: { status?: string; notes?: string }) =>
    api.put(`/payroll/${id}`, data),
  downloadPdf: (id: string) =>
    api.get(`/payroll/${id}/pdf`, { responseType: "blob" }),
};

// Holiday Profiles (Ferienprofile)
export const holidayProfilesApi = {
  list: () => api.get("/holiday-profiles"),
  create: (data: Record<string, unknown>) => api.post("/holiday-profiles", data),
  get: (id: string) => api.get(`/holiday-profiles/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/holiday-profiles/${id}`, data),
  delete: (id: string) => api.delete(`/holiday-profiles/${id}`),
  addPeriod: (profileId: string, data: Record<string, unknown>) =>
    api.post(`/holiday-profiles/${profileId}/periods`, data),
  updatePeriod: (profileId: string, periodId: string, data: Record<string, unknown>) =>
    api.put(`/holiday-profiles/${profileId}/periods/${periodId}`, data),
  deletePeriod: (profileId: string, periodId: string) =>
    api.delete(`/holiday-profiles/${profileId}/periods/${periodId}`),
  addCustomDay: (profileId: string, data: Record<string, unknown>) =>
    api.post(`/holiday-profiles/${profileId}/custom-days`, data),
  deleteCustomDay: (profileId: string, dayId: string) =>
    api.delete(`/holiday-profiles/${profileId}/custom-days/${dayId}`),
};

// Recurring Shifts (Regeltermine)
export const recurringShiftsApi = {
  list: () => api.get("/recurring-shifts"),
  preview: (data: Record<string, unknown>) =>
    api.post("/recurring-shifts/preview", data),
  create: (data: Record<string, unknown>) =>
    api.post("/recurring-shifts", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/recurring-shifts/${id}`, data),
  updateFrom: (id: string, data: Record<string, unknown>) =>
    api.post(`/recurring-shifts/${id}/update-from`, data),
  delete: (id: string) => api.delete(`/recurring-shifts/${id}`),
};

// Notifications
export const notificationsApi = {
  getLogs: (params?: { employee_id?: string; channel?: string; status?: string }) =>
    api.get("/notifications/logs", { params }),
  getPreferences: () => api.get("/notifications/preferences"),
  updatePreferences: (data: {
    telegram_chat_id?: string | null;
    quiet_hours_start?: string;
    quiet_hours_end?: string;
    notification_prefs?: Record<string, unknown>;
  }) => api.put("/notifications/preferences", data),
  getVapidKey: () => api.get("/notifications/vapid-key"),
  subscribePush: (data: { endpoint: string; p256dh: string; auth: string }) =>
    api.post("/notifications/push-subscription", data),
  unsubscribePush: (endpoint: string) =>
    api.delete("/notifications/push-subscription", { data: { endpoint } }),
};

// Contract History
export const contractsApi = {
  list: (employeeId: string) =>
    api.get(`/employees/${employeeId}/contracts`),
  create: (employeeId: string, data: {
    valid_from: string;
    contract_type: string;
    hourly_rate: number;
    weekly_hours?: number | null;
    full_time_percentage?: number | null;
    monthly_hours_limit?: number | null;
    annual_salary_limit?: number | null;
    annual_hours_target?: number | null;
    monthly_salary?: number | null;
    note?: string | null;
  }) => api.post(`/employees/${employeeId}/contracts`, data),
};

// Compliance
export const complianceApi = {
  listViolations: (params?: {
    from_date?: string;
    to_date?: string;
    employee_id?: string;
  }) => api.get("/compliance/violations", { params }),
  run: (params?: { from_date?: string; to_date?: string }) =>
    api.post("/compliance/run", null, { params }),
};

// Admin Settings (SMTP)
export const adminSettingsApi = {
  getSmtp: () => api.get("/admin/settings/smtp"),
  updateSmtp: (data: {
    host: string; port: number; user: string; password: string; from_email: string;
  }) => api.put("/admin/settings/smtp", data),
  testSmtp: () => api.post("/admin/settings/smtp/test"),
};

// Calendar vacation data
export const calendarDataApi = {
  vacationData: (from: string, to: string) =>
    api.get("/calendar/vacation-data", { params: { from, to } }),
};

// API Keys
export const apiKeysApi = {
  list: () => api.get("/api-keys"),
  create: (data: { name: string; scopes: string[]; expires_at?: string | null }) =>
    api.post("/api-keys", data),
  revoke: (id: string) => api.delete(`/api-keys/${id}`),
};

// Reports
export const reportsApi = {
  hoursSummary: (params: { from: string; to: string; employee_id?: string }) =>
    api.get("/reports/hours-summary", { params }),
  minijobLimitStatus: (year?: number) =>
    api.get("/reports/minijob-limit-status", { params: year ? { year } : {} }),
  complianceViolations: (params: { from: string; to: string; employee_id?: string }) =>
    api.get("/reports/compliance-violations", { params }),
  surchargeBreakdown: (month: string, employee_id?: string) =>
    api.get("/reports/surcharge-breakdown", { params: { month, ...(employee_id ? { employee_id } : {}) } }),
  exportCsv: (params: { from: string; to: string; employee_id?: string }) =>
    api.get("/reports/export/csv", { params, responseType: "blob" }),
};

// Webhooks
export const webhooksApi = {
  list: () => api.get("/webhooks"),
  create: (data: { name: string; url: string; events: string[]; secret?: string }) =>
    api.post("/webhooks", data),
  update: (id: string, data: Partial<{ name: string; url: string; events: string[]; secret: string; is_active: boolean }>) =>
    api.put(`/webhooks/${id}`, data),
  delete: (id: string) => api.delete(`/webhooks/${id}`),
  test: (id: string) => api.post(`/webhooks/${id}/test`),
  events: () => api.get("/webhooks/events"),
};

export const shiftTypesApi = {
  list: () => api.get("/shift-types"),
  create: (data: { name: string; color: string; description?: string; reminder_enabled: boolean; reminder_minutes_before: number }) =>
    api.post("/shift-types", data),
  update: (id: string, data: Partial<{ name: string; color: string; description: string; reminder_enabled: boolean; reminder_minutes_before: number; is_active: boolean }>) =>
    api.put(`/shift-types/${id}`, data),
  delete: (id: string) => api.delete(`/shift-types/${id}`),
};
