# WhatToWatch

A sophisticated Telegram bot for personalized movie recommendations powered by AI and semantic embeddings.

## Overview

WhatToWatch is an intelligent movie recommendation system that learns your taste through reviews and ratings, providing personalized suggestions using vector embeddings and AI-powered explanations. The bot integrates with TMDB (The Movie Database) for comprehensive movie data and supports importing your Letterboxd history.

### Key Features

- **Personalized Recommendations**: Get tailored movie suggestions based on your viewing history and preferences
- **AI-Powered Explanations**: Each recommendation comes with an explanation of why it matches your taste
- **Semantic Understanding**: Uses OpenAI embeddings to understand the semantic meaning of your reviews and preferences
- **Letterboxd Import**: Import your entire viewing history from Letterboxd
- **Taste Profile**: Automatically builds and maintains a profile of your movie preferences
- **Avoidance Patterns**: Set topics or themes you want to avoid in recommendations
- **Rate Limiting**: Built-in rate limiting to prevent API abuse
- **Two Recommendation Engines**:
  - **v0**: Traditional recommendation based on genres, countries, and decades
  - **v1**: Advanced vector-based recommendations with diversity optimization (MMR algorithm)

## Architecture

The project is built with:

- **Backend**: Python with asyncio for concurrent operations
- **Database**: PostgreSQL with pgvector extension for vector similarity search
- **Bot Framework**: aiogram for Telegram bot interactions
- **AI/ML**: OpenAI for embeddings and text generation
- **External APIs**: TMDB for movie metadata
- **ORM**: SQLAlchemy with async support

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose (for PostgreSQL with pgvector)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- TMDB API Key (from [TMDB](https://www.themoviedb.org/settings/api))
- OpenAI API Key (from [OpenAI Platform](https://platform.openai.com/api-keys))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Uvlazhnitel/WhatToWatch.git
   cd WhatToWatch
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and fill in your credentials:
   ```env
   DATABASE_URL_ASYNC=postgresql+asyncpg://movie_agent:movie_agent_password@localhost:5433/movie_agent
   DATABASE_URL_SYNC=postgresql+psycopg://movie_agent:movie_agent_password@localhost:5433/movie_agent
   TMDB_API_KEY=your_tmdb_api_key_here
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Start the database**
   ```bash
   docker-compose up -d
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt  # Create this if needed from your environment
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the bot**
   ```bash
   python -m app.bot.run
   ```

### Database Setup

The project uses PostgreSQL with the pgvector extension for vector similarity search. The Docker Compose configuration automatically sets up the database with pgvector.

To create test databases:
```bash
./scripts/create_test_db.sh
```

## Usage

### Bot Commands

Once the bot is running, interact with it via Telegram:

- `/start` - Initialize your user profile and see available commands
- `/review` - Add a review for a movie (searches TMDB and saves your rating/review)
- `/recommend` - Get personalized movie recommendations
- `/avoid <description>` - Add topics/themes to avoid (e.g., "/avoid office workplace drama")
- `/cancel` - Cancel current input operation
- `/myid` - Get your Telegram user ID

### Adding Reviews

1. Use `/review` command
2. Enter a movie title (optionally with year, e.g., "Alien 1979")
3. Select the correct movie from search results
4. Provide your rating (0-5 scale) and review text
5. The bot processes your review and updates your taste profile

### Getting Recommendations

1. Use `/recommend` command
2. The bot analyzes your taste profile and viewing history
3. Receive 3-5 personalized recommendations with:
   - Movie title and year
   - AI-generated explanation
   - Strategy label (🎯 Safe hit, 🧭 Adjacent exploration, 🎲 Wildcard)
   - Runtime, genres, and keywords
4. Mark movies as watched or skip them

### Importing Letterboxd Data

1. Export your Letterboxd data (includes diary.csv)
2. Get your Telegram user ID using `/myid` command
3. Run the import script:
   ```bash
   python -m app.scripts.import_letterboxd \
     --csv path/to/diary.csv \
     --telegram-id YOUR_TELEGRAM_ID \
     --unresolved-out unresolved.csv
   ```

Optional parameters:
- `--limit N` - Import only first N entries (for testing)
- `--sleep 0.2` - Delay between TMDB API calls (seconds)
- `--dry-run` - Preview without importing
- `--overrides path/to/overrides.csv` - Manual title-to-TMDB-ID mapping

### Background Jobs

The system includes background workers for processing:

1. **Embedding Worker**: Processes queued embedding jobs
   ```bash
   python -m app.jobs.embedding_worker
   ```

2. **Backfill Embeddings**: Generate embeddings for existing data
   ```bash
   python -m app.scripts.enqueue_embeddings_backfill
   ```

## Project Structure

```
WhatToWatch/
├── app/
│   ├── api/              # API endpoints (if used)
│   ├── bot/              # Telegram bot handlers and logic
│   ├── core/             # Core configuration and logging
│   ├── db/               # Database models, migrations, and repositories
│   │   ├── migrations/   # Alembic migration scripts
│   │   ├── repositories/ # Data access layer
│   │   └── models.py     # SQLAlchemy models
│   ├── integrations/     # External service integrations (TMDB, OpenAI)
│   ├── jobs/             # Background workers
│   ├── llm/              # LLM-related functionality
│   ├── recommender/      # Recommendation algorithms (v0 and v1)
│   ├── scripts/          # Utility scripts
│   └── services/         # Business logic services
├── tests/                # Test suite
├── docker-compose.yml    # PostgreSQL with pgvector setup
├── alembic.ini           # Database migration configuration
├── pytest.ini            # Test configuration
└── README.md             # This file
```

## Development

### Running Tests

```bash
pytest
```

### Creating Database Migrations

```bash
alembic revision -m "Description of changes"
alembic upgrade head
```

### Code Style

The project follows Python best practices:
- Type hints for better code clarity
- Async/await for concurrent operations
- Repository pattern for data access
- Clear separation of concerns

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Configuration

Key configuration options in `app/core/config.py`:

- **Database**: PostgreSQL connection strings
- **TMDB**: API settings and language preferences
- **OpenAI**: Model selection and parameters
  - Embedding model: text-embedding-3-small (1536 dimensions)
  - Text model: gpt-4o-mini
- **Bot**: Telegram bot token

## License

This project is provided as-is for educational and personal use.

## Troubleshooting

### Common Issues

1. **Database connection errors**: Ensure Docker containers are running and credentials match `.env`
2. **TMDB API errors**: Check API key validity and rate limits
3. **OpenAI API errors**: Verify API key and check usage limits
4. **Import failures**: Use `--dry-run` first to test and check `unresolved.csv` for problematic entries

### Getting Help

- Check the [issues](https://github.com/Uvlazhnitel/WhatToWatch/issues) for known problems
- Review logs for detailed error messages
- Ensure all environment variables are properly configured
