"use client";

import { useEffect } from "react";
import { notificationsApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

/** Konvertiert Base64url-String → Uint8Array (für VAPID applicationServerKey). */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from(Array.from(rawData).map((c) => c.charCodeAt(0)));
}

/**
 * Unsichtbare Hintergrundkomponente: registriert den Service Worker und
 * synchronisiert eine vorhandene Push-Subscription beim Login mit dem Backend.
 */
export function PushManager() {
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) return;
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

    async function syncPushSubscription() {
      try {
        const registration = await navigator.serviceWorker.register("/sw.js");
        await navigator.serviceWorker.ready;

        // Bestehende Subscription prüfen und ggf. mit Backend synchronisieren
        const existing = await registration.pushManager.getSubscription();
        if (!existing) return;

        const j = existing.toJSON();
        if (!j.keys?.p256dh || !j.keys?.auth) return;

        // Sicherstellen dass das Backend die Subscription kennt (silent upsert)
        await notificationsApi.subscribePush({
          endpoint: existing.endpoint,
          p256dh: j.keys.p256dh,
          auth: j.keys.auth,
        });
      } catch {
        // Fehler beim SW-Register oder Sync sind nicht kritisch
      }
    }

    syncPushSubscription();
  }, [isAuthenticated]);

  return null;
}

/**
 * Hilfsfunktion zum Aktivieren von Web Push (wird von der Notifications-Seite genutzt).
 * Gibt die neue Subscription zurück oder null bei Fehler/Ablehnung.
 */
export async function enablePushNotifications(): Promise<PushSubscription | null> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;
  try {
    const registration = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;

    const vapidRes = await notificationsApi.getVapidKey();
    const vapidKey = vapidRes.data.public_key as string;
    if (!vapidKey) return null;

    const sub = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey).buffer as ArrayBuffer,
    });
    const j = sub.toJSON();
    if (!j.keys?.p256dh || !j.keys?.auth) return null;

    await notificationsApi.subscribePush({
      endpoint: sub.endpoint,
      p256dh: j.keys.p256dh,
      auth: j.keys.auth,
    });
    return sub;
  } catch {
    return null;
  }
}

/**
 * Hilfsfunktion zum Deaktivieren von Web Push.
 */
export async function disablePushNotifications(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.ready;
    const sub = await registration.pushManager.getSubscription();
    if (!sub) return;
    await notificationsApi.unsubscribePush(sub.endpoint);
    await sub.unsubscribe();
  } catch {
    // ignore
  }
}
