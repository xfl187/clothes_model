import { useEffect, useMemo, useState } from 'react';
import type { PropsWithChildren } from 'react';
import type { AdminSessionSnapshot } from '../../api/adminAuthGateway';
import { AdminAuthGateway } from '../../api/adminAuthGateway';
import { setCsrfToken } from '../../api/adminApi';
import { AdminSessionContext } from './adminSessionState';
import type { AdminSessionValue, SessionState } from './adminSessionState';

export function AdminSessionProvider({ children }: PropsWithChildren) {
  const [gateway] = useState(() => new AdminAuthGateway());
  const [session, setSession] = useState<AdminSessionSnapshot>();
  const [state, setState] = useState<SessionState>('loading');

  useEffect(() => {
    void gateway.restore()
      .then(value => { setCsrfToken(value.csrfToken); setSession(value); setState('authenticated'); })
      .catch(() => { setCsrfToken(''); setState('anonymous'); });
  }, [gateway]);

  const value = useMemo<AdminSessionValue>(() => ({
    state,
    session,
    async login(token) {
      const restored = await gateway.login(token);
      setCsrfToken(restored.csrfToken);
      setSession(restored); setState('authenticated');
    },
    async logout() {
      await gateway.logout();
      setCsrfToken('');
      setSession(undefined); setState('anonymous');
    },
    expire() {
      setCsrfToken('');
      setSession(undefined); setState('anonymous');
    },
  }), [gateway, session, state]);
  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}
