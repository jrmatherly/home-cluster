# True when the research output is safe to publish. app, from, to and bump reach the public step
# summary as well as evidence and report, so the token search covers the whole output; digests go
# first, because they are long runs of hex that are not secrets.
(tostring | gsub("sha256:[0-9a-f]{64}"; "")
    | test("sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}") | not)
and (.verdicts | type == "array")
and all(.verdicts[];
    (.evidence | length < 800)
    and (.app | test("^[a-z0-9-]+$"))
    and (.namespace | test("^[a-z0-9-]*$"))
    and (.headRefOid | test("^[0-9a-f]{40}$"))
    and (.from | test("^[A-Za-z0-9._+-]{1,64}$"))
    and (.to | test("^[A-Za-z0-9._+-]{1,64}$"))
    and (.bump | test("^[a-z]{1,16}$")))
