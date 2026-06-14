import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
};

export const articlesApi = {
  getAll: (params?: { page?: number; limit?: number; specialite?: string }) =>
    api.get("/articles-pg/", { params }),
  search: (keyword: string) =>
    api.get("/articles-pg/search", { params: { keyword } }),
  scrapeAndProcess: (q: string, maxResults = 10) =>
    api.post("/articles-pg/scrape-and-process", null, {
      params: { q, max_results: maxResults },
    }),
};

export const articlesMongoApi = {
  getAll: (params?: { limit?: number; skip?: number }) =>
    api.get("/articles/", { params }),

  // Recherche Elasticsearch avec size configurable
  search: (keyword: string) =>
    api.get("/articles/search/elastic", { params: { q: keyword } }),

  // ✅ searchAll — retourne 30 résultats pour avoir toutes les sources
  searchAll: (keyword: string, size: number = 100) =>
    api.get("/articles/search/elastic", { params: { q: keyword, size } }),

  searchSemantic: (keyword: string) =>
    api.get("/articles/search/semantic", { params: { q: keyword } }),
};

export const alertsApi = {
  getAll: () => api.get("/alerts/"),
  create: (data: { mot_cle?: string; auteur?: string; actif?: boolean }) =>
    api.post("/alerts/", data),
  delete: (id: string) => api.delete(`/alerts/${id}`),
};