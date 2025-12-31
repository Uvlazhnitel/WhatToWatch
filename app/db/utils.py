"""Database utilities and helpers."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions with automatic error handling.
    
    Usage:
        async with get_session() as session:
            user = await get_user(session, user_id)
    
    Yields:
        AsyncSession: Database session
        
    Raises:
        DatabaseError: If database operation fails
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise DatabaseError(f"Database operation failed: {e}") from e
        finally:
            await session.close()


async def execute_with_retry(
    func, *args, max_attempts: int = 3, **kwargs
):
    """
    Execute a database function with retry logic.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for function
        max_attempts: Maximum number of retry attempts
        **kwargs: Keyword arguments for function
        
    Returns:
        Result of function execution
        
    Raises:
        DatabaseError: If all retry attempts fail
    """
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(f"Database operation failed (attempt {attempt}/{max_attempts}): {e}")
            
            if attempt < max_attempts:
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(0.1 * (2 ** attempt))
            else:
                logger.error(f"Database operation failed after {max_attempts} attempts")
    
    raise DatabaseError(f"Database operation failed after {max_attempts} attempts") from last_error
