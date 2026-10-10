import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import nimbus, {
  defineConfig as defineNimbusConfig,
} from "@cloudflare/nimbus-docs";
import { tableScroll } from "@cloudflare/nimbus-docs/markdown";

const nimbusConfig = defineNimbusConfig({
  // The canonical origin is baked into canonical links, the sitemap and
  // llms.txt at build time. The cluster serves the site on the internal
  // gateway only, so this name resolves on the LAN alone.
  site: "https://docs.matherly.net",
  title: "Home Cluster",
  description:
    "Architecture, decisions and runbooks for a Talos Linux and Flux home Kubernetes cluster.",
  locale: "en",
  github: "https://github.com/jrmatherly/home-cluster",
  editPattern: "https://github.com/jrmatherly/home-cluster/edit/main/docs/{path}",
  socialImageAlt: "Home Cluster documentation",
});

export default defineConfig({
  // nimbus:adapter
  output: "static",
  // Tailwind v4 through its Vite plugin: the PostCSS plugin does not build
  // under Astro 7's Vite 8 bundler.
  vite: {
    plugins: [tailwindcss()],
  },
  // Hover-prefetch link targets so full-page navigations feel instant without
  // a client-side router.
  prefetch: {
    prefetchAll: true,
    defaultStrategy: "hover",
  },
  integrations: [
    nimbus(nimbusConfig, {
      // Every rule is on, so pages converted by different hands keep one
      // shape. `npm run lint:docs` runs them, and so does the image build.
      rules: {
        "nimbus/bare-url": "error",
        "nimbus/code-block-lang": "error",
        "nimbus/code-block-prompt-prefix": "error",
        "nimbus/description-required": "error",
        "nimbus/duplicate-heading-text": "error",
        "nimbus/emphasis-style": "error",
        "nimbus/frontmatter-shape": "error",
        "nimbus/heading-hierarchy": "error",
        "nimbus/heading-punctuation": "error",
        "nimbus/image-ref": "error",
        "nimbus/internal-link": "error",
        "nimbus/list-marker-style": "error",
        "nimbus/no-self-host-url": "error",
        "nimbus/single-h1": "error",
      },
      // Wrap wide tables so they scroll instead of overflowing the page
      // (styled by `.nb-table-scroll` in src/styles/prose.css).
      markdown: {
        hastPlugins: [tableScroll()],
      },
    }),
  ],
});
