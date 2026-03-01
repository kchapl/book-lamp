# book-lamp

A personal reading history tracker using Google Sheets for storage.

## Setup

1. Install backend dependencies: `poetry install`
2. Install frontend dependencies: `npm install`
3. Compile TypeScript: `npm run build`
4. Create `.env` file with required variables:
   ```
   FLASK_ENV=development
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

