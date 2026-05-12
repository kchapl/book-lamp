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
            // Authentication successful, reload page to show authenticated state
            window.location.reload();
        } else {
            const error = await res.json();
            console.error('Authentication failed:', error);
            // Show error message to user
            alert('Authentication failed: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Network error during authentication:', error);
        alert('Network error during authentication. Please try again.');
    }
}

// Make the function globally available
window.handleOneTapCredential = handleOneTapCredential;
