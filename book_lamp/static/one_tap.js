// Google One Tap authentication handler
async function handleOneTapCredential(response) {
  const res = await fetch("/api/auth/google", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({credential: response.credential})
  });
  if (res.ok) {
    window.location.reload();
  } else {
    alert("Authentication failed");
  }
}
window.handleOneTapCredential = handleOneTapCredential;
