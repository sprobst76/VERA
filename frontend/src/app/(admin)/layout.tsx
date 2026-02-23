"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useSuperAdminStore } from "@/store/superadmin";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Shield, Building2, Users, LogOut, UserCog } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/admin/tenants", label: "Tenants",      icon: Building2 },
  { href: "/admin/admins",  label: "SuperAdmins",  icon: Users },
  { href: "/admin/account", label: "Mein Account", icon: UserCog },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, email, logout } = useSuperAdminStore();

  useEffect(() => {
    if (!isAuthenticated && pathname !== "/admin/login") {
      router.push("/admin/login");
    }
  }, [isAuthenticated, pathname, router]);

  // Show login page without sidebar
  if (!isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className="w-56 flex flex-col shrink-0"
        style={{
          backgroundColor: "rgb(var(--sidebar-bg))",
          color: "rgb(var(--sidebar-fg))",
          borderRight: "1px solid rgb(var(--border))",
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 p-4" style={{ borderBottom: "1px solid rgb(var(--border))" }}>
          <Shield size={18} style={{ color: "rgb(var(--ctp-red))" }} />
          <div>
            <h1 className="text-sm font-bold">VERA Admin</h1>
            <p className="text-xs truncate" style={{ color: "rgb(var(--muted-foreground))", maxWidth: "130px" }}>
              {email}
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                pathname === href ? "font-medium" : "opacity-75 hover:opacity-100"
              )}
              style={pathname === href ? { backgroundColor: "rgb(var(--sidebar-active-bg))" } : {}}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-3 space-y-1" style={{ borderTop: "1px solid rgb(var(--border))" }}>
          <ThemeToggle />
          <button
            onClick={() => { logout(); router.push("/admin/login"); }}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm w-full opacity-75 hover:opacity-100 transition-opacity"
          >
            <LogOut size={16} />
            Abmelden
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        {children}
      </main>
    </div>
  );
}
