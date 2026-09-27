import React, { useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppContext } from '../App';
import { authenticateWithGoogle } from '../services/api';

interface GoogleAuthProps {
    onSuccess?: () => void;
    onError?: (error: string) => void;
}

export const GoogleAuth: React.FC<GoogleAuthProps> = ({ onSuccess, onError }) => {
    const { googleClientId, setIsAuthorized } = useContext(AppContext);
    const [loading, setLoading] = useState(false);
    const [authError, setAuthError] = useState<string | null>(null);
    const buttonContainerRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (!googleClientId) {
            return;
        }

        const handleCredential = async (response: { credential: string }) => {
            setLoading(true);
            setAuthError(null);
            try {
                const res = await authenticateWithGoogle(response.credential);
                if (res.ok || res.success) {
                    setIsAuthorized(true);
                    if (onSuccess) {
                        onSuccess();
                    } else {
                        navigate('/books');
                    }
                } else {
                    const msg = res.error || 'Authentication failed. Please try again.';
                    setAuthError(msg);
                    if (onError) onError(msg);
                }
            } catch (err: any) {
                const msg = err?.message || 'Error signing in with Google';
                setAuthError(msg);
                if (onError) onError(msg);
            } finally {
                setLoading(false);
            }
        };

        const setupGoogle = () => {
            if (!window.google?.accounts?.id) {
                return;
            }

            window.google.accounts.id.initialize({
                client_id: googleClientId,
                callback: handleCredential,
                auto_select: false,
                cancel_on_tap_outside: false,
            });

            if (buttonContainerRef.current) {
                buttonContainerRef.current.innerHTML = '';
                window.google.accounts.id.renderButton(buttonContainerRef.current, {
                    type: 'standard',
                    theme: 'outline',
                    size: 'large',
                    text: 'signin_with',
                    shape: 'rectangular',
                });
            }

            window.google.accounts.id.prompt();
        };

        if (window.google?.accounts?.id) {
            setupGoogle();
        } else {
            // Dynamically load Google GSI script if not present
            const scriptId = 'google-gsi-script';
            let script = document.getElementById(scriptId) as HTMLScriptElement | null;
            if (!script) {
                script = document.createElement('script');
                script.id = scriptId;
                script.src = 'https://accounts.google.com/gsi/client';
                script.async = true;
                script.defer = true;
                script.onload = () => setupGoogle();
                document.body.appendChild(script);
            } else {
                script.addEventListener('load', setupGoogle);
            }
        }
    }, [googleClientId, navigate, onSuccess, onError, setIsAuthorized]);

    return (
        <div className="google-auth-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', marginTop: '1rem' }}>
            {authError && (
                <div className="auth-error-banner" style={{ color: '#dc2626', fontSize: '0.9rem' }}>
                    {authError}
                </div>
            )}
            {loading && <div className="spinner">Verifying authentication...</div>}
            <div ref={buttonContainerRef} id="google-signin-btn" />
        </div>
    );
};

export default GoogleAuth;
