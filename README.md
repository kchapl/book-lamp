# book-lamp

A personal reading history tracker using Google Sheets for storage.

**Security note:** the app only requests the `https://www.googleapis.com/auth/drive.file` scope
to find and manage the specific spreadsheet across sessions. No broader access is required.

## Setup

This project uses [mise](https://mise.jdx.dev/) to manage tool versions (Python, Node, Poetry).

1. Install tools: `mise install`
2. Install backend dependencies: `poetry install`
3. Install frontend dependencies: `npm install`
3. Compile TypeScript: `npm run build`
4. Create `.env` file with required variables:
   ```
   FLASK_DEBUG=True
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret

   SECRET_KEY=your_secret_key
   ```
5. Run the app: `poetry run flask --app book_lamp.app run`

## Testing

Run backend unit tests:
```bash
poetry run pytest
```

Run frontend unit tests:
```bash
npm test
```

