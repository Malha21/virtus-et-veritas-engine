export type UserRole = "admin" | "member";

export type AdminUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
};

export type AdminUserCreatePayload = {
  name: string;
  email: string;
  password: string;
  role: UserRole;
};

export type UserAICredential = {
  id: string;
  provider_type: "openai" | "anthropic" | "gemini";
  key_last_four: string;
  created_at: string;
  updated_at: string;
};
