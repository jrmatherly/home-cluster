---
paths:
    - "docs/src/content/**"
---

# Writing a docs page

The site is public, so a page describes the cluster in placeholders. `docs/scrub-check.sh` refuses the rest, and `npm run lint:docs` in `docs/` enforces the shape.

- Frontmatter: `title` (sentence case), a one-sentence `description`, and `sidebar.order`. The directory is the section and the sidebar; a section's `index.mdx` is its landing page.
- Body headings start at `##` and are not numbered. A guide that tracks progress opens with a `Status on` heading that carries the date, and a table. A page that rests on external documents ends with `## Sources`; inline attributions (`Docs`, `Source`, `Measured <date>`) are the alternative.
- Placeholders, always in backticks: the hosts are "the GPU host", "the non-GPU host" and "the media host"; `<proxmox service account>`, `<media host address>`, `<cp-1 address>`, `<router address>`, `<serial>`, `<token>`; the domain is `${SECRET_DOMAIN}`, as in `auth.${SECRET_DOMAIN}`. Talos node names (`k8s-cp-1`, `k8s-worker-2`) are role names and stay.
- MDX treats a bare `{` as an expression, so `${...}` and `{...}` go inside backticks or a code fence. Every fence names a language. Lists use `-`. No bare URLs.
- A guide starts in the gitignored `private/<name>.md` with real values; the page is its scrubbed copy, and a change means both files.
