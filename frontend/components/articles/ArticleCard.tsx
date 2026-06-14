"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Article } from "@/types";

const specialiteColors: Record<string, string> = {
  Oncologie: "bg-red-100 text-red-700",
  Cardiologie: "bg-pink-100 text-pink-700",
  Neurologie: "bg-purple-100 text-purple-700",
  Endocrinologie: "bg-yellow-100 text-yellow-700",
  Infectiologie: "bg-green-100 text-green-700",
  Immunologie: "bg-blue-100 text-blue-700",
  Néphrologie: "bg-orange-100 text-orange-700",
};

export default function ArticleCard({ article }: { article: Article }) {
  const router = useRouter();
  const colorClass = specialiteColors[article.specialite || ""] || "bg-blue-100 text-blue-700";

  const handleClick = () => {
    if (!article.id) return;

    // UUID avec tirets = PostgreSQL (PubMed scrape-and-process)
    if (article.id.includes("-")) {
      router.push(`/dashboard/articles/${article.id}`);
    } else {
      // ID hex sans tirets = MongoDB (bioRxiv / Europe PMC)
      router.push(`/dashboard/articles/mongo/${article.id}`);
    }
  };

  return (
    <Card
      className="border border-gray-100 transition-all hover:shadow-md hover:border-blue-200 cursor-pointer"
      onClick={handleClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
            {article.titre}
          </h3>
          {article.specialite && (
            <span className={`text-xs font-medium px-2 py-1 rounded-full shrink-0 ${colorClass}`}>
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
          {article.auteurs && (
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <span className="truncate max-w-[200px]">{article.auteurs}</span>
            </span>
          )}
          {article.annee && (
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {article.annee}
            </span>
          )}
          {article.source && (
            <Badge variant="outline" className="text-xs">
              {article.source}
            </Badge>
          )}
        </div>
        <p className="text-xs text-blue-500 mt-1">Cliquez pour voir le détail →</p>
      </CardContent>
    </Card>
  );
}