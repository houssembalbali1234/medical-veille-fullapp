"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import NotificationBell from "@/components/notifications/NotificationBell";

export default function Navbar({ username }: { username?: string }) {
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {}
    localStorage.removeItem("token");
    router.push("/login");
  };

  return (
    <nav className="bg-blue-700 text-white shadow-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="font-bold text-lg">Medical Veille</span>
          </Link>

          {/* Navigation */}
          <div className="hidden md:flex items-center gap-6 text-sm font-medium">
            <Link href="/dashboard" className="hover:text-blue-200 transition-colors">
              Tableau de bord
            </Link>
            <Link href="/dashboard/feed" className="hover:text-blue-200 transition-colors">
              Articles
            </Link>
            <Link href="/dashboard/search" className="hover:text-blue-200 transition-colors">
              Recherche
            </Link>
            <Link href="/dashboard/alerts" className="hover:text-blue-200 transition-colors">
              Alertes
            </Link>
            <Link href="/dashboard/network" className="hover:text-blue-200 transition-colors">
              Réseau
            </Link>
            {/* ✅ Nouveau lien Recommandations */}
            <Link href="/dashboard/recommendations" className="hover:text-blue-200 transition-colors">
              ✨ Recommandations
            </Link>
          </div>

          {/* Right side: Notification Bell + User Menu */}
          <div className="flex items-center gap-3">
            {/* Cloche notifications WebSocket */}
            <NotificationBell />

            {/* User Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                  <Avatar className="w-8 h-8">
                    <AvatarFallback className="bg-blue-500 text-white text-sm font-bold">
                      {username ? username[0].toUpperCase() : "U"}
                    </AvatarFallback>
                  </Avatar>
                  <span className="hidden md:block text-sm font-medium">{username}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem asChild>
                  <Link href="/dashboard/profile">Mon profil</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-red-600 cursor-pointer">
                  Se déconnecter
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </nav>
  );
}