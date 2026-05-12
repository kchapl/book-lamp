# Deployment Guide

## Render Deployment

### Required Environment Variables

Set the following environment variables in your Render web service:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string from Neon |
| `SECRET_KEY` | Flask session secret (generate with `python -c "import secrets; print(secrets.token_hex(32))"` ) |
| `FLASK_DEBUG` | Set to `False` for production deployment (set to `True` for development debugging - doesn't affect authentication) |
| `GOOGLE_CLIENT_ID` | Google One Tap Client ID (optional, for login) |
| `LLM_API_KEY` | OpenAI API key (optional, for AI features) |

### Neon Database Setup

1. Create a Neon account at https://neon.tech
2. Create a new project
3. Copy the connection string (starts with `postgresql://`)
4. Set `DATABASE_URL` in Render environment variables
5. Run `alembic upgrade head` to initialize the database schema

### Google One Tap Setup (Optional)

If you want Google login functionality:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 Client ID
3. Add your Render URL to authorized origins
4. Set `GOOGLE_CLIENT_ID` in environment variables

### Security Notes

- Database credentials are read from environment variables at runtime
- This follows the [12-factor app](https://12factor.net/config) methodology
- Never commit `.env` file to version control

### Build Configuration

**Build Command:**
```bash
npm ci && npm run build && pip install poetry && poetry install --without dev && poetry run alembic upgrade head
```

**Start Command:**
```bash
poetry run gunicorn book_lamp.app:app
```

### First-Time Setup

After deployment:
1. Visit your app URL
2. The app should work immediately with PostgreSQL storage
3. If using Google One Tap, you can click the Google login button
4. Start adding books via the UI

### Troubleshooting

**Database Connection Errors:**
1. Verify `DATABASE_URL` is set correctly in Render environment variables
2. Ensure your Neon project is active
3. Check that `alembic upgrade head` ran successfully during build

**Google One Tap Issues:**
1. Verify `GOOGLE_CLIENT_ID` is set in environment variables
2. Ensure your Render URL is added to authorized origins in Google Cloud Console
3. Check browser console for JavaScript errors

**General Issues:**
1. Check Render build logs for any errors during `alembic upgrade head`
2. Verify all required environment variables are set
3. Check application logs for connection errors
