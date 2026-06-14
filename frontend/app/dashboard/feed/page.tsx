"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api, articlesApi } from "@/lib/api";
import { Article } from "@/types";
import ArticleCard from "@/components/articles/ArticleCard";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

const SPECIALITES = [
  "Toutes", "Oncologie", "Cardiologie", "Neurologie",
  "Endocrinologie", "Infectiologie", "Immunologie", "Néphrologie", "Général",
];

const SOURCES = ["Toutes", "pubmed", "europe_pmc", "biorxiv"];

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

function FeedContent() {
  const searchParams = useSearchParams();
  const [articles, setArticles] = useState<Article[]>([]);
  const [filtered, setFiltered] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [specialite, setSpecialite] = useState("Toutes");
  const [source, setSource] = useState("Toutes");
  const [page, setPage] = useState(1);
  const PER_PAGE = 9;

  // ✅ Lire les paramètres source ET specialite depuis l'URL
  useEffect(() => {
    const sourceParam = searchParams.get("source");
    const specialiteParam = searchParams.get("specialite");
    if (sourceParam) setSource(sourceParam);
    if (specialiteParam) setSpecialite(specialiteParam);
  }, [searchParams]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [pgRes, biorxivRes, europePmcRes, pubmedMongoRes] = await Promise.allSettled([
          articlesApi.getAll({ limit: 100 }),
          api.get("/articles/?source=biorxiv&limite=50"),
          api.get("/articles/?source=europe_pmc&limite=100"),
          api.get("/articles/?source=pubmed&limite=100"),
        ]);

        const pgArticles: Article[] = pgRes.status === "fulfilled"
          ? pgRes.value.data : [];
        const biorxiv: Article[] = biorxivRes.status === "fulfilled"
          ? biorxivRes.value.data.map(normalizeMongoArticle) : [];
        const europePmc: Article[] = europePmcRes.status === "fulfilled"
          ? europePmcRes.value.data.map(normalizeMongoArticle) : [];
        const pubmedMongo: Article[] = pubmedMongoRes.status === "fulfilled"
          ? pubmedMongoRes.value.data.map(normalizeMongoArticle) : [];

        const seen = new Set<string>();
        const all: Article[] = [];

        // ✅ PostgreSQL en priorité — filtre les articles sans résumé
        for (const a of pgArticles) {
          if (a.id && a.titre && a.resume && !seen.has(a.id)) {
            seen.add(a.id);
            all.push(a);
          }
        }

        // ✅ MongoDB ensuite — filtre aussi les articles sans résumé
        for (const a of [...pubmedMongo, ...biorxiv, ...europePmc]) {
          if (a.id && a.titre && a.resume && !seen.has(a.id)) {
            seen.add(a.id);
            all.push(a);
          }
        }

        setArticles(all);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  useEffect(() => {
    let result = [...articles];
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (a) => a.titre?.toLowerCase().includes(q) ||
          a.resume?.toLowerCase().includes(q) ||
          a.auteurs?.toLowerCase().includes(q)
      );
    }
    if (specialite !== "Toutes") {
      result = result.filter((a) =>
        a.specialite?.toLowerCase() === specialite.toLowerCase()
      );
    }
    if (source !== "Toutes") {
      result = result.filter((a) => a.source === source);
    }
    setFiltered(result);
    setPage(1);
  }, [search, specialite, source, articles]);

  const totalPages = Math.ceil(filtered.length / PER_PAGE);
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const sourceLabel = (s: string) => {
    if (s === "europe_pmc") return "Europe PMC";
    if (s === "biorxiv") return "bioRxiv";
    if (s === "pubmed") return "PubMed";
    return s;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Articles scientifiques</h1>
        <p className="text-gray-500 text-sm mt-1">
          {filtered.length} article{filtered.length > 1 ? "s" : ""} · PubMed, Europe PMC, bioRxiv
        </p>
      </div>

      <Card className="border-0 shadow-sm">
        <CardContent className="p-4 space-y-4">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <Input placeholder="Rechercher par titre, auteur, résumé..."
              value={search} onChange={(e) => setSearch(e.target.value)}
              className="pl-10 h-11" />
          </div>

          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Spécialité</p>
            <div className="flex flex-wrap gap-2">
              {SPECIALITES.map((s) => (
                <button key={s} onClick={() => setSpecialite(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    specialite === s ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Source</p>
            <div className="flex flex-wrap gap-2">
              {SOURCES.map((s) => (
                <button key={s} onClick={() => setSource(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    source === s ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}>
                  {sourceLabel(s)}
                </button>
              ))}
            </div>
          </div>

          {(specialite !== "Toutes" || source !== "Toutes" || search) && (
            <button
              onClick={() => { setSearch(""); setSpecialite("Toutes"); setSource("Toutes"); }}
              className="text-xs text-blue-600 hover:underline">
              ✕ Réinitialiser les filtres
            </button>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : paginated.length > 0 ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginated.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                ← Précédent
              </button>
              <div className="flex gap-1">
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                  const p = i + 1;
                  return (
                    <button key={p} onClick={() => setPage(p)}
                      className={`w-9 h-9 text-sm rounded-lg font-medium ${
                        page === p ? "bg-blue-600 text-white" : "border border-gray-200 hover:bg-gray-50"
                      }`}>
                      {p}
                    </button>
                  );
                })}
              </div>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                Suivant →
              </button>
            </div>
          )}
        </>
      ) : (
        <Card className="border-dashed border-2 border-gray-200">
          <CardContent className="py-16 text-center">
            <p className="text-gray-500 font-medium">Aucun article trouvé</p>
            <p className="text-gray-400 text-sm mt-1">Essayez de modifier vos filtres</p>
            <button onClick={() => { setSearch(""); setSpecialite("Toutes"); setSource("Toutes"); }}
              className="mt-3 text-blue-600 text-sm hover:underline">
              Réinitialiser les filtres
            </button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function FeedPage() {
  return (
    <Suspense fallback={<div className="h-96 bg-gray-100 rounded-xl animate-pulse" />}>
      <FeedContent />
    </Suspense>
  );
}