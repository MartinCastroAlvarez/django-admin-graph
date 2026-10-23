# Security

`django-admin-graph` describes your admin's *structure* to whoever asks. The
whole design goal is that it never tells anyone more than the admin itself
would show them.

## Reporting a vulnerability

Open a private security advisory at
<https://github.com/MartinCastroAlvarez/django-admin-graph/security/advisories/new>.
Do **not** open a public issue for a suspected vulnerability. We acknowledge
within 5 business days and aim to ship a fix within 30 days; you are credited
in the advisory unless you ask otherwise.

Supported versions: the latest minor release.

## 1. Threat model

**Assets.** The schema of your project: which models exist, their fields,
choices and help texts, relations, admin configuration, actions and
permissions. Not record data — the package never queries rows.

**Actors.**

| Actor | Can reach | Must get |
| --- | --- | --- |
| Anonymous visitor | the JSON view, if mounted | `401`, nothing else |
| Authenticated non-staff user | the JSON view | `403` (even with model permissions) |
| Staff user with limited permissions | the JSON view, `build_graph(request=…)` in your code | only the models / fields / actions / inlines the admin shows them |
| Operator with shell access | `manage.py admin_graph`, `build_graph()` | the whole site (system mode) |
| A consumer of a saved graph (an agent, a code generator) | the JSON document | data, never instructions |

**Threats and controls.**

| Threat | Control |
| --- | --- |
| Enumerating models a user cannot open | Visibility is `has_module_permission` + `get_model_perms` per request; hidden models are not nodes and are never named (FK targets become `null`, `related_name` is dropped). |
| Leaking excluded fields (`exclude`, custom `get_fields`) | Fields come from the ModelAdmin's own form, read-only fields and `list_display`. |
| Advertising actions or inlines the user cannot use | `get_actions(request)` and `get_inline_instances(request)` — Django's own filtering. |
| Re-implemented permission logic drifting from the admin | No `has_perm` / queryset calls in the package; a test scans the source for them. |
| Shared caches serving one user's graph to another | `Cache-Control: private, no-store` and `Vary: Cookie` on every response. |
| CSRF / state change through the view | The view is `GET`/`HEAD` only (`require_safe`) and changes nothing; no `@csrf_exempt` anywhere. |
| Record data leaking into the graph | The builder reads `_meta` and ModelAdmin configuration only; a test asserts zero queries for a superuser build. The ModelAdmin's change form is resolved against an *unsaved* placeholder instance that is never saved or queried. |
| System mode reachable over HTTP | Only `request=None` selects it; the view always passes the real request. |
| Prompt injection via a saved graph | `help_text`, verbose names and choice labels are author-controlled strings. Consumers that feed the graph to an LLM must treat them as untrusted data, not instructions (`django-admin-skills` quotes them as data). |

**Out of scope.** Your own ModelAdmin permission methods being wrong (the
graph faithfully reports what they say), and operators publishing a
system-mode graph — treat that file like source code.

## 2. Non-negotiable rules

Enforced by `tests/test_security.py`; if one fails, fix the code, never the test.

1. **Staff-only.** The view delegates to `AdminSite.has_permission` and
   returns `401` / `403` before building anything.
2. **The admin decides.** No `user.has_perm`, no `Model.objects…`, no
   `.raw()` / `.extra()` in `django_admin_graph/`.
3. **No dangerous constructs.** No `csrf_exempt`, `mark_safe`, `eval`,
   `exec`, `pickle`, `yaml.load`, `shell=True`.
4. **Closed graph.** Every edge endpoint and relation target is a node in
   the same document.
5. **No identity.** The document carries no username, email, URL or host.

## 3. Supply chain

CI runs `bandit` and `pip-audit` on every push; Dependabot watches pip and
GitHub Actions; releases use PyPI Trusted Publishing (no API tokens) and the
built artefacts are scanned for token-shaped strings before upload.
