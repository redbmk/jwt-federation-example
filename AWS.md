# AWS deployment and live verification

Status: AWS login and CloudFormation template validation succeeded on September 24, 2026. No cloud resources have been deployed yet. The published issuer returned 404 and GitHub reported Pages was not enabled. Enable Pages and rerun its workflow before deployment.

## Enable the public issuer first

Open the repository's [Pages settings](https://github.com/redbmk/jwt-federation-example/settings/pages), select **GitHub Actions** as the source, then rerun [Publish OIDC issuer to Pages](https://github.com/redbmk/jwt-federation-example/actions/workflows/pages.yml).

These must both return JSON:

- https://redbmk.github.io/jwt-federation-example/.well-known/openid-configuration
- https://redbmk.github.io/jwt-federation-example/jwks.json

## Deploy

From the repository root, replace YOUR_ACCOUNT_ID with your intended 12-digit account ID:

```sh
python3 scripts/aws-deploy.py --account YOUR_ACCOUNT_ID
```

Defaults are profile `jwt-federation-example` and region `us-west-2`; override with `--profile` and `--region`. The script verifies the active account and compares the published discovery/JWKS with local files before creating resources. All resources are managed in the `jwt-federation-example` CloudFormation stack.

The template creates:

- An OIDC provider trusting our Pages issuer and `byo-idp-poc` audience.
- One Python 3.13 hello-world Lambda with 128 MB memory and a three-second timeout.
- An execution role with no additional AWS permissions. This deliberately omits CloudWatch logging permissions for the minimal demo; responses include the Lambda request ID instead.
- An invocation role whose trust policy requires our issuer, audience and exact `sub` of `client:client-a:agent:agent-a`. Its only resource permission is invoking this Lambda.
- A control role with the same federation trust but no invocation permissions.

There is no public Function URL, API Gateway, warm/provisioned capacity, scheduled invocation, or additional storage service. Deployment capabilities acknowledge IAM role creation. If another OIDC provider for this exact URL already exists, stop and inspect it rather than deleting or taking ownership of it.

## Run live tests

```sh
python3 scripts/aws-test.py --account YOUR_ACCOUNT_ID
```

The local signing key must match the published JWKS. Test tokens are regenerated immediately before the run. IAM changes may take a short time to propagate; if the initial valid baseline fails, investigate the reported code and rerun after propagation. A failed baseline stops the test suite.

The operator profile only reads stack outputs and the current account. Token exchanges are unsigned AWS requests containing our external JWT. Lambda calls use only the credentials returned by STS; the runner clears inherited AWS credentials and disables profile/metadata fallback for those calls.

Results are written to ignored `.local/aws-results.json`. Tokens and AWS temporary credentials are not included. The runner records Lambda request IDs for successful invocations. STS errors are recorded as codes, without raw responses or request IDs. Provider communication/unknown CLI failures are inconclusive. Review InvalidIdentityToken cases alongside both successful baselines because that code can also indicate issuer configuration problems.

The matrix distinguishes changing `client_id` or `agent_id` alone from changing the enforced subject. The custom-claim-only mutations are expected to succeed on AWS: those fields are not automatically IAM condition keys. Expiry, signature, audience, issuer, subject and `azp` mutations are also probed; future `nbf` is recorded as an observation without assuming an outcome. Finally, valid federation through the control role must fail invocation, and an unsigned invocation must fail.

## Cost and cleanup

This performs only a handful of tiny on-demand invocations. Account age or light usage alone does not establish free-tier eligibility; check your account's Billing/Free Tier view. No cost guarantee has been made. AWS lists request and compute allowances on its [Lambda pricing page](https://aws.amazon.com/lambda/pricing/).

To delete ONLY this experiment's stack, after confirming you are in the intended account:

```sh
aws sts get-caller-identity --profile jwt-federation-example
aws cloudformation delete-stack --stack-name jwt-federation-example --profile jwt-federation-example --region us-west-2
aws cloudformation wait stack-delete-complete --stack-name jwt-federation-example --profile jwt-federation-example --region us-west-2
```

This removes the function, roles and OIDC provider owned by the stack. It does not delete your setup IAM user, GitHub repository, Pages site, or local signing key. CloudFormation/CloudTrail service history can remain. An issued STS credential may remain valid until its expiry; deleting the role/function removes the invocation target and permissions.
