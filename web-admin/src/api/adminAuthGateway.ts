import { appConfig } from '../app/config';
import { AuthenticationApi } from './generated/apis/AuthenticationApi';
import { Configuration, FetchError, ResponseError } from './generated/runtime';

export type AuthFailure = 'invalid' | 'throttled' | 'offline' | 'expired' | 'unknown';
export interface AdminSessionSnapshot { authenticated: true; expiresAt: Date; csrfToken: string; }

export class AdminAuthError extends Error {
  constructor(readonly kind: AuthFailure) { super(kind); }
}

export class AdminAuthGateway {
  private csrf = '';
  private readonly api = new AuthenticationApi(new Configuration({
    basePath: appConfig.apiBaseUrl,
    credentials: 'include',
    apiKey: (name) => name === 'X-CSRF-Token' ? this.csrf : '',
  }));

  async login(adminToken: string): Promise<AdminSessionSnapshot> {
    try {
      const session = await this.api.createAdminSession({ adminSessionCreateRequest: { adminToken } });
      this.csrf = session.csrfToken;
      return { authenticated: true, expiresAt: session.expiresAt, csrfToken: session.csrfToken };
    } catch (error) { throw await this.classify(error, false); }
  }

  async restore(): Promise<AdminSessionSnapshot> {
    try {
      const session = await this.api.getAdminSession();
      this.csrf = session.csrfToken;
      return { authenticated: true, expiresAt: session.expiresAt, csrfToken: session.csrfToken };
    } catch (error) { throw await this.classify(error, true); }
  }

  async logout(): Promise<void> {
    try { await this.api.deleteAdminSession(); }
    finally { this.csrf = ''; }
  }

  private async classify(error: unknown, restoring: boolean): Promise<AdminAuthError> {
    if (error instanceof FetchError) return new AdminAuthError('offline');
    if (error instanceof ResponseError) {
      if (error.response.status === 429) return new AdminAuthError('throttled');
      if (error.response.status === 401) return new AdminAuthError(restoring ? 'expired' : 'invalid');
    }
    return new AdminAuthError('unknown');
  }
}
