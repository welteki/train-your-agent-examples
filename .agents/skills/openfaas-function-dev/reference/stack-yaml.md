# stack.yaml Reference

The OpenFaaS stack file (commonly `stack.yml` or `<fn>.yml`) describes one or more functions to build and deploy. Reference: https://docs.openfaas.com/reference/yaml/

## Top-level structure

```yaml
version: 1.0
provider:
  name: openfaas
  gateway: http://127.0.0.1:8080

functions:
  fn1:
    # function-level config
  fn2:
    # function-level config

configuration:
  templates:
    - name: golang-middleware
      source: https://github.com/openfaas/golang-http-template
  copy:
    - ./common
    - ./models
```

`envsubst` syntax is supported in any value: `${VAR}`, `${VAR:-default}`.

## Function fields

### Required

| Field | Description |
|---|---|
| `lang` | Template name (must exist in `./template/<lang>` or be pullable). |
| `handler` | Path to a folder containing the handler source (never a filename). |
| `image` | Docker image name with optional registry prefix and tag. |

Function name (the YAML key) must be a valid DNS label: lowercase alphanumeric and `-`, max 63 chars, no leading/trailing hyphen.

### Common

| Field | Type | Description |
|---|---|---|
| `environment` | map | In-line env vars (NEVER for secrets). |
| `environment_file` | list | External YAML file(s) of env vars; later files override earlier. |
| `secrets` | list | Names of secrets to bind; mounted at `/var/openfaas/secrets/<name>`. |
| `build_options` | list | Named bundles from the template's `template.yml`. |
| `build_args` | map | Pass `--build-arg` values to Docker (e.g. `ADDITIONAL_PACKAGE`). |
| `build_secrets` | map | Build-time secrets (e.g. `${HOME}/.netrc`, pip credentials). |
| `skip_build` | bool | Skip Docker build for this function (default `false`). |
| `constraints` | list | Kubernetes nodeSelector entries (`"key=value"`). |
| `annotations` | map | Free-form metadata (e.g. `topic` for connectors, health-check overrides). |
| `labels` | map | Kubernetes labels; some have special meaning (e.g. autoscaling). |
| `limits.memory`, `limits.cpu` | string | Container resource limits (`128Mi`, `100m`). |
| `requests.memory`, `requests.cpu` | string | Resource requests (Kubernetes only; ignored on faasd/Edge). |
| `readonly_root_filesystem` | bool | Mount `/` read-only. |

### Selected annotations

```yaml
annotations:
  topic: kafka.payments-received
  com.openfaas.health.http.path: /healthz
  com.openfaas.health.http.initialDelay: 30s
```

### Build-time secrets example (private pip repo)

```yaml
functions:
  withprivate:
    lang: python3-http
    handler: ./withprivate
    image: openfaasltd/withprivate:0.0.1
    build_secrets:
      pip-conf: ${HOME}/.config/pip/pip.conf
```

`pip.conf`:

```
[global]
index-url = https://aws:CODEARTIFACT_TOKEN@OWNER-DOMAIN.d.codeartifact.us-east-1.amazonaws.com/pypi/REPOSITORY/simple/
```

### Private GitHub clone via .netrc

```yaml
build_secrets:
  netrc: ${HOME}/.netrc
```

## `configuration` block

Top-level (not nested under a function).

### `configuration.templates`

Auto-pull templates as part of `faas-cli build` / `faas-cli template pull stack`:

```yaml
configuration:
  templates:
    - name: python3-http
      source: https://github.com/openfaas/python-flask-template
    - name: golang-middleware
      source: https://github.com/openfaas/golang-http-template#0.7.0   # pinned to tag
```

When only `name` is provided, the template is fetched from the template store.

### `configuration.copy`

Project-relative paths copied into every function's handler folder at build time:

```yaml
configuration:
  copy:
    - ./common
    - ./data
    - ./models
```

Paths must be subdirectories of the project root. The CLI flag `--copy-extra` extends (does not replace) this list.

## Memory/CPU example

```yaml
url-ping:
  lang: python3-http
  handler: ./url-ping
  image: alexellis/url-ping:0.2
  limits:
    memory: 40Mi
    cpu: 100m
  requests:
    memory: 20Mi
    cpu: 100m
```

## Environment substitution example

```yaml
functions:
  url-ping:
    lang: python3-http
    handler: ./url-ping
    image: ${DOCKER_USER:-exampleco}/url-ping:0.2
```

```bash
DOCKER_USER=alexellis2 faas-cli build
```

## Generating Kubernetes CRDs

For GitOps workflows (Argo, Flux), convert stack.yaml to a `Function` CRD:

```bash
faas-cli generate -f stack.yml | kubectl apply -f -
```

## Multiple functions

```yaml
provider:
  name: openfaas
  gateway: http://127.0.0.1:8080
functions:
  fn1:
    lang: golang-middleware
    handler: ./fn1
    image: fn1:latest
  fn2:
    lang: golang-middleware
    handler: ./fn2
    image: fn2:latest
```

Use `--filter` or `--regex` with CLI verbs to act on subsets.
