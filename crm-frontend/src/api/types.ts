export interface RoleInfo {
  code: string;
  name: string;
  dataScope?: string;
}

export interface AuthUser {
  id: number;
  tenantId: number;
  username: string;
  displayName: string;
  deptId?: number | null;
  roles: RoleInfo[];
  permissions: string[];
  dataScope?: string;
}

export interface LoginResult {
  token: string;
  tokenType: string;
  expiresAt: string;
  user: AuthUser;
}

export interface ManualTocItem {
  level: number;
  id: string;
  title: string;
}

export interface UserManual {
  title: string;
  version: string;
  format: string;
  updatedAt: string;
  content: string;
  toc: ManualTocItem[];
}
