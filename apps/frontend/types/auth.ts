export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
};

export type CurrentUser = User & {
  organization: Organization;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};
