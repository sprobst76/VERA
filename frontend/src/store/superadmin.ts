import { create } from "zustand";
import { persist } from "zustand/middleware";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://192.168.0.144:31367";

interface SuperAdminState {
  token: string | null;
  email: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useSuperAdminStore = create<SuperAdminState>()(
  persist(
    (set, get) => ({
      token: null,
      email: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const res = await axios.post(`${API_URL}/api/v1/superadmin/login`, { email, password });
          const data = res.data;
          if (data.requires_2fa) {
            // Passwort OK, aber 2FA nötig – Fehler mit 2FA-Daten werfen
            set({ isLoading: false });
            const err = Object.assign(new Error("2fa_required"), { response: { data } });
            throw err;
          }
          set({ token: data.access_token, email, isAuthenticated: true, isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: () => {
        set({ token: null, email: null, isAuthenticated: false });
      },
    }),
    {
      name: "vera-superadmin",
      partialize: (state) => ({ token: state.token, email: state.email, isAuthenticated: state.isAuthenticated }),
    }
  )
);

// Axios instance mit SuperAdmin-Token
export function getSuperAdminApi() {
  const token = useSuperAdminStore.getState().token;
  const instance = axios.create({
    baseURL: `${API_URL}/api/v1/superadmin`,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  return instance;
}
