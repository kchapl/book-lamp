# Deployment Guide

## Render Deployment

### Required Environment Variables

Set the following environment variables in your Render web service:

#### Google OAuth Configuration
- `GOOGLE_CLIENT_ID` - Your Google OAuth 2.0 Client ID
- `GOOGLE_CLIENT_SECRET` - Your Google OAuth 2.0 Client Secret

These credentials are obtained from the [Google Cloud Console](https://console.cloud.google.com/):
1. Go to APIs & Services > Credentials
2. Create OAuth 2.0 Client ID (or use existing)
3. Add your Render URL to authorized redirect URIs: `https://your-app.onrender.com/authorize`

#### Flask Configuration
- `SECRET_KEY` - A random secret key for Flask session management (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- `FLASK_ENV` - Set to `production` for production deployment

### Security Notes

- OAuth tokens are managed securely by the application and are NOT stored as local files.
- Client ID and Secret are read from environment variables at runtime
- This follows the [12-factor app](https://12factor.net/config) methodology for configuration management
- Never commit `.env` file to version control

### Build Configuration

**Build Command:**
```bash
npm ci && npm run build && pip install poetry && poetry install --without dev
```

**Start Command:**
```bash
poetry run gunicorn book_lamp.app:app
```

### First-Time Setup

After deployment:
1. Visit your app URL
2. Click "Authorize Google Sheets Access"
3. Complete the OAuth flow
4. The app will securely hold your access/refresh tokens via the persistent storage mechanism

### Troubleshooting

If you see "Authorization Error" after deployment:
1. Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in Render environment variables
2. Ensure your Render URL is added to authorized redirect URIs in Google Cloud Console
3. Verify your authorization status and re-authorize if needed
