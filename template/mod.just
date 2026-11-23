set quiet
set default-list
set default-script
set shell := ['bash', '-euo', 'pipefail', '-c']
set script-interpreter := ['bash', '-euo', 'pipefail']
set working-directory := '..'

bootstrap_dir := justfile_dir() + '/bootstrap'
kubernetes_dir := justfile_dir() + '/kubernetes'
talos_dir := justfile_dir() + '/talos'
private_dir := justfile_dir() + '/.private'

template_dir := justfile_dir() + '/template'
template_resources := template_dir + '/resources'
makejinja_config := justfile_dir() + '/makejinja.toml'
mise_fragment := justfile_dir() + '/.mise/conf.d/template.toml'

config_file := justfile_dir() + '/cluster.toml'
schema_file := justfile_dir() + '/cluster.schema.json'
sample_config_file := justfile_dir() + '/cluster.sample.toml'
validate_script := template_dir + '/scripts/validate.py'
check_layout_script := template_dir + '/scripts/check_layout.py'

[doc('Render and validate configuration files')]
[group('template')]
configure: check-layout render validate-kubernetes validate-talos

[doc('Check that cluster.toml keeps its sections in the order of cluster.sample.toml')]
[group('template')]
check-layout:
    uv run --quiet --locked --no-dev "{{ check_layout_script }}" "{{ sample_config_file }}" "{{ config_file }}"

[doc('Copy a section block from cluster.sample.toml into cluster.toml, in the sample order, keys left commented')]
[group('template')]
scaffold section:
    uv run --quiet --locked --no-dev "{{ template_dir }}/scripts/scaffold.py" "{{ section }}" "{{ sample_config_file }}" "{{ config_file }}"
    just template check-layout

[doc('Check the 1Password items against the secret map; prints item and field names, never a value')]
[group('template')]
secrets-check:
    uv run --quiet --locked --no-dev "{{ template_dir }}/scripts/secrets_check.py" "{{ config_file }}"

[doc('Check that all prerequisite files exist and cluster.toml validates against the schema')]
[group('template')]
[no-exit-message]
doctor:
    rc=0
    just log info "just version" version "{{ just_version() }}"
    just template doctor-check "cluster.toml"           "{{ config_file }}"           || rc=1
    just template doctor-check "cluster.sample.toml"    "{{ sample_config_file }}"    || rc=1
    if [ -f "{{ config_file }}" ]; then
        if just template check-layout; then
            just log info "ok" check layout
        else
            just log error "cluster.toml sections are out of the sample's order" check layout
            rc=1
        fi
    fi
    config_json="$(just template config-json 2>/dev/null || true)"
    just template doctor-sops                                                         || rc=1
    just template doctor-check "template/"             "{{ template_dir }}"          || rc=1
    just template doctor-check "makejinja.toml"         "{{ makejinja_config }}"      || rc=1
    just template doctor-check "validate.py"            "{{ validate_script }}"       || rc=1
    if [ -f "{{ config_file }}" ] && [ -f "{{ validate_script }}" ]; then
        if [ -n "$config_json" ]; then
            just log info "ok" check schema
        else
            just log error "fail" check schema
            just log info "diagnose with: uv run --locked --no-dev {{ validate_script }} {{ config_file }}"
            rc=1
        fi
    fi
    [ "$rc" = 0 ] && just log info "all good"
    exit "$rc"

[doc('Create cluster.toml from cluster.sample.toml, unless it exists')]
[group('template')]
init:
    [ -f "{{ config_file }}" ] || cp "{{ sample_config_file }}" "{{ config_file }}"

# Editors resolve the #:schema directive in cluster.toml against this file;
# the validator tests fail when it drifts from the pydantic model.
[doc('Regenerate the cluster.toml JSON Schema from the validator')]
[group('template')]
schema:
    uv run --quiet --locked --no-dev "{{ validate_script }}" --schema > "{{ schema_file }}"
    oxfmt "{{ schema_file }}" > /dev/null

[confirm("Remove all templated files and directories — continue? [y/N]")]
[doc('Remove rendered files (bootstrap/, kubernetes/, talos/)')]
[group('template')]
reset:
    rm -rf "{{ bootstrap_dir }}" "{{ kubernetes_dir }}" "{{ talos_dir }}"

# tidy-archive moves template/ (this module's source) away, so it runs as a
# subsequent dependency: the tidy script itself must spawn while the module
# directory still exists.
[confirm("All template related config will be archived — continue? [y/N]")]
[doc('Archive all template tooling under .private/<ts>/ (one-way, run after configure works)')]
[group('template')]
tidy: tidy-preconditions tidy-strip && tidy-archive

# Validated, defaulted cluster config as JSON on stdout; fails when the
# config is invalid.
[private]
config-json:
    uv run --quiet --locked --no-dev "{{ validate_script }}" "{{ config_file }}"

[no-exit-message]
[private]
doctor-check label path:
    if [ -e "{{ path }}" ]; then
        just log info "ok" file "{{ label }}"
    else
        just log error "missing" file "{{ label }}"
        exit 1
    fi

# Secrets live in 1Password, so a tracked *.sops.* file is a leftover.
[no-exit-message]
[private]
doctor-sops:
    tracked="$(git ls-files ':(glob)**/*.sops.*')"
    if [ -z "$tracked" ]; then
        just log info "ok" check "no sops files"
    else
        just log error "sops files are tracked" files "$(echo $tracked)"
        exit 1
    fi

[private]
render:
    PYTHONDONTWRITEBYTECODE=1 uv run --locked --no-dev makejinja

[private]
tidy-archive:
    TIDY_FOLDER="{{ private_dir }}/$(date +%s)"
    mkdir -p "$TIDY_FOLDER"
    rm -rf "{{ justfile_dir() }}/.github/template-tests" "{{ justfile_dir() }}/.github/workflows"/template-*.yaml
    mv \
        "{{ template_dir }}" \
        "{{ makejinja_config }}" \
        "{{ mise_fragment }}" \
        "{{ schema_file }}" \
        "{{ config_file }}" \
        "{{ sample_config_file }}" \
        "{{ justfile_dir() }}/pyproject.toml" \
        "{{ justfile_dir() }}/uv.lock" \
        "$TIDY_FOLDER/"
    rmdir "$(dirname "{{ mise_fragment }}")" 2>/dev/null || true
    rm -rf "{{ justfile_dir() }}/.venv"

[private]
tidy-preconditions:
    test -d "{{ template_dir }}"
    test -d "{{ justfile_dir() }}/.github/template-tests"
    test -f "{{ makejinja_config }}"
    test -f "{{ config_file }}"
    test -f "{{ sample_config_file }}"
    test -f "{{ justfile_dir() }}/pyproject.toml"
    test -f "{{ justfile_dir() }}/uv.lock"
    test -f "{{ justfile_dir() }}/justfile"
    test -f "{{ mise_fragment }}"
    test -f "{{ schema_file }}"
    test -f "{{ justfile_dir() }}/.renovaterc.json5"
    compgen -G "{{ justfile_dir() }}/.github/workflows/template-*.yaml" > /dev/null

[private]
tidy-strip:
    sd '\..\.j2'                          '' "{{ justfile_dir() }}/.renovaterc.json5"
    sd -A '(?ms)^# === template ===$.*'   '' "{{ justfile_dir() }}/justfile"

# Renders every bootstrap chart with the rendered values, catching chart or
# values drift that dry runs cannot; needs network access to pull charts.
[doc('Render the bootstrap helmfile charts against the rendered values')]
[group('template')]
test-helmfile:
    helmfile --file "{{ bootstrap_dir }}/helmfile/apps.yaml" template --quiet > /dev/null
    just log info "bootstrap charts rendered cleanly"

[private]
validate-kubernetes:
    bash "{{ template_resources }}/kubeconform.sh" "{{ kubernetes_dir }}"

# Renders in a scratch copy without the secrets bundle, where topf writes a
# throwaway one, so configure never needs 1Password or the real bundle.
[private]
validate-talos:
    if [ -n "$(git ls-files talos/secrets.yaml)" ]; then
        just log fatal "talos/secrets.yaml is tracked by Git"
    fi
    scratch="$(mktemp -d)"
    trap 'rm -rf "$scratch"' EXIT
    rsync -a --exclude secrets.yaml "{{ talos_dir }}/" "$scratch/"
    cd "$scratch"
    topf render --confirm=false --output "$scratch/.out" >/dev/null
