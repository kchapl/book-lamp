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
