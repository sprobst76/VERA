"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { absencesApi } from "@/lib/api";
import { DemoBar } from "@/components/shared/DemoBar";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import {
  CalendarDays,
  Users,
  Clock,
  CalendarOff,
  DollarSign,
  Bell,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
  ShieldAlert,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/",              label: "Übersicht",         icon: BarChart3,    adminOnly: false },
  { href: "/calendar",      label: "Kalender",           icon: CalendarDays, adminOnly: false },
  { href: "/shifts",        label: "Dienste",            icon: Clock,        adminOnly: false },
  { href: "/employees",     label: "Mitarbeiter",        icon: Users,        adminOnly: false },
  { href: "/absences",      label: "Abwesenheiten",      icon: CalendarOff,  adminOnly: false },
  { href: "/payroll",       label: "Abrechnung",         icon: DollarSign,   adminOnly: false },
  { href: "/compliance",    label: "Compliance",         icon: ShieldAlert,  adminOnly: false },
  { href: "/notifications", label: "Benachrichtigungen", icon: Bell,         adminOnly: false },
  { href: "/reports",       label: "Berichte",           icon: BarChart3,    adminOnly: false },
  { href: "/settings",      label: "Einstellungen",      icon: Settings,     adminOnly: false },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, logout, fetchMe } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isPrivileged = user?.role === "admin" || user?.role === "manager";

  const { data: pendingAbsences = [] } = useQuery({
    queryKey: ["absences", "pending"],
    queryFn: () => absencesApi.list({ status: "pending" }).then(r => r.data),
    enabled: isPrivileged,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const pendingCount = (pendingAbsences as any[]).length;

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) {
      fetchMe().catch(() => router.push("/login"));
    }
  }, [isAuthenticated, fetchMe, router]);

  if (!isAuthenticated || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted-foreground text-sm">Wird geladen…</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        style={{
          backgroundColor: "rgb(var(--sidebar-bg))",
          color: "rgb(var(--sidebar-fg))",
        }}
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-64 flex flex-col transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div
          className="flex items-center justify-between p-4"
          style={{ borderBottom: "1px solid rgb(var(--border))" }}
        >
          <div>
            <h1 className="text-xl font-bold">VERA</h1>
            <p className="text-xs truncate" style={{ color: "rgb(var(--muted-foreground))" }}>
              {user.email}
            </p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-2.5 rounded"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.filter(item => !item.adminOnly || user.role !== "employee").map(({ href, label, icon: Icon }) => {
            const badge = href === "/absences" && isPrivileged ? pendingCount : 0;
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setSidebarOpen(false)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
                style={
                  pathname === href
                    ? {
                        backgroundColor: "rgb(var(--sidebar-active-bg))",
                        fontWeight: 500,
                      }
                    : {}
                }
                onMouseEnter={(e) => {
                  if (pathname !== href)
                    (e.currentTarget as HTMLElement).style.backgroundColor =
                      "rgb(var(--sidebar-hover-bg))";
                }}
                onMouseLeave={(e) => {
                  if (pathname !== href)
                    (e.currentTarget as HTMLElement).style.backgroundColor = "";
                }}
              >
                <Icon size={18} />
                <span className="flex-1">{label}</span>
                {badge > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full font-medium min-w-[20px] text-center"
                    style={{ backgroundColor: "rgb(var(--ctp-red))", color: "#fff" }}>
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom: Theme toggle + Logout */}
        <div className="p-3 space-y-1" style={{ borderTop: "1px solid rgb(var(--border))" }}>
          <ThemeToggle />
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm w-full transition-colors"
            onMouseEnter={(e) =>
              ((e.currentTarget as HTMLElement).style.backgroundColor =
                "rgb(var(--sidebar-hover-bg))")
            }
            onMouseLeave={(e) =>
              ((e.currentTarget as HTMLElement).style.backgroundColor = "")
            }
          >
            <LogOut size={18} />
            Abmelden
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar (mobile) */}
        <header className="bg-card border-b border-border px-4 py-3 flex items-center gap-3 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-3 rounded hover:bg-accent"
          >
            <Menu size={22} />
          </button>
          <span className="font-semibold text-ctp-blue">VERA</span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 pb-16">
          {children}
        </main>
      </div>

      <DemoBar />
    </div>
  );
}
