"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface MongoArticle {
  id: string;
  pubmed_id: string;
  titre: string;
  auteurs: any;
  resume: string;
  resume_ia: string;
  specialite: string;
  source: string;
  annee: string;
  journal: string;
  url: string;
  type_etude: string;
}

interface ResumeIA {
  resume_ia: string;
  population: string;
  intervention: string;
  resultats: string;
  conclusion: string;
}

export default function MongoArticleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [article, setArticle] = useState<MongoArticle | null>(null);
  const [traduction, setTraduction] = useState<{ titre_fr: string; resume_fr: string } | null>(null);
  const [resumeIA, setResumeIA] = useState<ResumeIA | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingTraduction, setLoadingTraduction] = useState(false);
  const [loadingIA, setLoadingIA] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/articles/id/${id}`)
      .then((res) => {
        setArticle(res.data);
        // Si resume_ia existe déjà, l'afficher
        if (res.data.resume_ia) {
          setResumeIA({
            resume_ia: res.data.resume_ia,
            population: res.data.resume_structure?.population || "",
            intervention: res.data.resume_structure?.intervention || "",
            resultats: res.data.resume_structure?.resultats || "",
            conclusion: res.data.resume_structure?.conclusion || "",
          });
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError("Article introuvable");
        setLoading(false);
      });
  }, [id]);

  const handleTraduire = async () => {
    setLoadingTraduction(true);
    try {
      const res = await api.post(`/articles/${id}/translate`);
      setTraduction(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingTraduction(false);
    }
  };

  const handleGenerateIA = async () => {
    if (!article?.pubmed_id) return;
    setLoadingIA(true);
    try {
      const res = await api.post(`/articles/resume-ia/${article.pubmed_id}`);
      setResumeIA({
        resume_ia: res.data.resume_ia,
        population: res.data.population || "",
        intervention: res.data.intervention || "",
        resultats: res.data.resultats || "",
        conclusion: res.data.conclusion || "",
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingIA(false);
    }
  };

  const getAuteurs = (auteurs: any): string => {
    if (!auteurs) return "";
    if (Array.isArray(auteurs)) return auteurs.join(", ");
    return auteurs;
  };

  if (loading) {
    return (
      <div className="space-y-4 max-w-4xl">
        <div className="h-8 w-32 bg-gray-100 rounded animate-pulse" />
        <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="text-center py-24">
        <p className="text-gray-500">{error || "Article introuvable"}</p>
        <Button onClick={() => router.back()} className="mt-4">Retour</Button>
      </div>
    );
  }

  const sourceColors: Record<string, string> = {
    pubmed: "bg-blue-100 text-blue-700",
    europe_pmc: "bg-green-100 text-green-700",
    biorxiv: "bg-purple-100 text-purple-700",
  };

  return (
    <div className="max-w-4xl space-y-6">
      <button onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Retour
      </button>

      <Card className="border-0 shadow-sm">
        <CardContent className="p-6 space-y-4">
          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            {article.specialite && <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">{article.specialite}</Badge>}
            {article.source && <Badge className={`hover:opacity-80 ${sourceColors[article.source] || "bg-gray-100 text-gray-700"}`}>{article.source}</Badge>}
            {article.annee && <Badge className="bg-gray-100 text-gray-600 hover:bg-gray-100">{article.annee}</Badge>}
            {article.type_etude && <Badge className="bg-indigo-100 text-indigo-700 hover:bg-indigo-100">{article.type_etude}</Badge>}
          </div>

          {/* Titre */}
          <div>
            <h1 className="text-2xl font-bold text-gray-900 leading-snug">
              {traduction ? traduction.titre_fr : article.titre}
            </h1>
            {traduction && <p className="text-sm text-gray-400 mt-1 italic">Titre original : {article.titre}</p>}
          </div>

          {article.journal && (
            <p className="text-sm text-gray-500"><span className="font-medium text-gray-700">Journal : </span>{article.journal}</p>
          )}

          {getAuteurs(article.auteurs) && (
            <p className="text-sm text-gray-500"><span className="font-medium text-gray-700">Auteurs : </span>{getAuteurs(article.auteurs)}</p>
          )}

          {article.url && (
            <a href={article.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Voir l&apos;article original
            </a>
          )}

          {/* Résumé */}
          {article.resume ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700">Résumé</h3>
                {!traduction && (
                  <Button onClick={handleTraduire} disabled={loadingTraduction} variant="outline"
                    className="text-xs h-8 border-blue-200 text-blue-600 hover:bg-blue-50">
                    {loadingTraduction ? (
                      <span className="flex items-center gap-1">
                        <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Traduction...
                      </span>
                    ) : "🇫🇷 Traduire en français"}
                  </Button>
                )}
              </div>

              {traduction ? (
                <div className="space-y-3">
                  <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">🇫🇷</span>
                      <span className="text-xs font-semibold text-green-700">Traduction française (via Llama 3.1)</span>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed">{traduction.resume_fr}</p>
                  </div>
                  <details className="cursor-pointer">
                    <summary className="text-xs text-gray-400 hover:text-gray-600 select-none">🇬🇧 Voir le texte original</summary>
                    <p className="text-sm text-gray-500 leading-relaxed mt-2 pl-3 border-l-2 border-gray-200">{article.resume}</p>
                  </details>
                </div>
              ) : (
                <p className="text-sm text-gray-600 leading-relaxed">{article.resume}</p>
              )}
            </div>
          ) : (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
              <p className="text-sm text-yellow-700">
                ⚠️ Résumé non disponible pour cet article.
                <a href={article.url} target="_blank" rel="noopener noreferrer" className="ml-1 underline hover:text-yellow-900">
                  Voir l&apos;article complet →
                </a>
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analyse PICO */}
      {!resumeIA ? (
        <Card className="border-0 shadow-sm border-dashed border-2 border-blue-200 bg-blue-50">
          <CardContent className="p-6 text-center">
            <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="font-semibold text-blue-900 mb-1">Analyse PICO avec Llama 3.1</h3>
            <p className="text-blue-700 text-sm mb-4">
              Générez une analyse structurée adaptée aux professionnels de santé (&lt;300 mots)
            </p>
            <Button onClick={handleGenerateIA} disabled={loadingIA || !article.resume}
              className="bg-blue-600 hover:bg-blue-700 text-white">
              {loadingIA ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Génération en cours...
                </span>
              ) : "✨ Générer l'analyse PICO"}
            </Button>
            {!article.resume && (
              <p className="text-xs text-gray-400 mt-2">Résumé requis pour générer l&apos;analyse PICO</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <Card className="border-0 shadow-sm bg-gradient-to-r from-blue-50 to-indigo-50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <span className="text-lg">✨</span>
                Résumé IA — {article.source}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-700 leading-relaxed">{resumeIA.resume_ia}</p>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Analyse structurée PICO</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { label: "👥 Population", value: resumeIA.population, color: "bg-blue-50 border-blue-200" },
                { label: "💊 Intervention", value: resumeIA.intervention, color: "bg-green-50 border-green-200" },
                { label: "📊 Résultats", value: resumeIA.resultats, color: "bg-yellow-50 border-yellow-200" },
                { label: "🎯 Conclusion", value: resumeIA.conclusion, color: "bg-purple-50 border-purple-200" },
              ].map((item) => item.value && (
                <div key={item.label} className={`p-4 rounded-xl border ${item.color}`}>
                  <p className="text-xs font-bold text-gray-700 mb-1">{item.label}</p>
                  <p className="text-sm text-gray-600 leading-relaxed">{item.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}