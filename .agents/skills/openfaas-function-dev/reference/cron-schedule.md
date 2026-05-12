# Scheduling functions with the cron-connector

Use the OpenFaaS **cron-connector** to invoke a function on a schedule. It works on every OpenFaaS provider (Kubernetes CE/Pro, OpenFaaS Edge/faasd), so the same `stack.yaml` is portable.

Do not use Kubernetes `batch/v1 CronJob` running `faas-cli invoke` to schedule function calls. It bypasses it does not work on faasd.

## Wiring a function to a schedule

Annotate the function in `stack.yaml` with a `topic` of `cron-function` and a valid cron expression in `schedule`:

```yaml
functions:
  nightly-report:
    lang: python3-http
    handler: ./nightly-report
    image: ${REGISTRY:-ttl.sh/myuser}/nightly-report:${TAG:-latest}
    annotations:
      topic: cron-function
      schedule: "0 2 * * *"        # every day at 02:00 UTC
```

Then deploy as usual:

```bash
faas-cli up -f stack.yaml --tag=digest
```

The cron-connector picks up the annotations and starts firing on schedule. No further wiring is required from the function side.

## Cron expression rules

- Standard 5-field cron expressions (https://crontab.guru is handy for authoring/validating).
- Multiple schedules can be combined in one annotation, separated by `;` — the connector fires once per expression:
  ```yaml
  schedule: "0 9 * * 1-5;0 13 * * 1-5"   # 09:00 and 13:00 on weekdays
  ```

## Disabling a schedule

- To stop scheduled invocations, remove the `schedule` annotation.
- To detach the function from the connector entirely, remove both `topic` and `schedule`.
- Re-deploy with `faas-cli deploy` — the connector reconciles annotation changes automatically.

## CE vs Pro

- On OpenFaaS **CE**, a function bound to the cron-connector can only be triggered by cron — no other connector can co-exist on that function.
- On OpenFaaS **Pro**, the same function can be wired to multiple connectors at once (e.g. Cron + Kafka), and gets structured JSON logs and additional metrics.

## Break-glass: when a Kubernetes CronJob is acceptable

Reach for a `batch/v1 CronJob` only when the scheduled work is **not a function invocation** — for example running an admin `kubectl` command on a schedule. For anything that ends in `faas-cli invoke <fn>` or `curl .../function/<fn>`, use the cron-connector. When you do break glass, flag the deviation to the user.

## Reference

- https://docs.openfaas.com/reference/cron/
- https://github.com/openfaas/cron-connector
