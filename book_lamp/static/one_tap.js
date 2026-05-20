"use strict";
/**
 * Handles the Google One Tap credential callback.
 * @param response The response from Google One Tap containing the JWT credential.
 */
async function handleOneTapCredential(response) {
    const credential = response.credential;
    try {
        const res = await fetch("/api/auth/google", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ credential }),
        });
        if (res.ok) {
            // Refresh the page or redirect to bookshelf
            window.location.href = "/books";
        }
        else {
            const data = await res.json();
            throw new Error(data.error || "Authentication failed");
        }
    }
    catch (err) {
        console.error("One Tap login failed:", err);
        alert("Failed to sign in with Google: " + err.message);
    }
}
// Show manual sign-in button as fallback/default
function showManualSignIn() {
    console.log("Showing manual sign-in option");
    const signInDiv = document.getElementById("google-signin-btn");
    if (signInDiv && typeof google !== "undefined" && google.accounts && google.accounts.id) {
        google.accounts.id.renderButton(signInDiv, {
            theme: "outline",
            size: "large",
            text: "signin_with",
            shape: "rectangular",
        });
    }
}
// Initialize Google One Tap with standard button fallback
function initializeGoogleOneTap() {
    console.log("Initializing Google One Tap...");
    console.log("GOOGLE_CLIENT_ID:", window.GOOGLE_CLIENT_ID);
    if (!window.GOOGLE_CLIENT_ID) {
        console.error("GOOGLE_CLIENT_ID not found in window object");
        showManualSignIn();
        return;
    }
    if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
        try {
            google.accounts.id.initialize({
                client_id: window.GOOGLE_CLIENT_ID,
                callback: handleOneTapCredential,
                auto_select: false,
                cancel_on_tap_outside: false,
            });
            console.log("Google One Tap initialized successfully");
            // Always render the standard button so the user can always sign in manually
            showManualSignIn();
            // Also attempt to show the One Tap floating prompt
            google.accounts.id.prompt((notification) => {
                if (notification.isNotDisplayed()) {
                    console.log("One Tap prompt not displayed:", notification.getNotDisplayedReason());
                }
                else if (notification.isSkippedMoment()) {
                    console.log("One Tap prompt skipped:", notification.getSkippedReason());
                }
                else if (notification.isDismissedMoment()) {
                    console.log("One Tap prompt dismissed:", notification.getDismissedReason());
                }
            });
        }
        catch (error) {
            console.error("Error initializing Google One Tap:", error);
            showManualSignIn();
        }
    }
    else {
        console.log("Google API not ready yet, retrying...");
        setTimeout(initializeGoogleOneTap, 100);
    }
}
// Expose to global scope for the GSI callback
window.handleOneTapCredential = handleOneTapCredential;
// Initialize when ready
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeGoogleOneTap);
}
else {
    initializeGoogleOneTap();
}
