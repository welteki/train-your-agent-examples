import json
import os
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
DISCORD_SECRET_PATH = "/var/openfaas/secrets/discord-webhook-url"
PG_CONN_SECRET_PATH = "/var/openfaas/secrets/hn-pg-connection"


def get_pg_conn_string():
    try:
        with open(PG_CONN_SECRET_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get("PG_CONNECTION_STRING", "")


def get_db():
    conn_str = get_pg_conn_string()
    if not conn_str:
        raise RuntimeError("PostgreSQL connection string not configured")
    conn = psycopg2.connect(conn_str)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()
    return conn


def is_new(conn, item_id):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM seen_items WHERE id = %s", (item_id,))
        return cur.fetchone() is None


def mark_seen(conn, item_id, title, url):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO seen_items (id, title, url) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (item_id, title, url),
        )
    conn.commit()


def get_discord_url():
    try:
        with open(DISCORD_SECRET_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get("DISCORD_WEBHOOK_URL", "")


def post_to_discord(webhook_url, title, hn_url, story_url, author, points):
    story_link = f" | [Story]({story_url})" if story_url else ""
    embed = {
        "title": title or "Hacker News item",
        "url": hn_url,
        "description": f"**Author:** {author} | **Points:** {points}{story_link}",
        "color": 0xFF6600,
        "footer": {"text": "Hacker News · serverless"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload = {"embeds": [embed]}
    resp = requests.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


def search_hn(query="serverless", tags="story", num_hours=1):
    params = {
        "query": query,
        "tags": tags,
        "numericFilters": f"created_at_i>{int(datetime.now(timezone.utc).timestamp()) - num_hours * 3600}",
        "hitsPerPage": 50,
    }
    resp = requests.get(HN_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def handle(event, context):
    webhook_url = get_discord_url()
    if not webhook_url:
        return {"statusCode": 500, "body": "Discord webhook URL not configured"}

    try:
        conn = get_db()
    except Exception as e:
        return {"statusCode": 500, "body": f"DB connection error: {e}"}

    posted = []
    errors = []

    hits = []
    for tags in ("story", "comment"):
        try:
            hits += search_hn(query="serverless", tags=tags, num_hours=24)
        except Exception as e:
            errors.append(f"HN search error ({tags}): {e}")

    for hit in hits:
        item_id = hit.get("objectID")
        if not item_id:
            continue

        title = hit.get("title") or hit.get("story_title") or hit.get("comment_text", "")[:80]
        story_url = hit.get("url") or ""
        hn_url = f"https://news.ycombinator.com/item?id={item_id}"
        author = hit.get("author", "unknown")
        points = hit.get("points") or 0

        if is_new(conn, item_id):
            try:
                post_to_discord(webhook_url, title, hn_url, story_url, author, points)
                mark_seen(conn, item_id, title, story_url)
                posted.append(item_id)
            except Exception as e:
                errors.append(f"Discord post error for {item_id}: {e}")

    conn.close()

    result = {"posted": len(posted), "posted_ids": posted, "errors": errors}
    return {"statusCode": 200, "body": json.dumps(result), "headers": {"Content-Type": "application/json"}}
