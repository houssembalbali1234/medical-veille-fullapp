"use client";

import { useEffect, useState, useRef, useCallback } from "react";

interface Notification {
  id: string;
  type: string;
  titre?: string;
  message?: string;
  data?: any;
  timestamp: string;
  read: boolean;
}

export default function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const unread = notifications.filter(n => !n.read).length;

  const connect = useCallback(() => {
    const token = localStorage.getItem("token");
    const userId = getUserIdFromToken(token);
    if (!token || !userId) return;

    try {
      const ws = new WebSocket(`ws://localhost:8000/ws/notifications/${userId}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        console.log("WebSocket connecté !");
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "heartbeat") {
            ws.send("ping");
            return;
          }
          if (msg.type === "connection") return;
          if (msg.type === "pong") return;

          // Nouvelle notification
          const notif: Notification = {
            id: Date.now().toString(),
            type: msg.type,
            titre: msg.titre || msg.data?.titre || getTypeLabel(msg.type),
            message: msg.message || msg.data?.message || "",
            data: msg.data,
            timestamp: new Date().toISOString(),
            read: false,
          };
          setNotifications(prev => [notif, ...prev].slice(0, 20));
        } catch (err) {
          console.error("WebSocket message error:", err);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnexion automatique après 5 secondes
        setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        setConnected(false);
      };
    } catch (err) {
      console.error("WebSocket error:", err);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  // Fermer dropdown en cliquant ailleurs
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const markAllRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const clearAll = () => {
    setNotifications([]);
    setOpen(false);
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      alert: "Nouvelle alerte",
      new_article: "Nouvel article",
      scraping_status: "Scraping terminé",
      admin: "Notification admin",
    };
    return labels[type] || "Notification";
  };

  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      alert: "🔔",
      new_article: "📄",
      scraping_status: "⚙️",
      admin: "📢",
    };
    return icons[type] || "📣";
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={() => { setOpen(!open); if (!open) markAllRead(); }}
        className="relative flex items-center justify-center w-9 h-9 rounded-full hover:bg-blue-600 transition-colors"
        title={connected ? "Notifications (connecté)" : "Notifications (déconnecté)"}
      >
        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        {/* Badge unread */}
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
            {unread > 9 ? "9+" : unread}
          </span>
        )}

        {/* Indicateur connexion */}
        <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-blue-700 ${connected ? "bg-green-400" : "bg-gray-400"}`} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-12 w-80 bg-white rounded-xl shadow-xl border border-gray-100 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900 text-sm">Notifications</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {connected ? "● Temps réel" : "○ Déconnecté"}
              </span>
            </div>
            {notifications.length > 0 && (
              <button onClick={clearAll} className="text-xs text-gray-400 hover:text-red-500 transition-colors">
                Effacer tout
              </button>
            )}
          </div>

          {/* Liste */}
          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-12 text-center">
                <div className="text-3xl mb-2">🔔</div>
                <p className="text-sm text-gray-400">Aucune notification</p>
                <p className="text-xs text-gray-300 mt-1">
                  {connected ? "En attente de nouvelles..." : "Connexion en cours..."}
                </p>
              </div>
            ) : (
              notifications.map((notif) => (
                <div key={notif.id}
                  className={`px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${!notif.read ? "bg-blue-50" : ""}`}>
                  <div className="flex items-start gap-3">
                    <span className="text-lg shrink-0">{getTypeIcon(notif.type)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{notif.titre}</p>
                      {notif.message && (
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{notif.message}</p>
                      )}
                      <p className="text-xs text-gray-300 mt-1">{formatTime(notif.timestamp)}</p>
                    </div>
                    {!notif.read && (
                      <div className="w-2 h-2 bg-blue-500 rounded-full shrink-0 mt-1.5" />
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-gray-400 text-center">
              {connected ? "🟢 Connecté en temps réel" : "🔴 Reconnexion..."}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function getUserIdFromToken(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
}