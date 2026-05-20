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

// Initialize Google One Tap with fallback
function initializeGoogleOneTap() {
    console.log('Initializing Google One Tap...');
    console.log('GOOGLE_CLIENT_ID:', window.GOOGLE_CLIENT_ID);
    
    if (!window.GOOGLE_CLIENT_ID) {
        console.error('GOOGLE_CLIENT_ID not found in window object');
        showManualSignIn();
        return;
    }
    
    if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
        try {
            google.accounts.id.initialize({
                client_id: window.GOOGLE_CLIENT_ID,
                callback: handleOneTapCredential,
                auto_prompt: false,
                cancel_on_tap_outside: false
            });
            console.log('Google One Tap initialized successfully');
            
            // Try to show One Tap, but handle FedCM errors
            try {
                google.accounts.id.prompt();
            } catch (error) {
                console.warn('FedCM error, falling back to manual sign-in:', error);
                showManualSignIn();
            }
        } catch (error) {
            console.error('Error initializing Google One Tap:', error);
            showManualSignIn();
        }
    } else {
        console.log('Google API not ready yet, retrying...');
        setTimeout(initializeGoogleOneTap, 100);
    }
}

// Show manual sign-in button as fallback
function showManualSignIn() {
    console.log('Showing manual sign-in option');
    const signInDiv = document.querySelector('.g_id_signin');
    if (signInDiv) {
        // Initialize manual sign-in button
        if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
            google.accounts.id.renderButton(signInDiv, {
                theme: 'outline',
                size: 'large',
                text: 'signin_with',
                shape: 'rectangular'
            });
        }
    }
}

// Make function globally available
window.handleOneTapCredential = handleOneTapCredential;

// Initialize when ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGoogleOneTap);
} else {
    initializeGoogleOneTap();
}
