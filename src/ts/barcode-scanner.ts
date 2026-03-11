/**
 * Barcode Scanner
 * Integrates html5-qrcode for mobile ISBN scanning.
 */

// Since we're loading the library via CDN in the template for simplicity 
// in this non-bundled environment, we declare the global.
declare const Html5Qrcode: any;

/**
 * Initialises the barcode scanner functionality on the Add Book page.
 */
export async function initBarcodeScanner(): Promise<void> {
    const scanButton = document.getElementById('scan-barcode-btn');
    const scannerContainer = document.getElementById('barcode-scanner-container');
    const scannerControls = document.getElementById('scanner-controls');
    const stopScanButton = document.getElementById('stop-scan-btn');
    const isbnInput = document.getElementById('isbn') as HTMLInputElement;

    if (!scanButton || !scannerContainer || !scannerControls || !stopScanButton || !isbnInput) return;

    // 1. Detect device camera support
    // We only show the scan button if the browser supports camera access
    try {
        const hasCameras = await checkCameraSupport();
        if (hasCameras) {
            scanButton.classList.remove('hidden');
        }
    } catch (err) {
        console.warn('Barcode scanner: Camera support check failed', err);
    }

    let html5QrCode: any = null;

    const startScanning = async () => {
        try {
            if (!html5QrCode) {
                html5QrCode = new Html5Qrcode("barcode-scanner-container");
            }

            scanButton.classList.add('hidden');
            scannerContainer.classList.remove('hidden');
            scannerControls.classList.remove('hidden');

            await html5QrCode.start(
                { facingMode: "environment" },
                {
                    fps: 10,
                    qrbox: { width: 280, height: 160 } // Rectangular for barcodes
                },
                (decodedText: string) => {
                    // SUCCESS: Found a barcode (usually EAN-13 for books)
                    isbnInput.value = decodedText;
                    stopScanning();
                    
                    // Add visual feedback to input
                    isbnInput.classList.add('success-flash');
                    setTimeout(() => isbnInput.classList.remove('success-flash'), 2000);
                },
                (_errorMessage: string) => {
                    // Scanning... ignore noise
                }
            );
        } catch (err) {
            console.error('Failed to start barcode scanner', err);
            alert('Could not start camera. Please ensure you have granted camera permissions in your browser settings.');
            stopScanning();
        }
    };

    const stopScanning = async () => {
        if (html5QrCode && html5QrCode.isScanning) {
            try {
                await html5QrCode.stop();
            } catch (err) {
                console.error('Error stopping scanner', err);
            }
        }
        scannerContainer.classList.add('hidden');
        scannerControls.classList.add('hidden');
        scanButton.classList.remove('hidden');
    };

    scanButton.addEventListener('click', startScanning);
    stopScanButton.addEventListener('click', stopScanning);
}

/**
 * Checks if the device has at least one camera.
 */
async function checkCameraSupport(): Promise<boolean> {
    // If library not yet loaded, wait once
    if (typeof Html5Qrcode === 'undefined') {
        await new Promise(resolve => setTimeout(resolve, 500));
        if (typeof Html5Qrcode === 'undefined') return false;
    }
    
    try {
        const devices = await Html5Qrcode.getCameras();
        return devices && devices.length > 0;
    } catch (e) {
        return false;
    }
}

// Auto-init for the Add Book page
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBarcodeScanner);
    } else {
        initBarcodeScanner();
    }
}
