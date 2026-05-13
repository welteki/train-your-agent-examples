# train-your-agent-examples

Example functions from the OpenFaaS blog post [**How To Train Your Agent**](https://www.openfaas.com/blog/how-to-train-your-agent-to-write-functions/), written by an AI coding agent using the [`openfaas-function-dev`](https://github.com/openfaas/agent-skills/tree/master/skills/openfaas-function-dev) skill.

---

# enrich-telemetry

An OpenFaaS function that enriches telemetry events with geolocation data (country, city, coordinates, ASN) derived from the event's `ip` field using embedded GeoLite2 databases.

## Prompt

```
Create a function the accepts telemetry events as input and enrich the
events with geolocation data: country, ASN, city, etc. This will require
downloading or embedding the geo2lite database:
https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/.
```

## How it works

1. Receives a JSON object or array of objects, each with an `ip` field
2. Looks up the IP in the embedded GeoLite2-City and GeoLite2-ASN databases
3. Merges geo fields (`country_code`, `country_name`, `city`, `latitude`, `longitude`, `asn`, `asn_org`) into the original event
4. Returns the enriched event(s) — all original fields are preserved

## Request format

Single event:

```json
{ "ip": "8.8.8.8", "event": "pageview", "user_id": "u123" }
```

Batch (array):

```json
[
  { "ip": "8.8.8.8", "event": "pageview" },
  { "ip": "1.1.1.1", "event": "click" }
]
```

## Response format

Single event response:

```json
{
  "ip": "8.8.8.8",
  "event": "pageview",
  "user_id": "u123",
  "country_code": "US",
  "country_name": "United States",
  "city": "Mountain View",
  "latitude": 37.751,
  "longitude": -97.822,
  "asn": 15169,
  "asn_org": "GOOGLE"
}
```

The response shape mirrors the input shape: a single object in → a single object out, an array in → an array out.

Events with an invalid or missing IP are returned unchanged without geo fields.

## Invoke

Using `curl`:

```bash
curl -s https://127.0.0.1:8080/function/enrich-telemetry \
  -H 'Content-Type: application/json' \
  -d '{"ip":"8.8.8.8","event":"pageview","user_id":"u123"}'
```

Using `faas-cli`:

```bash
echo '{"ip":"8.8.8.8","event":"pageview"}' | faas-cli invoke enrich-telemetry
```

Batch invocation:

```bash
curl -s https://127.0.0.1:8080/function/enrich-telemetry \
  -H 'Content-Type: application/json' \
  -d '[{"ip":"8.8.8.8"},{"ip":"1.1.1.1"}]'
```

## GeoLite2 database setup

The `.mmdb` database files are **not committed to the repository**. You must obtain them from MaxMind and place them in `enrich-telemetry/static/` before building.

The databases are embedded into the container image at build time and read from `/home/app/static/` at runtime. No external database connection is required.

### 1. Create a MaxMind account

Go to [https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/) and sign up for a free account.

### 2. Generate a license key

Once logged in, generate a license key in your [account portal](https://www.maxmind.com/en/accounts/current/license-key). This key is used to authenticate database downloads.

### 3. Download the databases

Download the two required databases in binary (`.mmdb`) format. Replace `YOUR_LICENSE_KEY` with the key you generated:

```bash
# GeoLite2 City
curl -sSL "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=YOUR_LICENSE_KEY&suffix=tar.gz" \
  | tar -xz --strip-components=1 --wildcards -C /tmp "*.mmdb"

# GeoLite2 ASN
curl -sSL "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN&license_key=YOUR_LICENSE_KEY&suffix=tar.gz" \
  | tar -xz --strip-components=1 --wildcards -C /tmp "*.mmdb"
```

### 4. Move files into place

```bash
mkdir -p enrich-telemetry/static
mv /tmp/GeoLite2-City.mmdb enrich-telemetry/static/
mv /tmp/GeoLite2-ASN.mmdb enrich-telemetry/static/
```

Required files:

```
enrich-telemetry/static/GeoLite2-City.mmdb
enrich-telemetry/static/GeoLite2-ASN.mmdb
```

> **Note:** The GeoLite2 EULA requires you to keep the databases up to date — delete and replace them within 30 days of each new MaxMind release.

## Deploy

```bash
faas-cli up -f stack.yaml --filter enrich-telemetry --tag=digest
```

## Local development

Place the `.mmdb` files as described above, then:

```bash
faas-cli local-run --build enrich-telemetry --port 9090
```

In a separate terminal:

```bash
curl -s http://127.0.0.1:9090 \
  -H 'Content-Type: application/json' \
  -d '{"ip":"8.8.8.8","event":"pageview"}'
```

## Error responses

| Status | Meaning |
|--------|---------|
| `400` | Body is not valid JSON or not an object/array |
| `500` | GeoLite2 database files could not be opened at startup |

---

# decrypt-payload

An OpenFaaS function that decrypts an AES-128-CBC encrypted payload, parses the inner JSON, and returns it with a `processedAt` timestamp appended.

## Prompt

```
Write a function in node.js that takes an encrypted payload (internally
it's JSON), and uses a single master key AES 128-bit attached to it via
a secret. It decrypts it and adds a processedAt field

{
  "processedAt": "RFC time",
  "cipher": "ZUDWIOeeef==="
}

The body is returned back to the caller.
```

## How it works

1. Receives a JSON body containing a `cipher` field
2. Reads the AES-128 master key from `/var/openfaas/secrets/master-key`
3. Decodes the base64 cipher value — the first 16 bytes are the IV, the remainder is the ciphertext
4. Decrypts using AES-128-CBC and parses the result as JSON
5. Appends a `processedAt` field (RFC UTC string) and returns the enriched object

## Request format

```json
{
  "cipher": "<base64(IV + ciphertext)>"
}
```

The cipher value must be a base64-encoded blob where the first 16 bytes are the AES IV and the rest is the ciphertext — this is the format produced when you manually prepend the IV before encrypting.

## Response format

The decrypted JSON payload with an additional field:

```json
{
  "user": "alice",
  "amount": 42,
  "processedAt": "Tue, 12 May 2026 09:46:50 GMT"
}
```

## Secrets

The function reads the master key from a single secret named `master-key`. The key must be exactly 16 bytes, stored as 32 lowercase hex characters.

Generate a key:

```bash
openssl rand -hex 16
```

Create the secret in OpenFaaS:

```bash
faas-cli secret create master-key --from-file master-key.txt
```

For local testing with `faas-cli local-run`, place the key in `.secrets/master-key` at the project root:

```bash
mkdir -p .secrets
openssl rand -hex 16 > .secrets/master-key
```

## Deploy

```bash
faas-cli up -f stack.yaml --tag=digest
```

## Invoke

Using `faas-cli`:

```bash
echo '{"cipher":"<base64-cipher>"}' | faas-cli invoke decrypt-payload
```

Using `curl`:

```bash
curl -s https://<gateway>/function/decrypt-payload \
  -H 'Content-Type: application/json' \
  -d '{"cipher":"<base64-cipher>"}'
```

## Generating a test payload

Use the included `encrypt-test.js` script to produce a valid cipher from any JSON string:

```bash
node encrypt-test.js '{"user":"alice","amount":42}'
```

This prints the request body and a ready-to-run `curl` command. It reads the key from `.secrets/master-key`.

## Local development

Build and run the function locally with `faas-cli local-run`:

```bash
faas-cli local-run --build decrypt-payload --port 8090
```

Then in a separate terminal, generate a cipher and invoke:

```bash
node encrypt-test.js '{"hello":"world"}' 
# copy the curl command from the output and run it against http://127.0.0.1:8090
```

## Error responses

| Status | Meaning |
|--------|---------|
| `400` | Missing or malformed JSON body, or missing `cipher` field |
| `422` | Decryption failed (wrong key, corrupt cipher) or decrypted bytes are not valid JSON |
| `500` | Master key could not be read from the secrets mount |

---

# hn-serverless-monitor

A cron-triggered OpenFaaS function that polls the Hacker News Algolia API every 15 minutes for posts and comments mentioning "serverless", deduplicates them against a PostgreSQL database, and posts each new hit to a Discord channel via a webhook.

## Prompts

Initial prompt:

```
Every 15 minutes, connect to Hacker News and look for comments or posts
on serverless. We want to keep everything we've seen in a database so we
don't have to re-scan it again. I want you to post each unique article
to a Discord channel using a webhook URL: https://discord.com/api/webhooks/
```

Follow-up prompt (the first iteration used SQLite; this switched it to PostgreSQL):

```
Switch to using postgresql. The connection string should be configurable.
```

## How it works

1. Triggered every 15 minutes by the [cron-connector](https://docs.openfaas.com/reference/cron/) via the `topic: cron-function` and `schedule: "*/15 * * * *"` annotations
2. Queries the [HN Algolia API](https://hn.algolia.com/api) for `story` and `comment` hits matching `serverless` from the last 24 hours
3. Checks each item against a `seen_items` table in PostgreSQL
4. For each unseen item, posts a Discord embed via the webhook and records the item id

## Secrets

Two secrets are required:

| Name | Contents |
|------|----------|
| `discord-webhook-url` | Full Discord webhook URL, e.g. `https://discord.com/api/webhooks/...` |
| `hn-pg-connection` | A libpq connection string, e.g. `postgres://user:pass@host:5432/dbname` |

Create them with:

```bash
faas-cli secret create discord-webhook-url --from-file .secrets/discord-webhook-url
faas-cli secret create hn-pg-connection    --from-file .secrets/hn-pg-connection
```

## Deploy

```bash
faas-cli up -f stack.yaml --filter hn-serverless-monitor --tag=digest
```

## Invoke manually

The function is normally driven by the cron-connector but can be invoked on demand:

```bash
faas-cli invoke hn-serverless-monitor < /dev/null
```

A successful run returns:

```json
{"posted": 2, "posted_ids": ["43928412", "43928577"], "errors": []}
```
