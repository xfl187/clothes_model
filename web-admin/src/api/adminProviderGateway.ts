import { appConfig } from '../app/config';
import { AdminConfigurationApi } from './generated/apis/AdminConfigurationApi';
import { ProvidersApi } from './generated/apis/ProvidersApi';
import type { ProviderConfig } from './generated/models/ProviderConfig';
import type { ProviderConfigRequest } from './generated/models/ProviderConfigRequest';
import type { ProviderValidationResult } from './generated/models/ProviderValidationResult';
import { Configuration } from './generated/runtime';

export type { ProviderConfig, ProviderConfigRequest, ProviderValidationResult };

export interface ProviderAdminGateway {
  list(): Promise<ProviderConfig[]>;
  save(request: ProviderConfigRequest, providerId?: string): Promise<ProviderConfig>;
  validate(providerId: string): Promise<ProviderValidationResult>;
  enable(providerId: string): Promise<ProviderConfig>;
  setDefault(providerId: string): Promise<void>;
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

  async setDefault(providerId: string) {
    await this.configuration.updateDefaultProviderConfiguration({
      defaultProviderUpdateRequest: { providerId, confirmNewJobsOnly: true },
    });
  }
}
