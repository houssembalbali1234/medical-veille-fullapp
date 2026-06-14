"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Alert {
  id: string;
  keyword?: string;
  author_name?: string;
  type: "keyword" | "author";
}

interface DigestArticle {
  pubmed_id: string;
  titre: string;
  journal: string;
  specialite: string | null;
  resume_ia: string | null;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [keyword, setKeyword] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(false);
  const [digest, setDigest] = useState<DigestArticle[]>([]);
  const [loadingDigest, setLoadingDigest] = useState(false);
  const [showDigest, setShowDigest] = useState(false);

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    try {
      const res = await api.get("/alerts/");
      setAlerts(res.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddKeyword = async () => {
    if (!keyword.trim()) return;
    setLoading(true);
    try {
      await api.post(`/alerts/keyword?keyword=${encodeURIComponent(keyword)}`);
      setKeyword("");
      fetchAlerts();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddAuthor = async () => {
    if (!author.trim()) return;
    setLoading(true);
    try {
      await api.post(`/alerts/author?author_name=${encodeURIComponent(author)}`);
      setAuthor("");
      fetchAlerts();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAlert = async (alert: Alert) => {
    try {
      if (alert.type === "keyword") {
        await api.delete(`/alerts/keyword/${encodeURIComponent(alert.keyword || "")}`);
      } else {
        await api.delete(`/alerts/author/${encodeURIComponent(alert.author_name || "")}`);
      }
      fetchAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const handleShowDigest = async () => {
    setLoadingDigest(true);
    setShowDigest(true);
    try {
      const res = await api.get("/alerts/digest");
      setDigest(res.data?.articles || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDigest(false);
    }
  };

  const keywordAlerts = alerts.filter((a) => a.type === "keyword" || a.keyword);
  const authorAlerts = alerts.filter((a) => a.type === "author" || a.author_name);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Alertes & Veille</h1>
        <p className="text-gray-500 text-sm mt-1">
          Suivez automatiquement les nouvelles publications sur vos sujets d&apos;intérêt
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Alerte mot-clé */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              🔍 Alerte par mot-clé
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="Ex: cancer, diabetes..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddKeyword()}
                className="h-9"
              />
              <Button onClick={handleAddKeyword} disabled={loading || !keyword.trim()}
                className="bg-blue-600 hover:bg-blue-700 text-white h-9 px-4 shrink-0">
                Ajouter
              </Button>
            </div>
            <div className="space-y-2">
              {keywordAlerts.map((alert) => (
                <div key={alert.id} className="flex items-center justify-between bg-blue-50 rounded-lg px-3 py-2">
                  <span className="text-sm text-blue-700 font-medium">🔍 {alert.keyword}</span>
                  <button onClick={() => handleDeleteAlert(alert)}
                    className="text-red-400 hover:text-red-600 text-xs">
                    Supprimer
                  </button>
                </div>
              ))}
              {keywordAlerts.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-2">Aucune alerte mot-clé</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Alerte auteur */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              👤 Alerte par auteur (KOL)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="Ex: Smith J, Harris G D..."
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddAuthor()}
                className="h-9"
              />
              <Button onClick={handleAddAuthor} disabled={loading || !author.trim()}
                className="bg-blue-600 hover:bg-blue-700 text-white h-9 px-4 shrink-0">
                Suivre
              </Button>
            </div>
            <div className="space-y-2">
              {authorAlerts.map((alert) => (
                <div key={alert.id} className="flex items-center justify-between bg-green-50 rounded-lg px-3 py-2">
                  <span className="text-sm text-green-700 font-medium">👤 {alert.author_name}</span>
                  <button onClick={() => handleDeleteAlert(alert)}
                    className="text-red-400 hover:text-red-600 text-xs">
                    Supprimer
                  </button>
                </div>
              ))}
              {authorAlerts.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-2">Aucune alerte auteur</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Résumé alertes */}
      <Card className="border-0 shadow-sm bg-blue-50">
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <p className="font-semibold text-blue-900">
              Mes alertes ({alerts.length})
            </p>
            <p className="text-xs text-blue-600 mt-1">
              Vérification automatique chaque nuit via Celery Beat
            </p>
          </div>
          <Button onClick={handleShowDigest} disabled={loadingDigest}
            className="bg-blue-600 hover:bg-blue-700 text-white">
            {loadingDigest ? "Chargement..." : "📋 Voir le digest"}
          </Button>
        </CardContent>
      </Card>

      {/* Digest */}
      {showDigest && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">
              📋 Digest — Articles de la semaine
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingDigest ? (
              <div className="space-y-3">
                {[1,2,3].map((i) => (
                  <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : digest.length > 0 ? (
              <div className="space-y-3">
                {digest.map((article) => (
                  <div key={article.pubmed_id}
                    className="p-4 border border-gray-100 rounded-xl hover:border-blue-200 transition-colors">
                    <p className="text-sm font-medium text-gray-900 leading-snug">{article.titre}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {article.journal && (
                        <span className="text-xs text-gray-400">{article.journal}</span>
                      )}
                      {article.specialite && (
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                          {article.specialite}
                        </span>
                      )}
                    </div>
                    {article.resume_ia && (
                      <p className="text-xs text-gray-600 mt-2 leading-relaxed">{article.resume_ia}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm text-center py-8">
                Aucun article trouvé cette semaine pour vos alertes
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}