# Contributing to WhatToWatch

Thank you for your interest in contributing to WhatToWatch! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain a welcoming environment for all contributors

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:

1. **Clear title**: Summarize the problem
2. **Description**: Detailed explanation of the issue
3. **Steps to reproduce**: How to recreate the problem
4. **Expected behavior**: What should happen
5. **Actual behavior**: What actually happens
6. **Environment**: Python version, OS, relevant package versions
7. **Logs**: Any relevant error messages or logs

### Suggesting Enhancements

Feature requests are welcome! Please include:

1. **Use case**: Why is this feature needed?
2. **Proposed solution**: How would it work?
3. **Alternatives**: Other approaches you've considered
4. **Additional context**: Screenshots, mockups, or examples

### Pull Requests

We actively welcome your pull requests! Here's the process:

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following our code style guidelines
3. **Add tests** if you're adding functionality
4. **Update documentation** if you're changing behavior
5. **Ensure tests pass** and code follows style guidelines
6. **Write a clear commit message** describing your changes
7. **Submit a pull request** with a description of your changes

## Development Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Git

### Local Development Environment

1. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/WhatToWatch.git
   cd WhatToWatch
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt  # When available
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your test credentials
   ```

5. **Start the database**
   ```bash
   docker-compose up -d
   ```

6. **Run migrations**
   ```bash
   alembic upgrade head
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific_file.py

# Run with coverage
pytest --cov=app
```

### Testing Your Bot Changes

1. Create a test bot with [@BotFather](https://t.me/botfather)
2. Use test credentials in `.env`
3. Start the bot: `python -m app.bot.run`
4. Test your changes interactively

## Code Style Guidelines

### Python Style

- **Follow PEP 8**: Use standard Python style conventions
- **Type hints**: Add type annotations to function signatures
- **Docstrings**: Document classes and non-trivial functions
- **Async/await**: Use async patterns consistently
- **Imports**: 
  - Group imports: standard library, third-party, local
  - Sort alphabetically within groups
  - Avoid duplicate imports
  - Use absolute imports for clarity

### Code Organization

- **Repository pattern**: Use repositories for database access
- **Separation of concerns**: Keep business logic separate from handlers
- **DRY principle**: Don't repeat yourself - extract common functionality
- **Small functions**: Keep functions focused and concise
- **Error handling**: Use try-except blocks appropriately

### Example Function

```python
from __future__ import annotations

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_recommendations(
    session: AsyncSession,
    user_id: int,
    count: int = 5,
    recent_days: int = 60,
) -> list[Recommendation]:
    """
    Fetch personalized movie recommendations for a user.
    
    Args:
        session: Database session
        user_id: User's unique identifier
        count: Number of recommendations to return
        recent_days: Consider recommendations from this many days ago
        
    Returns:
        List of Recommendation objects
        
    Raises:
        ValueError: If user_id is invalid
    """
    # Implementation here
    pass
```

## Database Changes

### Creating Migrations

When modifying database models:

```bash
# Create a new migration
alembic revision -m "Add field to user table"

# Edit the generated migration file in app/db/migrations/versions/

# Test the migration
alembic upgrade head

# If needed, rollback
alembic downgrade -1
```

### Migration Best Practices

- Make migrations reversible (implement `downgrade`)
- Test migrations on a copy of production data
- Keep migrations small and focused
- Add indexes for frequently queried fields
- Consider backward compatibility

## Commit Messages

Write clear, descriptive commit messages:

```
Short summary (50 chars or less)

More detailed explanation if needed. Wrap at 72 characters.
Explain what and why, not how.

- Bullet points are okay
- Use present tense: "Add feature" not "Added feature"
- Reference issues: "Fixes #123" or "Related to #456"
```

### Examples

Good:
- `Fix duplicate imports in router.py`
- `Add taste profile caching to improve performance`
- `Update README with installation instructions`

Not ideal:
- `Fixed stuff`
- `Update code`
- `Changes`

## Testing Guidelines

### What to Test

- **Happy paths**: Normal expected usage
- **Edge cases**: Boundary conditions
- **Error handling**: Invalid inputs, API failures
- **Database operations**: CRUD operations work correctly
- **Async operations**: Concurrent operations don't interfere

### Test Structure

```python
import pytest
from app.services.example import example_function

async def test_example_function_success():
    """Test example_function with valid input."""
    result = await example_function(valid_input)
    assert result == expected_output

async def test_example_function_invalid_input():
    """Test example_function handles invalid input."""
    with pytest.raises(ValueError):
        await example_function(invalid_input)
```

## Documentation

### When to Update Documentation

- Adding new features
- Changing existing behavior
- Adding configuration options
- Changing API endpoints or bot commands

### Documentation Standards

- **README.md**: High-level overview, setup, usage
- **Code comments**: Explain "why", not "what"
- **Docstrings**: Document public APIs
- **Type hints**: Self-documenting code

## Getting Help

- **Questions**: Open a discussion or issue
- **Bugs**: Create a bug report issue
- **Features**: Create a feature request issue

## Review Process

After submitting a PR:

1. **Automated checks**: Tests and linting must pass
2. **Code review**: Maintainers will review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, your PR will be merged
5. **Recognition**: Contributors are acknowledged

## Recognition

All contributors will be acknowledged in the project. Thank you for helping make WhatToWatch better!

## Questions?

Don't hesitate to ask! Open an issue or reach out to the maintainers.

---

Thank you for contributing to WhatToWatch! 🎬
