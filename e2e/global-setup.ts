import { request } from '@playwright/test';
import { BASE_URL } from './env';
import { resetAndSeed } from './seed';

export default async function globalSetup(): Promise<void> {
    const api = await request.newContext({ baseURL: BASE_URL });
    try {
        await resetAndSeed(api);
    } finally {
        await api.dispose();
    }
}
