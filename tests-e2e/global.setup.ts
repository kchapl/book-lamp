import { request } from '@playwright/test';

export default async function globalSetup() {
    const baseURL = process.env.BASE_URL || 'http://127.0.0.1:5000';
    const req = await request.newContext({ baseURL });
    const res = await req.post('/test/reset');
    if (!res.ok()) {
        throw new Error(`Failed to reset DB: ${res.status()}`);
    }
    await req.dispose();
}


