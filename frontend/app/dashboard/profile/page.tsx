"use client";

import { useEffect, useState } from "react";
import { authApi, api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface User {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  created_at?: string;
}

interface Stats {
  totalArticles: number;
  alertes: number;
  specialites: number;
  sources: number;
}

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<Stats>({ totalArticles: 0, alertes: 0, specialites: 0, sources: 3 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [userRes, statsRes, alertsRes] = await Promise.allSettled([
          authApi.me(),
          api.get("/articles/stats"),
          api.get("/alerts/"),
        ]);

        if (userRes.status === "fulfilled") setUser(userRes.value.data);

        const s = statsRes.status === "fulfilled" ? statsRes.value.data : null;
        const a = alertsRes.status === "fulfilled" ? alertsRes.value.data : [];

        if (s) {
          setStats({
            totalArticles: s.total_articles || 0,
            alertes: a?.length || 0,
            specialites: Object.keys(s.par_specialite || {}).length,
            sources: Object.keys(s.par_source || {}).length,
          });
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString("fr-FR", {
      day: "numeric", month: "long", year: "numeric"
    });
  };

  if (loading) {
    return (
      <div className="space-y-4 max-w-2xl">
        <div className="h-8 w-48 bg-gray-100 rounded animate-pulse" />
        <div className="h-48 bg-gray-100 rounded-xl animate-pulse" />
        <div className="h-32 bg-gray-100 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Mon profil</h1>
        <p className="text-gray-500 text-sm mt-1">Informations de votre compte Medical Veille</p>
      </div>

      {/* Avatar + Info */}
      <Card className="border-0 shadow-sm">
        <CardContent className="p-6">
          <div className="flex items-center gap-5">
            <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center text-white text-3xl font-bold shrink-0">
              {user.username?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-900">{user.username}</h2>
              <p className="text-gray-500 text-sm">{user.email}</p>
              {user.created_at && (
                <p className="text-xs text-gray-400 mt-1">
                  Membre depuis {formatDate(user.created_at)}
                </p>
              )}
              <div className="mt-2 flex gap-2">
                {user.is_active ? (
                  <Badge className="bg-green-100 text-green-700 hover:bg-green-100">
                    ✓ Compte actif
                  </Badge>
                ) : (
                  <Badge className="bg-red-100 text-red-700 hover:bg-red-100">
                    Compte inactif
                  </Badge>
                )}
                <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">
                  Professionnel de santé
                </Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats dynamiques */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">Tableau de bord personnel</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Link href="/dashboard/feed">
              <div className="p-4 bg-blue-50 rounded-xl hover:bg-blue-100 transition-colors cursor-pointer text-center">
                <p className="text-2xl font-bold text-blue-600">{stats.totalArticles}</p>
                <p className="text-xs text-gray-500 mt-1">Articles disponibles</p>
              </div>
            </Link>
            <Link href="/dashboard/alerts">
              <div className="p-4 bg-orange-50 rounded-xl hover:bg-orange-100 transition-colors cursor-pointer text-center">
                <p className="text-2xl font-bold text-orange-600">{stats.alertes}</p>
                <p className="text-xs text-gray-500 mt-1">Alertes actives</p>
              </div>
            </Link>
            <Link href="/dashboard/feed">
              <div className="p-4 bg-green-50 rounded-xl hover:bg-green-100 transition-colors cursor-pointer text-center">
                <p className="text-2xl font-bold text-green-600">{stats.specialites}</p>
                <p className="text-xs text-gray-500 mt-1">Spécialités</p>
              </div>
            </Link>
            <Link href="/dashboard/feed">
              <div className="p-4 bg-purple-50 rounded-xl hover:bg-purple-100 transition-colors cursor-pointer text-center">
                <p className="text-2xl font-bold text-purple-600">{stats.sources}</p>
                <p className="text-xs text-gray-500 mt-1">Sources actives</p>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Détails compte */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">Informations du compte</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Nom d&apos;utilisateur</span>
            <span className="text-sm font-medium text-gray-900">{user.username}</span>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Email</span>
            <span className="text-sm font-medium text-gray-900">{user.email}</span>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">ID utilisateur</span>
            <span className="text-sm font-mono text-gray-400">{user.id?.slice(0, 8)}...</span>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Membre depuis</span>
            <span className="text-sm font-medium text-gray-900">{formatDate(user.created_at)}</span>
          </div>
          <div className="flex items-center justify-between py-3">
            <span className="text-sm text-gray-500">Statut</span>
            <span className={`text-sm font-medium ${user.is_active ? "text-green-600" : "text-red-500"}`}>
              {user.is_active ? "✓ Actif" : "Inactif"}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Liens rapides */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">Accès rapide</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3">
          {[
            { label: "📄 Articles", href: "/dashboard/feed", color: "bg-blue-50 text-blue-700 hover:bg-blue-100" },
            { label: "🔍 Recherche", href: "/dashboard/search", color: "bg-green-50 text-green-700 hover:bg-green-100" },
            { label: "🔔 Alertes", href: "/dashboard/alerts", color: "bg-orange-50 text-orange-700 hover:bg-orange-100" },
            { label: "🌐 Réseau", href: "/dashboard/network", color: "bg-purple-50 text-purple-700 hover:bg-purple-100" },
          ].map((item) => (
            <Link key={item.href} href={item.href}>
              <div className={`p-3 rounded-xl text-sm font-medium text-center transition-colors cursor-pointer ${item.color}`}>
                {item.label}
              </div>
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}