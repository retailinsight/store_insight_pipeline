export interface Store {
  id: number;
  name: string;
  location?: string;
}

export interface AuthUser {
  id: string;
  username: string;
  role: string;
  roleId: number;
  storeId: number;
  store?: Store;
  stores: Store[];
  features: string[];
}

export interface DecodedToken {
  userId?: string;
  sub?: string;
  id?: string;
  username?: string;
  preferred_username?: string;
  name?: string;
  email?: string;
  roles?: string | string[];
  userType?: number;
  roleId?: number;
  storeId?: number;
  store?: Store;
  stores?: Store[];
  features?: string[];
  exp?: number;
  iat?: number;
  [key: string]: unknown;
}
