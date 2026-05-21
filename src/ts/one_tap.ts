/**
 * Handles the Google One Tap credential callback.
 * @param response The response from Google One Tap containing the JWT credential.
 */
async function handleOneTapCredential(response: { credential: string }): Promise<void> {
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
    } else {
      const data = await res.json();
      throw new Error(data.error || "Authentication failed");
    }
  } catch (err: any) {
    console.error("One Tap login failed:", err);
    alert("Failed to sign in with Google: " + err.message);
  }
}

// Expose to global scope for the GSI callback
(window as any).handleOneTapCredential = handleOneTapCredential;

// Initialize Google One Tap when the script loads
function initializeGoogleOneTap(): void {
  const clientId = (window as any).GOOGLE_CLIENT_ID;
  if (!clientId) {
    console.error("GOOGLE_CLIENT_ID is not set");
    return;
  }

  // Wait for the Google Identity Services library to load
  const checkGsiLoaded = setInterval(() => {
    if ((window as any).google && (window as any).google.accounts) {
      clearInterval(checkGsiLoaded);

      (window as any).google.accounts.id.initialize({
        client_id: clientId,
        callback: handleOneTapCredential,
        auto_select: false,
        cancel_on_tap_outside: false,
      });

      // Display the One Tap prompt
      (window as any).google.accounts.id.prompt((notification: any) => {
        if (notification.isNotDisplayed()) {
          console.log("One Tap not displayed:", notification.getNotDisplayedReason());
        } else if (notification.isSkipped()) {
          console.log("One Tap skipped:", notification.getSkippedReason());
        }
      });
    }
  }, 100);

  // Timeout after 5 seconds
  setTimeout(() => {
    clearInterval(checkGsiLoaded);
    if (!(window as any).google || !(window as any).google.accounts) {
      console.error("Google Identity Services library failed to load");
    }
  }, 5000);
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeGoogleOneTap);
} else {
  initializeGoogleOneTap();
}
