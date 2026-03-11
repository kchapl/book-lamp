import { describe, it, expect, vi, beforeEach } from 'vitest';
import { initBarcodeScanner } from '../barcode-scanner.js';

// Mock Html5Qrcode
const mockStart = vi.fn().mockResolvedValue(undefined);
const mockStop = vi.fn().mockResolvedValue(undefined);
const mockGetCameras = vi.fn().mockResolvedValue([{ id: '1', label: 'Camera 1' }]);

vi.stubGlobal('Html5Qrcode', class {
    isScanning = true;
    constructor(_id: string) {}
    start = mockStart;
    stop = mockStop;
    static getCameras = mockGetCameras;
});

describe('barcode-scanner', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <button id="scan-barcode-btn" class="hidden"></button>
            <div id="barcode-scanner-container" class="hidden"></div>
            <div id="scanner-controls" class="hidden">
                <button id="stop-scan-btn"></button>
            </div>
            <input type="text" id="isbn">
        `;
        vi.clearAllMocks();
    });

    it('shows scan button if cameras are supported', async () => {
        await initBarcodeScanner();
        // The initBarcodeScanner has a 500ms delay if Html5Qrcode is not immediately ready
        // In our test it's stubbed globally so it should be ready, but let's wait a bit.
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const scanBtn = document.getElementById('scan-barcode-btn');
        expect(scanBtn?.classList.contains('hidden')).toBe(false);
    });

    it('starts scanner when scan button is clicked', async () => {
        await initBarcodeScanner();
        await new Promise(resolve => setTimeout(resolve, 100));

        const scanBtn = document.getElementById('scan-barcode-btn');
        scanBtn?.click();

        expect(mockStart).toHaveBeenCalled();
        expect(scanBtn?.classList.contains('hidden')).toBe(true);
        expect(document.getElementById('barcode-scanner-container')?.classList.contains('hidden')).toBe(false);
    });

    it('stops scanner when stop button is clicked', async () => {
        await initBarcodeScanner();
        await new Promise(resolve => setTimeout(resolve, 100));

        const scanBtn = document.getElementById('scan-barcode-btn');
        scanBtn?.click();
        
        const stopBtn = document.getElementById('stop-scan-btn');
        stopBtn?.click();

        // Wait for async stopScanning to finish
        await new Promise(resolve => setTimeout(resolve, 100));

        expect(mockStop).toHaveBeenCalled();
        expect(scanBtn?.classList.contains('hidden')).toBe(false);
    });
});

