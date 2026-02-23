"use client";

import { Bell, Construction } from "lucide-react";

export default function NotificationsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">Benachrichtigungen</h1>
      <div className="bg-card rounded-xl border border-border p-12 text-center space-y-4">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto"
          style={{ backgroundColor: "rgb(var(--ctp-yellow) / 0.15)", color: "rgb(var(--ctp-yellow))" }}
        >
          <Bell size={32} />
        </div>
        <div>
          <div className="font-semibold text-foreground text-lg">Benachrichtigungen</div>
          <p className="text-muted-foreground text-sm mt-1">
            Telegram-, Matrix- und E-Mail-Benachrichtigungen – in Entwicklung
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Construction size={14} />
          <span>Wird in einer der nächsten Versionen verfügbar sein</span>
        </div>
      </div>
    </div>
  );
}
