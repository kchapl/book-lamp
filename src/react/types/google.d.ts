// Google Identity Services (GSI) type definitions
declare namespace google.accounts.id {
    interface IdConfiguration {
        client_id: string;
        callback: (response: CredentialResponse) => void;
        auto_select?: boolean;
        cancel_on_tap_outside?: boolean;
        context?: string;
    }

    interface CredentialResponse {
        credential: string;
        select_by?: string;
    }

    interface GsiButtonConfiguration {
        type?: 'standard' | 'icon';
        theme?: 'outline' | 'filled_blue' | 'filled_black';
        size?: 'large' | 'medium' | 'small';
        text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
        shape?: 'rectangular' | 'pill' | 'circle' | 'square';
        logo_alignment?: 'left' | 'center';
        width?: number;
        locale?: string;
    }

    interface PromptMomentNotification {
        isNotDisplayed: () => boolean;
        isSkipped: () => boolean;
        isDismissed: () => boolean;
        getNotDisplayedReason: () => string;
        getSkippedReason: () => string;
        getDismissedReason: () => string;
    }

    function initialize(configuration: IdConfiguration): void;
    function renderButton(parent: HTMLElement, options: GsiButtonConfiguration): void;
    function prompt(momentListener?: (notification: PromptMomentNotification) => void): void;
    function disableAutoSelect(): void;
    function cancel(): void;
}

interface Window {
    google?: typeof google;
    GOOGLE_CLIENT_ID?: string;
}
