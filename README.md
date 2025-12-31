# WhatToWatch 🎬

A personalized movie recommendation Telegram bot powered by AI and vector embeddings.

## Features

- 🤖 **Telegram Bot Interface** - Natural conversation for movie discovery
- 🎯 **Smart Recommendations** - Personalized picks based on your taste profile
- 📝 **Review Management** - Track and rate movies you've watched
- 🧠 **AI-Powered Explanations** - Understand why movies are recommended
- 🎲 **Diverse Strategies** - Safe picks, adjacent discoveries, and wildcards
- 📊 **Letterboxd Import** - Import your watch history
- 🔍 **TMDB Integration** - Rich movie metadata and search
- 💾 **Vector Embeddings** - Semantic similarity search with pgvector

## Architecture

- **Backend**: Python 3.12+ with AsyncIO
- **Bot Framework**: Aiogram 3.x
- **API**: FastAPI (minimal, primarily bot-driven)
- **Database**: PostgreSQL 16 with pgvector extension
- **AI/ML**: OpenAI (embeddings + text generation)
- **External APIs**: TMDB (The Movie Database)

## Prerequisites

- Python 3.12+
- PostgreSQL 16 with pgvector extension
- Docker & Docker Compose (recommended)
- TMDB API Key ([get one here](https://www.themoviedb.org/settings/api))
- Telegram Bot Token ([create bot with @BotFather](https://t.me/botfather))
- OpenAI API Key ([get one here](https://platform.openai.com/api-keys))

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Uvlazhnitel/WhatToWatch.git
cd WhatToWatch

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and fill in your API keys:
# - TMDB_API_KEY
# - TELEGRAM_BOT_TOKEN
# - OPENAI_API_KEY
```

### 3. Start Database

```bash
# Start PostgreSQL with pgvector using Docker Compose
docker-compose up -d

# Wait for database to be ready
docker-compose ps
```

### 4. Run Migrations

```bash
# Apply database migrations
alembic upgrade head
```

### 5. Run the Bot

```bash
# Start the Telegram bot
python -m app.bot.run
```

## Usage

### Bot Commands

- `/start` - Initialize the bot
- `/review` - Add a movie review
- `/recommend` - Get personalized recommendations
- `/avoid` - Add themes/topics to avoid
- `/cancel` - Cancel current operation
- `/myid` - Get your Telegram ID

### Import Letterboxd Data

```bash
# Export your data from Letterboxd (Settings → Import & Export → Export Your Data)
# Place the watched.csv file in the project root

python -m app.scripts.import_letterboxd --user-id YOUR_TELEGRAM_ID --csv watched.csv
```

## Development

### Running Tests

```bash
# Setup test database (first time only)
./scripts/create_test_db.sh

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

### Project Structure

```
app/
  api/              # FastAPI endpoints (minimal)
  bot/              # Telegram bot handlers and UI
  core/             # Configuration and logging
  db/               # Database models, migrations, repositories
  integrations/     # External API integrations (TMDB, OpenAI)
  jobs/             # Background workers (embeddings)
  llm/              # LLM prompts and text generation
  recommender/      # Recommendation algorithms (v0, v1)
  scripts/          # Utility scripts
  services/         # Business logic services
tests/              # Test suite
```

## Recommendation Strategies

### V0 (Collaborative Filtering)
- Genre-based preferences
- TMDB similar/recommended movies
- Diversity scoring

### V1 (Semantic + Collaborative)
- Vector embeddings for reviews and movie metadata
- Cosine similarity for taste matching
- Novelty and diversity scoring
- Soft avoidance patterns
- LLM-generated explanations

## Contributing

See [AUDIT_REPORT.md](AUDIT_REPORT.md) for detailed analysis and improvement opportunities.

## License

[Add your license here]

## Support

For issues and questions, please open an issue on GitHub.
