---
paths:
    - "template/config/kubernetes/apps/network/unifi-dns/**"
    - "kubernetes/apps/network/unifi-dns/**"
    - "template/config/kubernetes/apps/kube-system/coredns/**"
    - "kubernetes/apps/kube-system/coredns/**"
---

# UniFi DNS (`[unifi]`)

- `[unifi]` in `cluster.toml` (`host`, the console address; the API key is `API_KEY` in the vault item `unifi`) gates `network/unifi-dns`, a second ExternalDNS with the UniFi webhook sidecar. It writes local DNS records to the console for routes on `envoy-internal`, and for the gateways' own names through the `service` source, so internal names resolve on the LAN without manual records. `cloudflare-dns` keeps handling `envoy-external`. When `unifi.host` is an IPv4 address, CoreDNS also forwards lookups for the domain to the console, with the node resolvers after it as a fallback, so pods resolve the names that exist only on the internal gateway. That forward is a second `forward` in the main server block, not a server block of its own, because `autopath` resolves a pod's search path inside the main block and would bypass a separate one. The `public` fixture sets the section.
