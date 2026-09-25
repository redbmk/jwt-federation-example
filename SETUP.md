# Account setup: what you do, what I do

Repository: `redbmk/jwt-federation-example` (public).
Issuer: `https://redbmk.github.io/jwt-federation-example`.

Recommended workflow: you push the repository and complete browser sign-in, MFA, and any account/billing enrollment. GitHub Actions publishes the public keys; I use local cloud sessions to provision the cloud resources, run tests, and document commands and results. No API keys or passwords need to be pasted into chat. Browser-only sign-in does not automatically sign in the command-line tools.

We can start with GitHub and whichever ONE cloud you can access first. You do not have to finish all three before we begin.

## 1. Install the tools on this Mac

Homebrew is already installed. Run these in Terminal:

```sh
brew install gh awscli azure-cli
brew install --cask gcloud-cli
```

If `gcloud` is not found afterward, follow the installer's printed PATH instructions, then reopen Terminal. Verify:

```sh
gh --version
aws --version
gcloud --version
az version
```

You can install only `gh` and the first cloud's tool initially. These commands install software; they do not create cloud resources.

## 2. GitHub

The local repository is ready at `~/code/jwt-federation-example`. Push it to a public `redbmk/jwt-federation-example` repository using your preferred Git workflow. GitHub CLI sign-in is optional if you already have another way to push.

After pushing:

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Open **Actions → Publish OIDC issuer to Pages → Run workflow** on `main`. Rerun an earlier failed deployment if it started before Pages was enabled.
4. Wait for the workflow to finish, then open both URLs:
   - https://redbmk.github.io/jwt-federation-example/.well-known/openid-configuration
   - https://redbmk.github.io/jwt-federation-example/jwks.json

Subsequent pushes to `main` publish automatically. No GitHub Actions secrets are needed. The signing key has been generated locally and stays in ignored `.local/private.pem`; only public key material goes into `docs/`. Do not regenerate it in CI. A fresh clone will need the original private key to mint tokens that match the published JWKS.

Tell me **Pages ready** when both URLs work. GitHub Pages hosting and GitHub Actions' built-in OIDC issuer are different things. This experiment uses our Pages URL as the issuer.

## 3. AWS

1. Open [AWS Console](https://console.aws.amazon.com/) and recover/sign into your personal account. If you need a new account, use [AWS Free Tier signup](https://aws.amazon.com/free/) and complete its account verification yourself.
2. Use an existing non-root administrative identity in your personal sandbox if you have one. If you only have the root account, tell me; we can establish a suitable setup identity before provisioning. Do not create permanent access keys just for this experiment.
3. For an IAM user/role with console access, use current AWS CLI browser login:

```sh
aws login --profile jwt-federation-example --region us-west-2
aws sts get-caller-identity --profile jwt-federation-example
```

`aws login` requires AWS CLI 2.32.0 or later. AWS documents the `SignInLocalDevelopmentAccess` managed policy as a login prerequisite for IAM identities. This enables local sign-in, not deployment access. If denied, send the error text (not tokens); I can help resolve the exact missing permission.

If you already use IAM Identity Center, use its login instead:

```sh
aws configure sso --profile jwt-federation-example
aws sso login --profile jwt-federation-example
aws sts get-caller-identity --profile jwt-federation-example
```

The SSO wizard asks for your existing access-portal/start URL and SSO region. Do not set up Identity Center solely to follow this alternative if normal console login works.

Tell me: **AWS ready**, the intended account ID, and whether this is a trial/free-plan or paid account. The profile name above lets me use the selected identity without changing your default profile. I will inspect permissions and eligibility, then create a dedicated OIDC provider, narrowly scoped invocation role, execution role, and small Lambda. The setup identity needs permission to manage these resources, including passing the Lambda execution role; test tokens will receive only invocation access.

## 4. Google Cloud

1. Open [Google Cloud Console](https://console.cloud.google.com/) using your personal Google account. If necessary, enroll through [Google Cloud Free Trial](https://cloud.google.com/free).
2. In the project selector, choose **New project**, name it `jwt-federation-example`, and note its globally unique **project ID** (different from its display name). Use **No organization** for a personal account when offered. An existing empty personal sandbox project also works.
3. In **Billing**, link that project to your trial or other intended billing account. Cloud Run deployment requires billing even when expected usage is within a free allowance. Complete any payment/account verification yourself.
4. Authenticate locally:

```sh
gcloud auth login
gcloud projects list --format='table(projectId,name)'
```

Tell me: **GCP ready**, the project ID, the Google account to use if you signed in more than one, and whether billing is linked. I will pass the selected project/account explicitly rather than rely on your existing defaults.

You don't need to create a service-account key or run `gcloud auth application-default login` for the CLI-based setup. If a later deployment tool requires Application Default Credentials, we'll establish that separately.

I will enable required APIs, create the workload identity pool/provider and service accounts, configure claim conditions, and deploy a private Cloud Run hello-world service. Your setup identity must be able to manage IAM and services in the project; the project creator commonly has Owner in a personal project. An organization may impose additional restrictions. If permission is missing, I will identify the specific missing access rather than ask for an unrelated API key.

## 5. Azure

1. Open [Azure Portal](https://portal.azure.com/) with your personal Microsoft account. If needed, enroll through [Azure free-account signup](https://azure.microsoft.com/en-us/free/).
2. Open **Subscriptions** and identify an enabled personal subscription. A Microsoft login alone is not enough; this needs an Azure subscription and its associated Microsoft Entra tenant.
3. Sign in and list available subscriptions:

```sh
az login
az account list --query '[].{name:name,id:id,tenantId:tenantId,state:state}' --output table
```

Choose the personal subscription in the sign-in selector. If your tenant does not appear, we can retry with `az login --tenant TENANT_ID`.

Tell me: **Azure ready**, the subscription ID, tenant ID, and whether this is a trial/free or paid subscription.

I will create a dedicated resource group, the function/storage resources, Entra app registrations, and the federated credential; then restrict function invocation to the intended application. Azure resource access and Entra application-registration access are separate: Contributor at the intended scope allows most resource creation, while Entra must separately allow you to register/manage apps. If we need an Azure role assignment, the setup identity also needs permission to create that assignment (Contributor alone does not). We will inspect the actual requirements before requesting any additional role.

## What to send back

Send whichever are ready; these are identifiers, not credentials:

```text
GitHub: redbmk — signed in / not yet
AWS: account ID, profile jwt-federation-example, free/trial/paid
GCP: project ID, billing linked yes/no, signed-in account if ambiguous
Azure: subscription ID, tenant ID, free/trial/paid
```

You handle passwords, MFA, account recovery and billing enrollment. I can drive ordinary setup screens if useful, but the repeatable deployment will live in this repository. I will record created resources, exact setup commands, observed test outcomes and cleanup steps. Local filesystem/network grants may still be needed for tools to use local sessions.

Free-tier eligibility varies by account and plan; it is not a universal zero-dollar guarantee. We will inspect the selected plan before deployment, use minimal consumption resources, and document cleanup. Budget alerts, if used, are notifications rather than a hard spending cap.

## Documentation sources

- [GitHub browser login](https://cli.github.com/manual/gh_auth_login)
- [Homebrew GitHub CLI](https://formulae.brew.sh/formula/gh), [AWS CLI](https://formulae.brew.sh/formula/awscli), [Azure CLI](https://formulae.brew.sh/formula/azure-cli), [Google CLI installation](https://docs.cloud.google.com/sdk/docs/downloads-homebrew)
- [AWS console-based CLI login and permissions](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [Google CLI authentication](https://docs.cloud.google.com/sdk/docs/authenticate)
- [Azure interactive login](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-interactively)

Written September 24, 2026. Account-specific capabilities and actual deployment results remain to be checked.
