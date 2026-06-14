"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, articlesApi } from "@/lib/api";
import { Article } from "@/types";
import ArticleCard from "@/components/articles/ArticleCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";

function normalizeMongoArticle(a: any): Article {
  return {
    id: a.id || a._id,
    titre: a.titre,
    auteurs: Array.isArray(a.auteurs) ? a.auteurs.join(", ") : (a.auteurs || ""),
    resume: a.resume || a.resume_ia || "",
    specialite: a.specialite || "",
    source: a.source,
    annee: a.annee,
    created_at: a.scraped_at || a.created_at,
  };
}

const COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444", "#EC4899", "#06B6D4", "#84CC16"];

export default function DashboardPage() {
  const router = useRouter();

  // ✅ TanStack Query — Stats
  const { data: statsData } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const res = await api.get("/articles/stats");
      return res.data;
    },
    staleTime: 5 * 60 * 1000,
  });

  // ✅ TanStack Query — Alertes
  const { data: alertesData } = useQuery({
    queryKey: ["alertes-count"],
    queryFn: async () => {
      const res = await api.get("/alerts/");
      return res.data;
    },
    staleTime: 60 * 1000,
  });

  // ✅ TanStack Query — Articles récents
  const { data: articlesData, isLoading: loading } = useQuery({
    queryKey: ["articles-recents"],
    queryFn: async () => {
      const [pgRes, biorxivRes, europePmcRes] = await Promise.allSettled([
        articlesApi.getAll({ limit: 3 }),
        api.get("/articles/?source=biorxiv&limite=3"),
        api.get("/articles/?source=europe_pmc&limite=3"),
      ]);

      const pgArticles: Article[] = pgRes.status === "fulfilled" ? pgRes.value.data : [];
      const biorxivArticles: Article[] = biorxivRes.status === "fulfilled"
        ? biorxivRes.value.data.map(normalizeMongoArticle) : [];
      const europePmcArticles: Article[] = europePmcRes.status === "fulfilled"
        ? europePmcRes.value.data.map(normalizeMongoArticle) : [];

      const mixed: Article[] = [];
      for (let i = 0; i < 3; i++) {
        if (pgArticles[i]) mixed.push(pgArticles[i]);
        if (biorxivArticles[i]) mixed.push(biorxivArticles[i]);
        if (europePmcArticles[i]) mixed.push(europePmcArticles[i]);
      }
      return mixed.slice(0, 9);
    },
    staleTime: 2 * 60 * 1000,
  });

  // Données calculées
  const nbSpecialites = Object.keys(statsData?.par_specialite || {}).length;
  const nbAlertes = Array.isArray(alertesData) ? alertesData.length : 0;
  const articles = articlesData || [];

  const stats = {
    total: statsData?.total_articles || 0,
    specialites: nbSpecialites,
    pubmed: statsData?.par_source?.pubmed || 0,
    europePmc: statsData?.par_source?.europe_pmc || 0,
    biorxiv: statsData?.par_source?.biorxiv || 0,
    alertes: nbAlertes,
  };

  // Données Recharts
  const specialiteData = Object.entries(statsData?.par_specialite || {})
    .slice(0, 6)
    .map(([name, value]) => ({ name, value: Number(value) }));

  const anneeData = Object.entries(statsData?.par_annee || {})
    .slice(0, 8)
    .map(([name, value]) => ({ name, value: Number(value) }));

  const typeEtudeData = Object.entries(statsData?.par_type_etude || {})
    .slice(0, 6)
    .map(([name, value]) => ({ name: name.length > 20 ? name.slice(0, 20) + "..." : name, value: Number(value) }));

  const sourceData = [
    { name: "PubMed", value: stats.pubmed, fill: "#3B82F6" },
    { name: "Europe PMC", value: stats.europePmc, fill: "#10B981" },
    { name: "bioRxiv", value: stats.biorxiv, fill: "#8B5CF6" },
  ];

  const statCards = [
    {
      label: "Total articles", value: stats.total.toString(),
      href: "/dashboard/feed", bg: "bg-blue-50",
      icon: <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
    },
    {
      label: "Spécialités couvertes", value: stats.specialites.toString(),
      href: "/dashboard/feed", bg: "bg-green-50",
      icon: <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>,
    },
    {
      label: "Sources actives", value: "3",
      href: "/dashboard/feed", bg: "bg-purple-50",
      icon: <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>,
    },
    {
      label: "Alertes actives", value: stats.alertes.toString(),
      href: "/dashboard/alerts", bg: "bg-orange-50",
      icon: <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tableau de bord</h1>
        <p className="text-gray-500 text-sm mt-1">Bienvenue sur votre espace de veille scientifique médicale</p>
      </div>

      {/* Stats cliquables */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Link key={stat.label} href={stat.href}>
            <Card className="border-0 shadow-sm hover:shadow-md transition-all cursor-pointer hover:border-blue-200 border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${stat.bg}`}>{stat.icon}</div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                    <p className="text-xs text-gray-500">{stat.label}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Graphiques Recharts */}
      {statsData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* ✅ PieChart — Articles par spécialité */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Articles par spécialité</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={specialiteData}
                    cx="50%" cy="50%"
                    innerRadius={50} outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    // ✅ Clic sur une spécialité → redirection vers le feed filtré
                    onClick={(data) => {
                      if (data && data.name) {
                        router.push(`/dashboard/feed?specialite=${encodeURIComponent(data.name)}`);
                      }
                    }}
                    cursor="pointer"
                  >
                    {specialiteData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => [`${value} articles`]} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* ✅ BarChart — Articles par année */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Articles par année</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={anneeData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => [`${value} articles`]} />
                  <Bar dataKey="value" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* ✅ BarChart — Types d'études */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Types d'études</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={typeEtudeData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={120} />
                  <Tooltip formatter={(value) => [`${value} articles`]} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {typeEtudeData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* ✅ BarChart — Articles par source avec clic */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Articles par source</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sourceData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => [`${value} articles`]} />
                  <Bar
                    dataKey="value"
                    radius={[4, 4, 0, 0]}
                    // ✅ Clic sur une source → redirection vers le feed filtré
                    onClick={(data) => {
                      if (data && data.name) {
                        const sourceMap: Record<string, string> = {
                          "PubMed": "pubmed",
                          "Europe PMC": "europe_pmc",
                          "bioRxiv": "biorxiv"
                        };
                        const source = sourceMap[data.name];
                        if (source) router.push(`/dashboard/feed?source=${source}`);
                      }
                    }}
                    cursor="pointer"
                  >
                    {sourceData.map((entry, index) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Articles récents */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Articles récents</h2>
          <Link href="/dashboard/feed" className="text-blue-600 text-sm hover:underline">Voir tout →</Link>
        </div>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1,2,3,4,5,6].map((i) => <div key={i} className="h-40 bg-gray-100 rounded-xl animate-pulse" />)}
          </div>
        ) : articles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {articles.map((article) => <ArticleCard key={article.id} article={article} />)}
          </div>
        ) : (
          <Card className="border-dashed border-2 border-gray-200">
            <CardContent className="py-12 text-center">
              <p className="text-gray-500 text-sm">Aucun article pour le moment</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Sources */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Sources de données</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { name: "PubMed", desc: "Base de données biomédicale principale", color: "border-l-blue-500", count: stats.pubmed, href: "/dashboard/feed?source=pubmed" },
            { name: "Europe PMC", desc: "Publications européennes en accès libre", color: "border-l-green-500", count: stats.europePmc, href: "/dashboard/feed?source=europe_pmc" },
            { name: "bioRxiv", desc: "Prépublications en biologie", color: "border-l-purple-500", count: stats.biorxiv, href: "/dashboard/feed?source=biorxiv" },
          ].map((source) => (
            <Link key={source.name} href={source.href}>
              <Card className={`border-l-4 ${source.color} shadow-sm hover:shadow-md transition-all cursor-pointer`}>
                <CardContent className="p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-gray-900">{source.name}</h3>
                      <p className="text-xs text-gray-500 mt-1">{source.desc}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-2xl font-bold text-gray-900">{source.count}</span>
                      <p className="text-xs text-gray-400">articles</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}