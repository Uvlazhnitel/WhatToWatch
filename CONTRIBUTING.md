# Contributing to WhatToWatch

Thank you for considering contributing to WhatToWatch! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/WhatToWatch.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Submit a pull request

## Development Setup

```bash
# Install dependencies
make install

# Start database
make db-up

# Run migrations
make migrate

# Run tests
make test
```

## Code Style

We use automated tools to maintain code quality:

- **Black** for code formatting (line length: 120)
- **Ruff** for linting
- **Mypy** for type checking

Before committing:

```bash
# Format code
make format

# Run linting
make lint

# Run type checking
make typecheck
```

## Testing

All new features must include tests:

- **Unit tests** for individual functions and classes
- **Integration tests** for database operations and API calls
- **End-to-end tests** for complete user flows

```bash
# Run tests
make test

# Run with coverage
make test-cov
```

Target minimum **80% code coverage** for new code.

## Commit Messages

Follow the conventional commits specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(bot): add movie search by director

fix(recommender): correct similarity scoring bug

docs(readme): update installation instructions
```

## Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new functionality
3. **Ensure all tests pass**: `make test`
4. **Run linting**: `make lint`
5. **Update CHANGELOG.md** (if applicable)
6. **Request review** from maintainers

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] No new linting errors
- [ ] Type hints added for new code
- [ ] Commit messages follow conventions

## Project Structure

```
app/
  api/              # FastAPI endpoints
  bot/              # Telegram bot handlers
  core/             # Configuration and utilities
  db/               # Database models and repositories
  integrations/     # External API clients
  jobs/             # Background workers
  llm/              # LLM prompts and generation
  recommender/      # Recommendation algorithms
  services/         # Business logic
tests/              # Test suite
```

## Architecture Guidelines

### Separation of Concerns

- **Handlers** (bot/api): Parse input, call services, format output
- **Services**: Business logic and orchestration
- **Repositories**: Database operations
- **Models**: Data structures and validation

### Async/Await

- Use `async/await` for all I/O operations
- Use `asyncio.gather()` for parallel operations
- Never block the event loop

### Error Handling

- Create specific exception types
- Log all errors with context
- Return user-friendly messages
- Never expose internal errors to users

### Database

- Use SQLAlchemy ORM for queries
- Add indexes for frequently queried columns
- Use transactions for multi-step operations
- Test migrations both up and down

## Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Update README.md for user-facing changes
- Add inline comments for complex logic

Example:
```python
async def create_recommendation(
    session: AsyncSession,
    user_id: int,
    count: int = 3
) -> list[RecPick]:
    """
    Generate personalized movie recommendations for a user.
    
    Args:
        session: Active database session
        user_id: ID of the user to recommend for
        count: Number of recommendations to generate
        
    Returns:
        List of recommendation picks with scores
        
    Raises:
        UserNotFoundError: If user doesn't exist
        InsufficientDataError: If user has too few ratings
    """
```

## Performance Considerations

- Avoid N+1 queries - use eager loading or batch fetching
- Cache expensive operations
- Use database indexes appropriately
- Profile slow code paths

## Security

- Never commit secrets or API keys
- Validate all user inputs
- Use parameterized queries (SQLAlchemy ORM does this)
- Keep dependencies updated
- Run security scans: `make security`

## Questions?

Open an issue or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
