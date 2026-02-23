"use client";

import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

interface ThemeToggleProps {
  /** Extra classes merged onto the button */
  className?: string;
  /** When true, shows only the icon (no label) */
  iconOnly?: boolean;
}

export function ThemeToggle({ className = "", iconOnly = false }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm w-full transition-colors hover:bg-[rgb(var(--sidebar-hover-bg))] ${className}`}
      title={isDark ? "Zum Hellmodus wechseln" : "Zum Dunkelmodus wechseln"}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
      {!iconOnly && (isDark ? "Hellmodus" : "Dunkelmodus")}
    </button>
  );
}
