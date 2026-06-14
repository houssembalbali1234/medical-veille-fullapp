export interface User {
    id: string;
    email: string;
    username: string;
    is_active: boolean;
  }
  
  export interface Article {
    id: string;
    titre: string;
    auteurs?: string;
    resume?: string;
    specialite?: string;
    source?: string;
    annee?: string;
    created_at: string;
  }
  
  export interface LoginRequest {
    email: string;
    password: string;
  }
  
  export interface RegisterRequest {
    username: string;
    email: string;
    password: string;
  }
  
  export interface TokenResponse {
    access_token: string;
    token_type: string;
  }