import { appConfig } from '../app/config';
import { AdminConfigurationApi } from './generated/apis/AdminConfigurationApi';
import { ProvidersApi } from './generated/apis/ProvidersApi';
import type { ProviderConfig } from './generated/models/ProviderConfig';
import type { ProviderConfigRequest } from './generated/models/ProviderConfigRequest';
import type { ProviderValidationResult } from './generated/models/ProviderValidationResult';
import { Configuration, ResponseError } from './generated/runtime';

export type { ProviderConfig, ProviderConfigRequest, ProviderValidationResult };

export async function providerAdminErrorMessage(error: unknown): Promise<string> {
  if (error instanceof ResponseError) {
    try {
      const problem = await error.response.clone().json() as { detail?: unknown };
      if (typeof problem.detail === 'string' && problem.detail.trim()) return problem.detail;
    } catch {
      // Fall through to the stable generic message for non-Problem responses.
    }
  }
  return '操作失败，请检查会话与配置后重试。';
}

export interface ProviderAdminGateway {
  list(): Promise<ProviderConfig[]>;
  save(request: ProviderConfigRequest, providerId?: string): Promise<ProviderConfig>;
  validate(providerId: string): Promise<ProviderValidationResult>;
  enable(providerId: string): Promise<ProviderConfig>;
  archive(providerId: string): Promise<ProviderConfig>;
  restore(providerId: string): Promise<ProviderConfig>;
  setDefault(providerId: string): Promise<void>;
  remove(providerId: string): Promise<void>;
}

export class OpenApiProviderAdminGateway implements ProviderAdminGateway {
  private readonly providers: ProvidersApi;
  private readonly configuration: AdminConfigurationApi;

  constructor(csrfToken: string) {
    const config = new Configuration({
      basePath: appConfig.apiBaseUrl,
      credentials: 'include',
      apiKey: (name) => name === 'X-CSRF-Token' ? csrfToken : '',
    });
    this.providers = new ProvidersApi(config);
    this.configuration = new AdminConfigurationApi(config);
  }

  async list() { return (await this.providers.listProviderConfigs()).items; }

  async save(request: ProviderConfigRequest, providerId?: string) {
    if (providerId) {
      return this.providers.updateProviderConfig({ providerId, providerConfigRequest: request });
    }
    return this.providers.createProviderConfig({
      providerConfigRequest: request,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async validate(providerId: string) {
    return this.providers.validateProviderConfig({
      providerId,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async enable(providerId: string) {
    return this.providers.enableProviderConfig({
      providerId,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async archive(providerId: string) {
    return this.providers.archiveProviderConfig({
      providerId,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async restore(providerId: string) {
    return this.providers.restoreProviderConfig({
      providerId,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async setDefault(providerId: string) {
    await this.configuration.updateDefaultProviderConfiguration({
      defaultProviderUpdateRequest: { providerId, confirmNewJobsOnly: true },
    });
  }

  async remove(providerId: string) {
    await this.providers.deleteProviderConfig({ providerId });
  }
}
