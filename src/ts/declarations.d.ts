// Type declarations for CSS modules
declare module '*.css' {
    const content: { [className: string]: string };
    export default content;
}

// Declare html5-qrcode module
declare module 'html5-qrcode' {
    export interface Html5QrcodeScanner {
        render(
            html5QrcodeError: (error: string) => void,
            html5QrcodeSuccess: (decodedText: string) => void
        ): void;
        clear(): void;
    }

    export interface Html5QrcodeConfig {
        fps?: number;
        qrbox?: number | { width: number; height: number };
        aspectRatio?: number;
        disableFlip?: boolean;
        preferredCamera?: 'environment' | 'user';
        formatsToSupport?: string[];
    }

    export class Html5Qrcode {
        constructor(elementId: string);
        start(
            cameraIdOrConfig: string | { facingMode: string },
            config: Html5QrcodeConfig,
            onSuccess: (decodedText: string) => void,
            onError: (error: string) => void
        ): Promise<void>;
        stop(): Promise<void>;
        clear(): void;
    }

    export class Html5QrcodeScanner {
        constructor(
            elementId: string,
            config: Html5QrcodeConfig,
            verbose: boolean
        );
        render(
            html5QrcodeError: (error: string) => void,
            html5QrcodeSuccess: (decodedText: string) => void
        ): void;
        clear(): void;
    }

    export function Html5QrcodeSupportedFormats(): string[];
}