#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-movie_agent_db}"
TEST_DB="${TEST_DB:-movie_agent_test}"
DB_USER="${DB_USER:-movie_agent}"

docker exec -it "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS ${TEST_DB};"
docker exec -it "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE ${TEST_DB};"

echo "✅ Test DB created: ${TEST_DB}"
