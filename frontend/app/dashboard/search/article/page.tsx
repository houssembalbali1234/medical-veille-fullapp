"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function SearchArticleRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pubmed_id = searchParams.get("pubmed_id");
  const source = searchParams.get("source");

  useEffect(() => {
    if (!pubmed_id) {
      router.push("/dashboard/search");
      return;
    }

    const redirect = async () => {
      try {
        if (source === "biorxiv" || source === "europe_pmc") {
          // Chercher dans MongoDB par pubmed_id
          const res = await api.get(`/articles/${pubmed_id}`);
          if (res.data?.id) {
            router.replace(`/dashboard/articles/mongo/${res.data.id}`);
          } else {
            router.push("/dashboard/search");
          }
        } else {
          // PubMed → chercher UUID PostgreSQL
          const res = await api.get(`/articles-pg/?limit=200`);
          const found = res.data?.find((a: any) => a.pubmed_id === pubmed_id);
          if (found?.id) {
            router.replace(`/dashboard/articles/${found.id}`);
          } else {
            router.push("/dashboard/search");
          }
        }
      } catch (err) {
        console.error(err);
        router.push("/dashboard/search");
      }
    };

    redirect();
  }, [pubmed_id, source, router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-600 border-t-transparent" />
        <p className="text-gray-500 text-sm">Chargement de l&apos;article...</p>
      </div>
    </div>
  );
}