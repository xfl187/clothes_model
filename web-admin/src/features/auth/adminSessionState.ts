import { createContext, useContext } from 'react';
import type { AdminSessionSnapshot } from '../../api/adminAuthGateway';

export type SessionState = 'loading' | 'anonymous' | 'authenticated';
export interface AdminSessionValue {
  state: SessionState;
  session?: AdminSessionSnapshot;
  login(token: string): Promise<void>;
  logout(): Promise<void>;
  expire(): void;
}

export const AdminSessionContext = createContext<AdminSessionValue | null>(null);

export function useAdminSession() {
  const value = useContext(AdminSessionContext);
  if (!value) throw new Error('AdminSessionProvider is missing');
  return value;
}
