import { useEffect, useMemo, useState } from 'react';
import type { PropsWithChildren } from 'react';
import type { AdminSessionSnapshot } from '../../api/adminAuthGateway';
import { AdminAuthError, AdminAuthGateway } from '../../api/adminAuthGateway';
import { AdminSessionContext } from './adminSessionState';
import type { AdminSessionValue, SessionState } from './adminSessionState';

export function AdminSessionProvider({ children }: PropsWithChildren) {
  const [gateway] = useState(() => new AdminAuthGateway());
  const [session, setSession] = useState<AdminSessionSnapshot>();
  const [state, setState] = useState<SessionState>('loading');

  useEffect(() => {
    void gateway.restore().then(value => { setSession(value); setState('authenticated'); })
      .catch(error => { if (error instanceof AdminAuthError) setState('anonymous'); else setState('anonymous'); });
  }, [gateway]);

  const value = useMemo<AdminSessionValue>(() => ({
    state,
    session,
    async login(token) {
      const restored = await gateway.login(token);
      setSession(restored); setState('authenticated');
    },
    async logout() { await gateway.logout(); setSession(undefined); setState('anonymous'); },
  }), [gateway, session, state]);
  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}
