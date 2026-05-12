# Store helper functions for development, testing, and debugging

The OpenFaaS function store ships several small pre-built functions that
are useful while developing, testing, or debugging another function. They
are not part of any deployment — you opt in by running
`faas-cli store deploy <name>`.

Browse the full list with `faas-cli store list` (or
`faas-cli store describe <name>` for details).

These run in the target cluster, so they observe in-cluster behaviour from
the same network and DNS context as the function under test. Use them in
the inner dev loop and when reproducing bugs, then remove them when you
are done — do not leave them deployed in production
(`faas-cli remove printer`, `faas-cli remove chaos`, etc.).

## When to reach for which helper

| Function | Use it to… |
|---|---|
| `printer` | Pretty-print incoming HTTP requests (headers + body) into the function's logs. Chain a request to it (`/function/printer`) or use it as the `X-Callback-Url` target for an async invocation, then `faas-cli logs printer -t` to inspect what arrived. |
| `env` | Dump the function's environment variables (watchdog config, `environment:` from `stack.yaml`). Useful when verifying env was applied. |
| `sleep` | Sleeps for a configurable duration. Reproduce timeout behaviour, exercise async / scaling paths. |
| `chaos` | Returns canned status codes, bodies, and delays via a `/set` endpoint. Drive error paths, retry policies, and timeout handling from outside without modifying your function. Documented in the Pro [Retries](https://docs.openfaas.com/openfaas-pro/retries/) docs. |
| `nodeinfo` | Reports container CPU / memory / uptime. Sanity-check `limits` / `requests`, observe pod identity across replicas while debugging autoscaling. |
| `curl` | Run `curl` from inside the cluster — test reachability of internal services, the gateway (`http://gateway.openfaas:8080`), private registries, or DNS-based service discovery from a function's network context. |
| `nslookup` | Quick in-cluster DNS lookups (CoreDNS / service resolution). Useful when a function fails to reach another service. |
| `alpine` | Generic Alpine base — deploy with a custom `fprocess` to run a one-shot busybox command (e.g. `--fprocess="wc -l"`). |

## Patterns

### Inspect what an async invocation actually sent back

Pattern from
[Scale to zero GPUs with OpenFaaS, Karpenter and AWS EKS](https://www.openfaas.com/blog/scale-to-zero-gpus/) —
`printer` is used as the callback target so the async result is visible
in its logs:

```bash
faas-cli store deploy printer
faas-cli store deploy <fn-under-test>

curl -i http://127.0.0.1:8080/async-function/<fn-under-test> \
  -H "X-Callback-Url: http://gateway.openfaas:8080/function/printer" \
  -d '<payload>'

# In another terminal:
faas-cli logs printer -t
```

### Inspect what your function sent to a downstream

Point your function at `printer` instead of the real downstream HTTP
service (e.g. via an `UPSTREAM_URL` env var or stack.yaml override),
invoke it, then read `faas-cli logs printer -t` to see headers and body
exactly as your function sent them.

### Drive error paths and retry / timeout handling without changing the
function

Use `chaos` as a configurable downstream that returns the status / delay /
body you choose:

```bash
faas-cli store deploy chaos
curl -i http://127.0.0.1:8080/function/chaos/set \
  -H "Content-type: application/json" \
  --data-binary '{"status": 429, "delay": "1s", "body": "busy"}'
curl -i http://127.0.0.1:8080/async-function/chaos -d "ping"
```

### Verify env injection

Deploy `env` and confirm the environment variables you expect are present
(watchdog config, `environment:` from `stack.yaml`, etc.):

```bash
faas-cli store deploy env
faas-cli invoke env < /dev/null
```

### Debug in-cluster connectivity

`curl` and `nslookup` run inside the cluster, so they share the function
namespace's DNS and network policies — handy when a function cannot reach
the gateway, another function, an internal service, or an external
endpoint:

```bash
faas-cli store deploy curl
echo "-i http://gateway.openfaas:8080/healthz" | faas-cli invoke curl

faas-cli store deploy nslookup
echo "gateway.openfaas" | faas-cli invoke nslookup
```
