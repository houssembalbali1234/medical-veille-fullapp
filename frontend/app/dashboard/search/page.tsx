"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, articlesMongoApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ElasticArticle {
  pubmed_id: string;
  titre: string;
  auteurs: any;
  resume: string;
  specialite: string;
  source: string;
  annee: string;
  date_publication: string;
}

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ElasticArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingArticle, setLoadingArticle] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState({ pubmed: 0, europePmc: 0, biorxiv: 0 });

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const response = await articlesMongoApi.searchAll(query, 50);
      const data = response.data;
      const raw: ElasticArticle[] = Array.isArray(data) ? data : (data.results || []);
      setTotal(data.total || raw.length);
      setCounts({
        pubmed: raw.filter(a => a.source === "pubmed").length,
        europePmc: raw.filter(a => a.source === "europe_pmc").length,
        biorxiv: raw.filter(a => a.source === "biorxiv").length,
      });
      setResults(raw);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleArticleClick = async (article: ElasticArticle) => {
    setLoadingArticle(article.pubmed_id);
    try {
      // Tous les articles → chercher dans MongoDB par pubmed_id
      const res = await api.get(`/articles/${article.pubmed_id}`);
      if (res.data?.id) {
        router.push(`/dashboard/articles/mongo/${res.data.id}`);
        return;
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingArticle(null);
    }
  };

  const getAuteurs = (auteurs: any): string => {
    if (!auteurs) return "";
    if (Array.isArray(auteurs)) return auteurs.join(", ");
    return auteurs;
  };

  const sourceColors: Record<string, string> = {
    pubmed: "bg-blue-100 text-blue-700",
    europe_pmc: "bg-green-100 text-green-700",
    biorxiv: "bg-purple-100 text-purple-700",
  };

  const specialiteColors: Record<string, string> = {
    Oncologie: "bg-red-100 text-red-700",
    Cardiologie: "bg-pink-100 text-pink-700",
    Neurologie: "bg-purple-100 text-purple-700",
    Endocrinologie: "bg-yellow-100 text-yellow-700",
    Infectiologie: "bg-green-100 text-green-700",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Recherche avancée</h1>
        <p className="text-gray-500 text-sm mt-1">
          Recherchez dans PubMed, Europe PMC et bioRxiv via Elasticsearch
        </p>
      </div>

      <Card className="border-0 shadow-sm">
        <CardContent className="p-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
                fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <Input placeholder="Ex: cancer, diabetes, cardiology..."
                value={query} onChange={(e) => setQuery(e.target.value)}
                className="pl-10 h-12 text-base" />
            </div>
            <Button type="submit" className="h-12 px-6 bg-blue-600 hover:bg-blue-700 text-white"
              disabled={loading || !query.trim()}>
              {loading ? "Recherche..." : "Rechercher"}
            </Button>
          </form>

          <div className="mt-4">
            <p className="text-xs text-gray-400 mb-2">Recherches populaires :</p>
            <div className="flex flex-wrap gap-2">
              {["cancer", "diabetes", "cardiology", "alzheimer", "covid", "oncology"].map((s) => (
                <button key={s} onClick={() => setQuery(s)}
                  className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs rounded-full transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!loading && searched && (
        <>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <p className="text-sm text-gray-600">
              <span className="font-semibold">{results.length}</span> résultats pour{" "}
              <span className="text-blue-600 font-medium">&quot;{query}&quot;</span>
              {total > results.length && <span className="text-gray-400"> (sur {total})</span>}
            </p>
            {results.length > 0 && (
              <div className="flex gap-3 text-xs">
                <span className="bg-blue-50 text-blue-700 px-2 py-1 rounded-full">PubMed: {counts.pubmed}</span>
                <span className="bg-green-50 text-green-700 px-2 py-1 rounded-full">Europe PMC: {counts.europePmc}</span>
                <span className="bg-purple-50 text-purple-700 px-2 py-1 rounded-full">bioRxiv: {counts.biorxiv}</span>
              </div>
            )}
          </div>

          {results.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.map((article) => (
                <Card key={article.pubmed_id}
                  className={`border border-gray-100 transition-all cursor-pointer ${
                    loadingArticle === article.pubmed_id
                      ? "opacity-50 cursor-wait"
                      : "hover:shadow-md hover:border-blue-200"
                  }`}
                  onClick={() => handleArticleClick(article)}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
                        {article.titre}
                      </h3>
                      {article.specialite && (
                        <span className={`text-xs font-medium px-2 py-1 rounded-full shrink-0 ${specialiteColors[article.specialite] || "bg-blue-100 text-blue-700"}`}>
                          {article.specialite}
                        </span>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0 space-y-2">
                    {article.resume && (
                      <p className="text-sm text-gray-600 line-clamp-3">{article.resume}</p>
                    )}
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      {getAuteurs(article.auteurs) && (
                        <span className="truncate max-w-[200px]">{getAuteurs(article.auteurs)}</span>
                      )}
                      {(article.annee || article.date_publication) && (
                        <span>{article.annee || article.date_publication}</span>
                      )}
                      {article.source && (
                        <Badge variant="outline" className={`text-xs ${sourceColors[article.source] || ""}`}>
                          {article.source}
                        </Badge>
                      )}
                    </div>
                    {loadingArticle === article.pubmed_id ? (
                      <p className="text-xs text-blue-500 flex items-center gap-1">
                        <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                        </svg>
                        Chargement...
                      </p>
                    ) : (
                      <p className="text-xs text-blue-500">Cliquez pour voir le détail →</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border-dashed border-2 border-gray-200">
              <CardContent className="py-16 text-center">
                <p className="text-gray-500 font-medium">Aucun résultat trouvé</p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {!searched && !loading && (
        <Card className="border-0 shadow-sm">
          <CardContent className="py-16 text-center">
            <svg className="w-16 h-16 text-blue-100 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <h3 className="text-lg font-semibold text-gray-700">Lancez votre recherche</h3>
            <p className="text-gray-400 text-sm mt-2 max-w-md mx-auto">
              Recherchez parmi des milliers d&apos;articles via Elasticsearch full-text
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}