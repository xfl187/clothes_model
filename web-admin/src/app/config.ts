import { z } from 'zod';

const environmentSchema = z.object({
  VITE_API_BASE_URL: z.string().trim().optional(),
});

const environment = environmentSchema.parse(import.meta.env);

export interface AppConfig {
  apiBaseUrl: string;
}

export const appConfig: AppConfig = {
  apiBaseUrl: environment.VITE_API_BASE_URL?.replace(/\/+$/, '') ?? '',
};
