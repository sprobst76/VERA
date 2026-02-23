"use client";

import { useAuthStore } from "@/store/auth";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useEffect, useState } from "react";

// In Produktion: NEXT_PUBLIC_DEMO_SLUG ist z.B. "demo-a3f9b2c1"
// In Entwicklung: nicht gesetzt → DemoBar immer sichtbar
const DEMO_SLUG = process.env.NEXT_PUBLIC_DEMO_SLUG;
const DEMO_COOKIE = "vera_demo";

const DEMO_USERS = [
  { label: "Stefan",  email: "stefan@vera.demo",  role: "Admin",     color: "bg-vera-700 text-white" },
  { label: "Lea",     email: "lea@vera.demo",      role: "Verwalter", color: "bg-indigo-600 text-white" },
  { label: "Anna",    email: "anna@vera.demo",     role: "Teilzeit",  color: "bg-emerald-600 text-white" },
  { label: "Tobias",  email: "tobias@vera.demo",   role: "Teilzeit",  color: "bg-emerald-600 text-white" },
  { label: "Marie",   email: "marie@vera.demo",    role: "Minijob",   color: "bg-amber-500 text-white" },
  { label: "Felix",   email: "felix@vera.demo",    role: "Minijob",   color: "bg-amber-500 text-white" },
  { label: "Lena",    email: "lena@vera.demo",     role: "Minijob",   color: "bg-amber-500 text-white" },
  { label: "Noah",    email: "noah@vera.demo",     role: "Minijob",   color: "bg-amber-500 text-white" },
  { label: "Sophie",  email: "sophie@vera.demo",   role: "Minijob",   color: "bg-amber-500 text-white" },
];

function hasDemoCookie(): boolean {
  return document.cookie.split(";").some((c) => c.trim().startsWith(`${DEMO_COOKIE}=`));
}

export function DemoBar() {
  const { login, user } = useAuthStore();
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(hasDemoCookie());
  }, []);

  if (!visible) return null;

  const switchUser = async (email: string, label: string) => {
    try {
      await login(email, "demo1234");
      toast.success(`Eingeloggt als ${label}`);
      router.push("/");
    } catch {
      toast.error("Login fehlgeschlagen");
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-gray-900/95 backdrop-blur border-t border-gray-700 px-3 py-2">
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
        <span className="text-xs text-gray-400 font-medium shrink-0">🎭</span>
        {DEMO_USERS.map((u) => (
          <button
            key={u.email}
            onClick={() => switchUser(u.email, u.label)}
            className={`text-xs px-2.5 py-1.5 rounded-full font-medium shrink-0 transition-opacity hover:opacity-80 ${u.color} ${
              user?.email === u.email ? "ring-2 ring-white ring-offset-1 ring-offset-gray-900" : ""
            }`}
            title={`${u.role}: ${u.email}`}
          >
            {u.label}
            <span className="ml-1 opacity-70 font-normal hidden sm:inline">{u.role}</span>
          </button>
        ))}
        {user && (
          <span className="ml-2 text-xs text-gray-400 shrink-0 hidden sm:block">
            <span className="text-white font-medium">{user.email.split("@")[0]}</span>
          </span>
        )}
      </div>
    </div>
  );
}
