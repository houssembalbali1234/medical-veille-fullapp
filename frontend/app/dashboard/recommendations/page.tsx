"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Recommendation {
  pubmed_id: string;
  titre: string;
  journal: string;
  annee: string;
  specialite: string | null;
  resume_ia: string | null;
  recommendation_score: number;
  recommendation_reason: string;
}

interface UserStats {
  total_interactions: number;
  interactions_par_type: Record<string, number>;
  specialites_preferees: Record<string, number>;
  articles_sauvegardes: number;
}

export default function RecommendationsPage() {
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingInteraction, setLoadingInteraction] = useState<string | null>(null);
  const [savedArticles, setSavedArticles] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [recRes, statsRes] = await Promise.allSettled([
        api.get("/recommendations/feed", { params: { limit: 10 } }),
        api.get("/recommendations/stats"),
      ]);
      if (recRes.status === "fulfilled") {
        setRecommendations(recRes.value.data.recommendations || []);
      } else {
        console.error("Erreur recommendations:", recRes.reason);
      }
      if (statsRes.status === "fulfilled") {
        setStats(statsRes.value.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInteraction = async (pubmed_id: string, type: string, specialite?: string, titre?: string) => {
    setLoadingInteraction(`${pubmed_id}-${type}`);
    try {
      // Enregistrer l'interaction
      await api.post(`/recommendations/interaction`, null, {
        params: {
          pubmed_id,
          interaction_type: type,
          ...(specialite ? { specialite } : {})
        }
      });

      // ✅ Mise à jour locale immédiate des stats
      setStats(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          total_interactions: prev.total_interactions + 1,
          interactions_par_type: {
            ...prev.interactions_par_type,
            [type]: (prev.interactions_par_type[type] || 0) + 1
          },
          articles_sauvegardes: type === "save"
            ? prev.articles_sauvegardes + 1
            : prev.articles_sauvegardes,
        };
      });

      // ✅ Supprimer l'article immédiatement de la liste
      if (type === "like" || type === "dislike" || type === "save") {
        setRecommendations(prev => prev.filter(r => r.pubmed_id !== pubmed_id));
      }

      // ✅ Si sauvegarde → appeler aussi /recommendations/save
      if (type === "save") {
        await api.post(`/recommendations/save`, null, {
          params: {
            pubmed_id,
            titre: titre || "Article sauvegardé",
            ...(specialite ? { specialite } : {})
          }
        });
        setSavedArticles(prev => new Set(Array.from(prev).concat(pubmed_id)));
      }

    } catch (err) {
      console.error(err);
    } finally {
      setLoadingInteraction(null);
    }
  };

  const handleArticleClick = async (pubmed_id: string, specialite?: string) => {
    await handleInteraction(pubmed_id, "view", specialite || undefined);
    try {
      const res = await api.get(`/articles/${pubmed_id}`);
      if (res.data?.id) {
        router.push(`/dashboard/articles/mongo/${res.data.id}`);
      }
    } catch {
      try {
        const res = await api.get(`/articles-pg/by-pubmed/${pubmed_id}`);
        if (res.data?.id) {
          router.push(`/dashboard/articles/${res.data.id}`);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const sourceColor = (pubmed_id: string) => {
    if (pubmed_id.startsWith("biorxiv")) return "bg-purple-100 text-purple-700";
    if (pubmed_id.startsWith("epmc")) return "bg-green-100 text-green-700";
    return "bg-blue-100 text-blue-700";
  };

  const sourceLabel = (pubmed_id: string) => {
    if (pubmed_id.startsWith("biorxiv")) return "bioRxiv";
    if (pubmed_id.startsWith("epmc")) return "Europe PMC";
    return "PubMed";
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Recommandations personnalisées</h1>
        <p className="text-gray-500 text-sm mt-1">
          Articles sélectionnés selon vos préférences et interactions
        </p>
      </div>

      {/* Stats utilisateur */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="border-0 shadow-sm bg-blue-50">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-blue-700">{stats.total_interactions}</p>
              <p className="text-xs text-gray-500 mt-1">Interactions</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm bg-green-50">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-green-700">{stats.articles_sauvegardes}</p>
              <p className="text-xs text-gray-500 mt-1">Sauvegardés</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm bg-purple-50">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-purple-700">
                {Object.keys(stats.specialites_preferees).length}
              </p>
              <p className="text-xs text-gray-500 mt-1">Spécialités suivies</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm bg-orange-50">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-orange-700">
                {stats.interactions_par_type?.like || 0}
              </p>
              <p className="text-xs text-gray-500 mt-1">Articles aimés</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Spécialités préférées */}
      {stats && Object.keys(stats.specialites_preferees).length > 0 && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Vos spécialités préférées</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.specialites_preferees).map(([spec, score]) => (
                <div key={spec} className="flex items-center gap-1 bg-blue-50 px-3 py-1 rounded-full">
                  <span className="text-sm text-blue-700 font-medium">{spec}</span>
                  <span className="text-xs text-blue-400">({score > 0 ? "+" : ""}{score.toFixed(1)})</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommandations */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Articles recommandés ({recommendations.length})
          </h2>
          <Button onClick={fetchAll} variant="outline" className="text-xs h-8">
            🔄 Actualiser
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1,2,3,4].map((i) => (
              <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : recommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.map((rec) => (
              <Card key={rec.pubmed_id}
                className="border border-gray-100 shadow-sm hover:shadow-md transition-all">
                <CardContent className="p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Badge className={`text-xs hover:opacity-80 ${sourceColor(rec.pubmed_id)}`}>
                      {sourceLabel(rec.pubmed_id)}
                    </Badge>
                    {rec.specialite && (
                      <Badge className="text-xs bg-gray-100 text-gray-600 hover:bg-gray-100">
                        {rec.specialite}
                      </Badge>
                    )}
                    {rec.annee && (
                      <span className="text-xs text-gray-400">{rec.annee}</span>
                    )}
                  </div>

                  <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2 mb-2 cursor-pointer hover:text-blue-600"
                    onClick={() => handleArticleClick(rec.pubmed_id, rec.specialite || undefined)}>
                    {rec.titre}
                  </h3>

                  {rec.journal && (
                    <p className="text-xs text-gray-400 mb-2">{rec.journal}</p>
                  )}

                  {rec.resume_ia && (
                    <p className="text-xs text-gray-600 line-clamp-2 mb-3 leading-relaxed">
                      {rec.resume_ia}
                    </p>
                  )}

                  <div className="flex items-center gap-1 mb-3">
                    <span className="text-xs">✨</span>
                    <span className="text-xs text-blue-600 italic">{rec.recommendation_reason}</span>
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                    <button
                      onClick={() => handleInteraction(rec.pubmed_id, "like", rec.specialite || undefined)}
                      disabled={loadingInteraction === `${rec.pubmed_id}-like`}
                      className="flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
                    >
                      👍 J'aime
                    </button>
                    <button
                      onClick={() => handleInteraction(rec.pubmed_id, "save", rec.specialite || undefined, rec.titre)}
                      disabled={loadingInteraction === `${rec.pubmed_id}-save`}
                      className="flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                    >
                      🔖 Sauvegarder
                    </button>
                    <button
                      onClick={() => handleInteraction(rec.pubmed_id, "dislike", rec.specialite || undefined)}
                      disabled={loadingInteraction === `${rec.pubmed_id}-dislike`}
                      className="flex items-center gap-1 px-3 py-1 text-xs rounded-full bg-red-50 text-red-600 hover:bg-red-100 transition-colors ml-auto"
                    >
                      👎
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="border-dashed border-2 border-gray-200">
            <CardContent className="py-16 text-center">
              <p className="text-4xl mb-3">🎯</p>
              <h3 className="text-lg font-semibold text-gray-700">Aucune recommandation</h3>
              <p className="text-gray-400 text-sm mt-2 max-w-md mx-auto">
                Consultez et interagissez avec des articles pour que l'algorithme apprenne vos préférences
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}