"use client";

import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface Researcher {
  nom: string;
  nb_articles: number;
  specialite_principale: string | null;
}

interface ResearcherProfile {
  nom: string;
  nb_articles: number;
  specialites: any;
  top_journaux: Record<string, number>;
  annees_actif: string[];
  top_coauthors: { nom: string; nb_collaborations: number }[];
  articles: { pubmed_id: string; titre: string; annee: string; specialite: string | null }[];
}

// ✅ Interface ORCID ajoutée
interface OrcidProfile {
  found: boolean;
  orcid_id?: string;
  orcid_url?: string;
  nom?: string;
  keywords?: string[];
  urls?: string[];
  publications_orcid?: { titre: string; annee: string; doi: string }[];
}

interface GraphData {
  nodes: { id: string; label: string; specialite: string | null; nb_articles: number }[];
  edges: { source: string; target: string; weight: number }[];
  total_researchers: number;
  total_collaborations: number;
}

export default function NetworkPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ResearcherProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [activeTab, setActiveTab] = useState<"list" | "graph">("list");
  const [orcidProfile, setOrcidProfile] = useState<OrcidProfile | null>(null); // ✅ ORCID state
  const [loadingOrcid, setLoadingOrcid] = useState(false); // ✅ ORCID loading
  const graphRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get("/network/top-researchers")
      .then((res) => setResearchers(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));

    api.get("/network/graph")
      .then((res) => setGraphData(res.data))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (activeTab === "graph" && graphData && graphRef.current) {
      renderGraph();
    }
  }, [activeTab, graphData]);

  const renderGraph = () => {
    if (!graphRef.current || !graphData) return;
    graphRef.current.innerHTML = "";
    const width = graphRef.current.clientWidth || 800;
    const height = 500;
    const topNodes = graphData.nodes.slice(0, 50);
    const nodeIds = new Set(topNodes.map(n => n.id));
    const filteredEdges = graphData.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target)).slice(0, 100);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.style.borderRadius = "12px";
    svg.style.background = "#f8fafc";
    const colorMap: Record<string, string> = {
      "Oncologie": "#E85D24", "Cardiologie": "#E91E8C", "Neurologie": "#7C3AED",
      "Endocrinologie": "#D97706", "Néphrologie": "#EA580C", "Infectiologie": "#16A34A",
      "Immunologie": "#2563EB", "default": "#6B7280"
    };
    const nodes = topNodes.map((n) => ({
      ...n, x: width / 2 + (Math.random() - 0.5) * width * 0.8,
      y: height / 2 + (Math.random() - 0.5) * height * 0.8, vx: 0, vy: 0
    }));
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    for (let iter = 0; iter < 100; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x, dy = nodes[j].y - nodes[i].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 800 / (dist * dist);
          nodes[i].vx -= (dx / dist) * force; nodes[i].vy -= (dy / dist) * force;
          nodes[j].vx += (dx / dist) * force; nodes[j].vy += (dy / dist) * force;
        }
      }
      filteredEdges.forEach(e => {
        const s = nodeMap.get(e.source), t = nodeMap.get(e.target);
        if (!s || !t) return;
        const dx = t.x - s.x, dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = dist * 0.01;
        s.vx += (dx / dist) * force; s.vy += (dy / dist) * force;
        t.vx -= (dx / dist) * force; t.vy -= (dy / dist) * force;
      });
      nodes.forEach(n => {
        n.vx += (width / 2 - n.x) * 0.005; n.vy += (height / 2 - n.y) * 0.005;
        n.x += n.vx * 0.5; n.y += n.vy * 0.5; n.vx *= 0.8; n.vy *= 0.8;
        n.x = Math.max(30, Math.min(width - 30, n.x)); n.y = Math.max(30, Math.min(height - 30, n.y));
      });
    }
    filteredEdges.forEach(e => {
      const s = nodeMap.get(e.source), t = nodeMap.get(e.target);
      if (!s || !t) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(s.x)); line.setAttribute("y1", String(s.y));
      line.setAttribute("x2", String(t.x)); line.setAttribute("y2", String(t.y));
      line.setAttribute("stroke", "#CBD5E1"); line.setAttribute("stroke-width", "1"); line.setAttribute("opacity", "0.5");
      svg.appendChild(line);
    });
    nodes.forEach(n => {
      const color = colorMap[n.specialite || "default"] || colorMap.default;
      const radius = Math.min(8 + n.nb_articles * 2, 18);
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", String(n.x)); circle.setAttribute("cy", String(n.y));
      circle.setAttribute("r", String(radius)); circle.setAttribute("fill", color);
      circle.setAttribute("opacity", "0.85"); circle.setAttribute("stroke", "white"); circle.setAttribute("stroke-width", "1.5");
      circle.style.cursor = "pointer";
      circle.addEventListener("click", () => { setActiveTab("list"); handleSelectResearcher(n.id); });
      circle.addEventListener("mouseenter", () => { circle.setAttribute("opacity", "1"); circle.setAttribute("r", String(radius + 3)); });
      circle.addEventListener("mouseleave", () => { circle.setAttribute("opacity", "0.85"); circle.setAttribute("r", String(radius)); });
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${n.label} (${n.nb_articles} articles)`;
      circle.appendChild(title); svg.appendChild(circle);
      if (n.nb_articles > 1) {
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.textContent = n.label.split(" ").pop() || n.label;
        text.setAttribute("x", String(n.x)); text.setAttribute("y", String(n.y + radius + 12));
        text.setAttribute("text-anchor", "middle"); text.setAttribute("font-size", "9"); text.setAttribute("fill", "#6B7280");
        svg.appendChild(text);
      }
    });
    graphRef.current.appendChild(svg);
  };

  const handleSelectResearcher = async (name: string) => {
    setLoadingProfile(true);
    setOrcidProfile(null); // ✅ Reset ORCID
    try {
      const res = await api.get(`/network/researcher/${encodeURIComponent(name)}`);
      setSelected(res.data);
      // ✅ Charger ORCID en parallèle
      fetchOrcid(name);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingProfile(false);
    }
  };

  // ✅ Nouvelle fonction ORCID
  const fetchOrcid = async (name: string) => {
    setLoadingOrcid(true);
    try {
      const res = await api.get(`/network/orcid/${encodeURIComponent(name)}`);
      setOrcidProfile(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingOrcid(false);
    }
  };

  const filtered = researchers.filter((r) =>
    r.nom.toLowerCase().includes(search.toLowerCase())
  );

  const getSpecialites = (specialites: any): string[] => {
    if (!specialites) return [];
    if (Array.isArray(specialites)) return specialites;
    if (typeof specialites === "object") return Object.keys(specialites).filter(k => k);
    return [];
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Réseau de chercheurs</h1>
        <p className="text-gray-500 text-sm mt-1">Explorez les chercheurs les plus actifs et leurs collaborations</p>
      </div>

      {graphData && (
        <div className="grid grid-cols-2 gap-4">
          <Card className="border-0 shadow-sm bg-blue-50">
            <CardContent className="p-4 text-center">
              <p className="text-3xl font-bold text-blue-700">{graphData.total_researchers}</p>
              <p className="text-sm text-blue-600">Chercheurs</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm bg-purple-50">
            <CardContent className="p-4 text-center">
              <p className="text-3xl font-bold text-purple-700">{graphData.total_collaborations}</p>
              <p className="text-sm text-purple-600">Collaborations</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={() => setActiveTab("list")}
          className={activeTab === "list" ? "bg-blue-600 text-white hover:bg-blue-700" : "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"}>
          📋 Liste
        </Button>
        <Button onClick={() => setActiveTab("graph")}
          className={activeTab === "graph" ? "bg-blue-600 text-white hover:bg-blue-700" : "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"}>
          🕸️ Graphe de collaboration
        </Button>
      </div>

      {activeTab === "graph" && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Graphe de collaboration (Top 50 chercheurs)</CardTitle>
            <p className="text-xs text-gray-400">Cliquez sur un nœud pour voir le profil</p>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3 mb-3">
              {[
                { label: "Oncologie", color: "#E85D24" }, { label: "Cardiologie", color: "#E91E8C" },
                { label: "Neurologie", color: "#7C3AED" }, { label: "Endocrinologie", color: "#D97706" },
                { label: "Autres", color: "#6B7280" },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-xs text-gray-500">{item.label}</span>
                </div>
              ))}
            </div>
            <div ref={graphRef} className="w-full" style={{ minHeight: 500 }} />
          </CardContent>
        </Card>
      )}

      {activeTab === "list" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-4">
            <Input placeholder="Rechercher un chercheur..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="h-10" />
            {loading ? (
              <div className="space-y-3">{[1,2,3,4,5].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />)}</div>
            ) : (
              <div className="space-y-2">
                {filtered.map((researcher, index) => (
                  <Card key={researcher.nom}
                    className={`border-0 shadow-sm cursor-pointer transition-all hover:shadow-md ${selected?.nom === researcher.nom ? "ring-2 ring-blue-500" : ""}`}
                    onClick={() => handleSelectResearcher(researcher.nom)}>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                          index === 0 ? "bg-yellow-100 text-yellow-700" : index === 1 ? "bg-gray-100 text-gray-600" :
                          index === 2 ? "bg-orange-100 text-orange-600" : "bg-blue-50 text-blue-600"}`}>
                          {index + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 text-sm truncate">{researcher.nom}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-gray-500">{researcher.nb_articles} articles</span>
                            {researcher.specialite_principale && (
                              <Badge className="text-xs bg-blue-50 text-blue-700 hover:bg-blue-50 px-1 py-0">
                                {researcher.specialite_principale}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          <div className="lg:col-span-2">
            {loadingProfile ? (
              <div className="space-y-4">
                <div className="h-32 bg-gray-100 rounded-xl animate-pulse" />
                <div className="h-48 bg-gray-100 rounded-xl animate-pulse" />
              </div>
            ) : selected ? (
              <div className="space-y-4">
                <Card className="border-0 shadow-sm">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center text-white text-2xl font-bold shrink-0">
                        {selected.nom[0]}
                      </div>
                      <div className="flex-1">
                        <h2 className="text-xl font-bold text-gray-900">{selected.nom}</h2>
                        <p className="text-gray-500 text-sm">{selected.nb_articles} articles publiés</p>
                        {selected.annees_actif?.length > 0 && (
                          <p className="text-xs text-gray-400 mt-1">Actif : {selected.annees_actif.join(", ")}</p>
                        )}
                        <div className="flex flex-wrap gap-1 mt-2">
                          {getSpecialites(selected.specialites).map((s) => (
                            <Badge key={s} className="bg-blue-100 text-blue-700 hover:bg-blue-100 text-xs">{s}</Badge>
                          ))}
                          {/* ✅ Badge ORCID */}
                          {loadingOrcid && (
                            <span className="text-xs text-gray-400 italic">Recherche ORCID...</span>
                          )}
                          {orcidProfile?.found && orcidProfile.orcid_url && (
                            <a href={orcidProfile.orcid_url} target="_blank" rel="noopener noreferrer"
                              className="flex items-center gap-1 bg-green-100 text-green-700 px-2 py-0.5 rounded-full text-xs font-medium hover:bg-green-200 transition-colors">
                              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm-1.5 5.5c.828 0 1.5.672 1.5 1.5S11.328 8.5 10.5 8.5 9 7.828 9 7s.672-1.5 1.5-1.5zm.5 3.5h-1v9h1V9zm3 0h-1v1.5c-.5-.9-1.4-1.5-2.5-1.5-1.9 0-3.5 1.6-3.5 3.5s1.6 3.5 3.5 3.5c1.1 0 2-.6 2.5-1.5V18h1V9z"/>
                              </svg>
                              ORCID {orcidProfile.orcid_id}
                            </a>
                          )}
                          {orcidProfile && !orcidProfile.found && (
                            <span className="text-xs text-gray-400 italic">Pas de profil ORCID</span>
                          )}
                        </div>
                        {/* ✅ Mots-clés ORCID */}
                        {orcidProfile?.found && orcidProfile.keywords && orcidProfile.keywords.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {orcidProfile.keywords.map((kw) => (
                              <span key={kw} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{kw}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* ✅ Publications ORCID */}
                {orcidProfile?.found && orcidProfile.publications_orcid && orcidProfile.publications_orcid.length > 0 && (
                  <Card className="border-0 shadow-sm border-l-4 border-l-green-500">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base font-semibold flex items-center gap-2">
                        <span className="text-green-600">🎓</span> Publications ORCID officielles
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {orcidProfile.publications_orcid.map((pub, i) => (
                        <div key={i} className="flex items-start gap-2 py-2 border-b border-gray-50 last:border-0">
                          <span className="text-xs text-gray-400 shrink-0 mt-1">#{i+1}</span>
                          <div>
                            <p className="text-sm text-gray-900 line-clamp-2">{pub.titre}</p>
                            <div className="flex gap-2 mt-1">
                              {pub.annee && <span className="text-xs text-gray-400">{pub.annee}</span>}
                              {pub.doi && (
                                <a href={`https://doi.org/${pub.doi}`} target="_blank" rel="noopener noreferrer"
                                  className="text-xs text-blue-500 hover:underline">DOI →</a>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {selected.top_journaux && Object.keys(selected.top_journaux).length > 0 && (
                  <Card className="border-0 shadow-sm">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base font-semibold">Journaux principaux</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {Object.entries(selected.top_journaux).slice(0, 3).map(([journal, count]) => (
                        <div key={journal} className="flex items-center justify-between">
                          <p className="text-xs text-gray-600 truncate flex-1 mr-2">{journal}</p>
                          <Badge className="bg-gray-100 text-gray-600 hover:bg-gray-100 shrink-0">
                            {count} article{count > 1 ? "s" : ""}
                          </Badge>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {selected.top_coauthors?.length > 0 && (
                  <Card className="border-0 shadow-sm">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base font-semibold">Top collaborateurs ({selected.top_coauthors.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        {selected.top_coauthors.slice(0, 10).map((collab) => (
                          <button key={collab.nom} onClick={() => handleSelectResearcher(collab.nom)}
                            className="px-3 py-1 bg-gray-100 hover:bg-blue-50 hover:text-blue-700 text-gray-700 text-xs rounded-full transition-colors">
                            {collab.nom} <span className="text-gray-400">({collab.nb_collaborations})</span>
                          </button>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {selected.articles?.length > 0 && (
                  <Card className="border-0 shadow-sm">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base font-semibold">Articles publiés</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {selected.articles.slice(0, 5).map((article) => (
                        <div key={article.pubmed_id} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                          <div className="w-6 h-6 bg-blue-50 rounded flex items-center justify-center shrink-0 mt-0.5">
                            <svg className="w-3 h-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm text-gray-900 leading-snug line-clamp-2">{article.titre}</p>
                            <div className="flex items-center gap-2 mt-1">
                              {article.annee && <span className="text-xs text-gray-400">{article.annee}</span>}
                              {article.specialite && (
                                <Badge className="text-xs bg-green-50 text-green-700 hover:bg-green-50 px-1 py-0">{article.specialite}</Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}
              </div>
            ) : (
              <Card className="border-0 shadow-sm h-full">
                <CardContent className="py-24 text-center">
                  <svg className="w-16 h-16 text-gray-200 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <h3 className="text-lg font-semibold text-gray-500">Sélectionnez un chercheur</h3>
                  <p className="text-gray-400 text-sm mt-2">Cliquez sur un chercheur pour voir son profil et ses collaborations</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}