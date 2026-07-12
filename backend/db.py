"""Postgres + pgvector helpers."""
import psycopg
from pgvector.psycopg import register_vector
import config


def connect():
    conn = psycopg.connect(**config.PG)
    register_vector(conn)
    return conn


def insert_knowledge(conn, source_key, domain, content, embedding, approved=True):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO knowledge (source_key, domain, content, approved, embedding)
               VALUES (%s, %s, %s, %s, %s)""",
            (source_key, domain, content, approved, embedding),
        )
    conn.commit()


def count_knowledge(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge")
        return cur.fetchone()[0]


def reset_knowledge(conn):
    """Wipe the whole knowledge table (clean slate for a fresh demo run)."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE knowledge RESTART IDENTITY")
    conn.commit()


def search(conn, query_embedding, top_k=config.TOP_K, domain=None):
    """Cosine similarity search over approved entries. Optional domain filter."""
    sql = """SELECT id, source_key, domain, content,
                    1 - (embedding <=> %s::vector) AS score
             FROM knowledge
             WHERE approved = TRUE"""
    params = [query_embedding]
    if domain:
        sql += " AND domain = %s"
        params.append(domain)
    sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params += [query_embedding, top_k]
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        {"id": r[0], "source_key": r[1], "domain": r[2], "content": r[3], "score": float(r[4])}
        for r in rows
    ]
