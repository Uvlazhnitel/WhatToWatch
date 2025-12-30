# tests/fakes/tmdb_stub.py

# Минимальные ответы TMDB, чтобы recommender/v0.py мог работать без сети.

DETAILS = {
    # tmdb_id: payload
    999: {
        "id": 999,
        "title": "Watched",
        "release_date": "2000-01-01",
        "runtime": 120,
        "genres": [{"id": 18, "name": "Drama"}],
        "overview": "Stub overview for watched movie.",
        "popularity": 10.0,
        "vote_average": 7.0,
        "vote_count": 100,
    },
    1001: {
        "id": 1001,
        "title": "Candidate A",
        "release_date": "2001-01-01",
        "runtime": 110,
        "genres": [{"id": 18, "name": "Drama"}],
        "overview": "Stub overview A.",
        "popularity": 50.0,
        "vote_average": 7.5,
        "vote_count": 500,
    },
    1002: {
        "id": 1002,
        "title": "Candidate B",
        "release_date": "2002-01-01",
        "runtime": 95,
        "genres": [{"id": 53, "name": "Thriller"}],
        "overview": "Stub overview B.",
        "popularity": 40.0,
        "vote_average": 7.2,
        "vote_count": 400,
    },
}

KEYWORDS = {
    999: {"id": 999, "keywords": [{"id": 1, "name": "corporate"}, {"id": 2, "name": "law"}]},
    1001: {"id": 1001, "keywords": [{"id": 10, "name": "family"}]},
    1002: {"id": 1002, "keywords": [{"id": 20, "name": "mystery"}]},
}

# В v0 мы можем дергать similar и/или recommendations.
# Дадим оба.
SIMILAR = {
    999: {
        "page": 1,
        "results": [
            {"id": 1001, "title": "Candidate A", "release_date": "2001-01-01"},
            {"id": 1002, "title": "Candidate B", "release_date": "2002-01-01"},
        ],
    }
}

RECOMMENDATIONS = {
    999: {
        "page": 1,
        "results": [
            {"id": 1001, "title": "Candidate A", "release_date": "2001-01-01"},
            {"id": 1002, "title": "Candidate B", "release_date": "2002-01-01"},
        ],
    }
}
