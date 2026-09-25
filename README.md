# Bring your own IdP: three-cloud proof of concept

Status: local Git repository created; cloud deployment and live verification are pending. The GitHub remote has not been created. Local tests prove signing behavior only.

Start with [SETUP.md](SETUP.md) for account creation, installation, sign-in, and the division of work. The intended remote is `redbmk/jwt-federation-example`; its issuer will be `https://redbmk.github.io/jwt-federation-example`.

## Architecture

Local signer → external JWT → cloud identity exchange → temporary cloud credential → protected hello-world function.

GitHub Pages serves public discovery metadata and signing keys. It does not mint tokens. The private signing key stays in `.local/`, excluded from Git. This is a federation test issuer, not a full interactive OpenID Connect login service.

Public paths under `https://OWNER.github.io/REPO`:

- `/.well-known/openid-configuration`
- `/jwks.json`

The exact issuer includes the repository path. Keep it identical in the token, discovery document, and cloud configuration. `.nojekyll` preserves the `.well-known` directory in branch-based Pages publishing. Publish only `docs/`, never the repository root or `.local/`.

## Run the local starter

Requires Node.js 22 or later; no third-party packages.

```sh
npm test
node issuer.mjs init https://OWNER.github.io/REPO
node issuer.mjs mint https://OWNER.github.io/REPO byo-idp-poc
```

`init` creates a local private key and public discovery/JWKS files. It refuses to overwrite an existing private key. `mint` writes 14 short-lived test tokens into `.local/tokens/`. Tokens expire after five minutes except deliberate time-negative cases. Regenerate just before a test. For Azure use `api://AzureADTokenExchange` as the audience; generating another suite replaces local token files.

## Claims and trust policy

Baseline identity:

```json
{
  "iss": "https://OWNER.github.io/REPO",
  "aud": "byo-idp-poc",
  "sub": "client:client-a:agent:agent-a",
  "client_id": "client-a",
  "agent_id": "agent-a"
}
```

The signer adds `iat` and `exp`. Use separate audiences for cloud-specific requests when appropriate. Audience identifies the intended recipient; the external `client_id` is a separate concept. Azure's application/client ID used in the exchange is also a separate identifier.

| Cloud | Exchange and invocation | Proposed claim enforcement |
|---|---|---|
| AWS | AssumeRoleWithWebIdentity → temporary credentials → signed Lambda Invoke API | Register our OIDC provider; role trust matches provider, audience and exact subject; role grants InvokeFunction on one function only. |
| GCP | Security Token Service → service-account impersonation → ID token for private Cloud Run URL → HTTPS call | Provider matches issuer/audience; CEL condition checks exact subject, client_id and agent_id; service account has Cloud Run Invoker on one service only. |
| Azure | External JWT as client assertion → Entra application access token → Azure Function with Entra authentication | Federated credential matches issuer, subject and token-exchange audience; Function auth requires correct API audience and allowlists the caller application's ID. |

For AWS, use the standard OIDC claim mapping: arbitrary top-level `client_id` and `agent_id` claims are not automatically IAM condition keys. An optional later experiment can pass claims as AWS session tags using AWS's special claim format and explicit TagSession policy. Also test `azp`: when present it changes AWS's `aud` condition-key mapping; `oaud` maps the original audience.

For GCP, map `google.subject=assertion.sub` and set a condition equivalent to:

```text
assertion.sub == 'client:client-a:agent:agent-a' &&
assertion.client_id == 'client-a' &&
assertion.agent_id == 'agent-a'
```

For Azure, use ordinary federated identity credentials for our own issuer. Do not assume arbitrary custom-claim filtering is available: flexible credentials currently document support for selected issuer platforms. Management-plane Azure RBAC alone does not protect invocation of an HTTP Function; configure its authentication/authorization explicitly, returning 401 for unauthenticated callers, and allow only the intended caller app. The downstream token contains Entra's identity, not an automatic copy of all original custom claims.

## Live test matrix

These are expected outcomes for the proposed configurations, NOT observed results.

| Test | AWS | GCP | Azure |
|---|---|---|---|
| Valid identity | Exchange + hello succeed | Exchange + hello succeed | Exchange + hello succeed |
| Wrong issuer | Deny | Deny | Deny |
| Wrong audience | Deny | Deny | Deny |
| Different client, including subject | Deny | Deny | Deny |
| Different agent, including subject | Deny | Deny | Deny |
| Change only custom client_id | Accept: claim not checked | Deny | Accept: claim not checked |
| Change only custom agent_id | Accept: claim not checked | Deny | Accept: claim not checked |
| Remove custom client_id or agent_id | Accept: claim not checked | Deny | Accept: claim not checked |
| Missing subject | Deny | Deny | Deny |
| Expired token | Deny | Deny | Deny |
| Invalid signature, trusted kid | Deny | Deny | Deny |
| Future nbf | Measure enforcement | Measure enforcement | Measure enforcement |
| Wrong azp added | Deny under proposed aud condition | Measure; no explicit azp condition | Measure; no explicit azp condition |

Also test invocation with no credentials and with a second valid cloud identity that lacks invocation access. These distinguish federation trust from function authorization. Test the latter using a temporary dedicated identity, not by changing an existing user's permissions.

For each case record the changed claims (no JWT), exchange status/error code, invocation status/body, cloud request ID, and timestamp. A timeout, JWKS-fetch error, rate limit, or server error is inconclusive—not a passing rejection. Run a successful baseline first and again after negative cases. Capture rejection at the correct stage. Never print tokens or temporary credentials in results.

## Remaining implementation steps

1. Select personal GitHub owner and cloud account/project/subscription; establish sign-in.
2. Create a public repository, initialize the actual issuer, and publish `docs/` with Pages.
3. Verify both public URLs return the expected documents and key.
4. Add infrastructure and exchange/invocation adapters for the selected accounts.
5. Deploy one private hello-world endpoint per cloud and run the live matrix.
6. Save observed results separately from expectations; remove test resources after the demonstration.

Target minimal pay-per-use resources and no warm instances. Free allowance eligibility, billing activation, storage, build and logging charges must be checked in the selected accounts before deployment; zero cost has not been established.

## Primary references

- [AWS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
- [AWS OIDC claim condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html#condition-keys-wif)
- [GCP federation with other providers](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-providers)
- [Cloud Run federation flow](https://docs.cloud.google.com/iam/docs/tutorial-cloud-run-workload-id-federation)
- [Entra external issuer trust](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust)
- [Entra flexible credential limits](https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-flexible-federated-identity-credentials)
- [Azure application authorization](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad)
- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
