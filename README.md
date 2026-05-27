# book-lamp

A personal reading history tracker.

## Setup

This project uses [mise](https://mise.jdx.dev/) to manage tool versions (Python, Node, uv).

1. Install tools: `mise install`
2. Install backend dependencies: `uv sync`
3. Install frontend dependencies: `npm install`
3. Compile TypeScript: `npm run build`
4. Create `.env` file with required variables:
   ```
   FLASK_DEBUG=True
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret

   SECRET_KEY=your_secret_key
   ```
5. Run the app: `uv run flask --app book_lamp.app run`

## Testing

Run backend unit tests:
```bash
uv run pytest
```

Run frontend unit tests:
```bash
npm test
```

