"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface KeywordAlert {
  keyword: string;
  specialite?: string;
}

interface AuthorAlert {
  author_name: string;
}

export default function AlertsPage() {
  const [keywordAlerts, setKeywordAlerts] = useState<KeywordAlert[]>([]);
  const [authorAlerts, setAuthorAlerts] = useState<AuthorAlert[]>([]);
  const [keyword, setKeyword] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  // Charger les alertes existantes
  useEffect(() => {
    api.get("/alerts/").then((res) => {
      setKeywordAlerts(res.data.keyword_alerts || []);
      setAuthorAlerts(res.data.author_alerts || []);
    }).catch(console.error);
  }, []);

  const handleCreateKeyword = async () => {
    if (!keyword.trim()) return;
    setLoading(true);
    setError("");
    try {
      await api.post(`/alerts/keyword?keyword=${encodeURIComponent(keyword)}`);
      setKeywordAlerts((prev) => [...prev, { keyword }]);
      setKeyword("");
      setSuccess("Alerte mot-clé créée !");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de la création");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAuthor = async () => {
    if (!author.trim()) return;
    setLoading(true);
    setError("");
    try {
      await api.post(`/alerts/author?author_name=${encodeURIComponent(author)}`);
      setAuthorAlerts((prev) => [...prev, { author_name: author }]);
      setAuthor("");
      setSuccess("Alerte auteur créée !");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de la création");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteKeyword = async (kw: string) => {
    try {
      await api.delete(`/alerts/keyword/${encodeURIComponent(kw)}`);
      setKeywordAlerts((prev) => prev.filter((a) => a.keyword !== kw));
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteAuthor = async (name: string) => {
    try {
      await api.delete(`/alerts/author/${encodeURIComponent(name)}`);
      setAuthorAlerts((prev) => prev.filter((a) => a.author_name !== name));
    } catch (err) {
      console.error(err);
    }
  };

  const total = keywordAlerts.length + authorAlerts.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Alertes & Veille</h1>
        <p className="text-gray-500 text-sm mt-1">
          Configurez vos alertes pour suivre des mots-clés ou des auteurs spécifiques
        </p>
      </div>

      {/* Notifications */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-600 px-4 py-3 rounded-lg text-sm">
          {success}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Créer alertes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Mot-clé */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Alerte par mot-clé
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Ex: cancer, alzheimer, covid..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateKeyword()}
              className="h-10"
            />
            <Button
              onClick={handleCreateKeyword}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white"
              disabled={loading || !keyword.trim()}
            >
              + Ajouter le mot-clé
            </Button>
          </CardContent>
        </Card>

        {/* Auteur */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Alerte par auteur (KOL)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Ex: Smith J, Dupont M..."
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateAuthor()}
              className="h-10"
            />
            <Button
              onClick={handleCreateAuthor}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white"
              disabled={loading || !author.trim()}
            >
              + Ajouter l&apos;auteur
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Alertes actives */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Mes alertes ({total})
        </h2>

        {total === 0 ? (
          <Card className="border-dashed border-2 border-gray-200">
            <CardContent className="py-16 text-center">
              <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <p className="text-gray-500 font-medium">Aucune alerte configurée</p>
              <p className="text-gray-400 text-sm mt-1">Créez votre première alerte ci-dessus</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {/* Alertes mots-clés */}
            {keywordAlerts.map((alert) => (
              <Card key={alert.keyword} className="border-0 shadow-sm">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    <div>
                      <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">
                        🔍 {alert.keyword}
                      </Badge>
                      {alert.specialite && (
                        <span className="ml-2 text-xs text-gray-400">{alert.specialite}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteKeyword(alert.keyword)}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </CardContent>
              </Card>
            ))}

            {/* Alertes auteurs */}
            {authorAlerts.map((alert) => (
              <Card key={alert.author_name} className="border-0 shadow-sm">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    </div>
                    <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100">
                      👤 {alert.author_name}
                    </Badge>
                  </div>
                  <button
                    onClick={() => handleDeleteAuthor(alert.author_name)}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Info digest */}
      <Card className="border-0 shadow-sm bg-blue-50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-blue-900">Digest hebdomadaire</h3>
              <p className="text-blue-700 text-sm mt-1">
                Chaque lundi à 8h, vous recevrez un email récapitulatif des nouveaux articles
                correspondant à vos alertes configurées.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}