---
paths:
    - "template/config/kubernetes/apps/kube-system/restart-reset/**"
    - "kubernetes/apps/kube-system/restart-reset/**"
---

# restart-reset

- `kube-system/restart-reset` is an hourly CronJob (`concurrencyPolicy: Forbid`, so runs never overlap) that evicts every Running, fully Ready pod whose last restart is over an hour old, one at a time, so restart counts left by a switch or gateway reboot or an API outage reset on their own within two hours. It was daily at 10:00 UTC until 2026-10-12, when that left a 09:21 EDT burst in place for a day. Eviction honours PodDisruptionBudgets, static pods are skipped, and so is a CloudNativePG primary (label `cnpg.io/instanceRole=primary`), because evicting it would be a failover. A pod that is not Ready or restarted within the hour is left alone, so a real crash loop is never churned; a restart with no `finishedAt` counts as now, so that pod is left alone too. It runs kubectl and jq from the `alpine/k8s` image as uid 65534 with a ClusterRole limited to listing pods and creating evictions.
