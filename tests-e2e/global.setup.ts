import { request } from '@playwright/test';

export default async function globalSetup() {
    const baseURL = process.env.BASE_URL || 'http://127.0.0.1:5000';
    const req = await request.newContext({ baseURL });

    try {
        // Try to reset the database up to 3 times
        let attempts = 0;
        while (attempts < 3) {
            try {
                // Reset the database
                const res = await req.post('/test/reset');
                if (!res.ok()) {
                    throw new Error(`Failed to reset DB: ${res.status()}`);
                }
                // If successful, break the retry loop
                break;
            } catch (error) {
                attempts++;
                if (attempts === 3) {
                    throw error;
                }
                // Wait a bit before retrying
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        // Authorize as the test user
        const loginRes = await req.get('/test/connect');
        if (!loginRes.ok()) {
            throw new Error(`Failed to authorize as test user: ${loginRes.status()}`);
        }
    } finally {
        await req.dispose();
    }
}


