// Google One Tap authentication handler
async function handleOneTapCredential(response) {
    try {
        const res = await fetch('/api/auth/google', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                credential: response.credential
            })
        });

        if (res.ok) {
            window.location.reload();
        } else {
            const error = await res.json();
            console.error('Authentication failed:', error);
            alert('Authentication failed: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Network error during authentication:', error);
        alert('Network error during authentication. Please try again.');
    }
}

// Initialise Google Sign-In programmatically
function initialiseGoogleSignIn() {
    console.log('Initialising Google Sign-In...');
    console.log('GOOGLE_CLIENT_ID:', window.GOOGLE_CLIENT_ID);

    if (!window.GOOGLE_CLIENT_ID) {
        console.error('GOOGLE_CLIENT_ID not found in window object');
        showFallbackSignIn();
        return;
    }

    // Wait for Google API to be ready
    if (typeof google === 'undefined' || !google.accounts || !google.accounts.id) {
        console.log('Google API not ready yet, retrying...');
        setTimeout(initialiseGoogleSignIn, 100);
        return;
    }

    // Determine the current origin for logging
    const currentOrigin = window.location.origin;
    console.log('Current origin:', currentOrigin);

    try {
        // Programmatic initialisation with client configuration
        google.accounts.id.initialize({
            client_id: window.GOOGLE_CLIENT_ID,
            callback: handleOneTapCredential,
            auto_prompt: false,
            cancel_on_tap_outside: false,
            // Listen for One Tap display events to diagnose issues
            moment_listener: function(notification) {
                const reason = notification.getMomentNotGoingVisibleReason();
                const detail = notification.getDetailedNotGoingVisibleReason();
                
                if (reason === 'DISPLAYED') {
                    console.log('One Tap displayed successfully');
                } else if (reason === 'NOT_DISPLAYED') {
                    console.warn('One Tap not displayed. Reason:', detail);
                    
                    // Specific diagnostics for common issues
                    if (detail === 'OPTIMUS_TAP_ALREADY_SIGNED_IN') {
                        console.log('(User is already signed in to Google)');
                    } else if (detail === 'FEDCM_API-disabled') {
                        console.log('(FedCM disabled - check browser privacy settings)');
                    } else if (detail === 'INVALID_CLIENT_ID') {
                        console.error('(INVALID_CLIENT_ID - check Google Cloud Console client ID)');
                    } else if (detail.startsWith('POPUP_BLOCKED') || detail === 'WINDOW_BLOCKED') {
                        console.log('(Popup blocked - check browser popup blocker)');
                    } else if (detail.includes('ORIGIN')) {
                        console.error('(ORIGIN_MISMATCH - add ' + currentOrigin + ' to Authorized JavaScript origins in Google Cloud Console)');
                        console.error('Go to: Google Cloud Console → APIs & Services → Credentials → OAuth Client → Authorized JavaScript origins');
                    } else {
                        console.log('(Unknown reason - check browser console for more details)');
                    }
                } else {
                    console.log('One Tap notification:', reason, detail);
                }
            }
        });
        console.log('Google Sign-In initialised successfully');

        // Render the standard sign-in button inside custom container
        renderGoogleButton();

        // Asynchronously overlay One Tap as a helper flow
        overlayOneTap();
    } catch (error) {
        console.error('Error initialising Google Sign-In:', error);
        showFallbackSignIn();
    }
}

// Render the standard Google sign-in button in custom container
function renderGoogleButton() {
    const buttonContainer = document.getElementById('google-signin-btn');
    if (!buttonContainer) {
        console.error('Button container #google-signin-btn not found');
        return;
    }

    if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
        google.accounts.id.renderButton(buttonContainer, {
            theme: 'outline',
            size: 'large',
            text: 'signin_with',
            shape: 'rectangular'
        });
        console.log('Google sign-in button rendered');
    }
}

// Overlay One Tap prompt as a helper flow
function overlayOneTap() {
    // Delay One Tap to ensure button is visible first
    setTimeout(() => {
        try {
            google.accounts.id.prompt();
            console.log('One Tap prompt shown as helper flow');
        } catch (error) {
            // One Tap may fail silently (e.g., FedCM blocked)
            console.warn('One Tap prompt skipped:', error.message);
        }
    }, 500);
}

// Fallback for when Google API fails
function showFallbackSignIn() {
    const buttonContainer = document.getElementById('google-signin-btn');
    if (!buttonContainer) return;

    if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
        google.accounts.id.renderButton(buttonContainer, {
            theme: 'outline',
            size: 'large',
            text: 'signin_with',
            shape: 'rectangular'
        });
    }
}

// Make functions globally available
window.handleOneTapCredential = handleOneTapCredential;

// Initialise when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialiseGoogleSignIn);
} else {
    initialiseGoogleSignIn();
}
