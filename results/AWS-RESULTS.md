# AWS federation: observed results

Run: 2026-09-25T15:52:42.875764+00:00. Region: us-west-2.

16 expected-outcome checks passed; one additional observation confirmed rejection of a token whose nbf is in the future. The CloudFormation stack jwt-federation-example is deployed and remains available.

| Case | Token exchange | Function invocation | Result |
|---|---|---|---|
| valid | allowed | allowed | pass |
| wrong_issuer | denied | not attempted | pass |
| wrong_audience | denied | not attempted | pass |
| other_client | denied | not attempted | pass |
| other_agent | denied | not attempted | pass |
| changed_client_claim_only | allowed | allowed | pass |
| changed_agent_claim_only | allowed | allowed | pass |
| missing_client_claim | allowed | allowed | pass |
| missing_agent_claim | allowed | allowed | pass |
| missing_subject | denied | not attempted | pass |
| expired | denied | not attempted | pass |
| invalid_signature | denied | not attempted | pass |
| future_not_before | denied | not attempted | observed |
| wrong_authorized_party | denied | not attempted | pass |
| valid_after_negatives | allowed | allowed | pass |
| valid_identity_without_invoke_permission | allowed | denied | pass |
| unsigned_invocation | not applicable | denied | pass |

The valid JWT invoked hello-world both before and after the negative cases. Changing the subject to a different client or agent was rejected. Changing or removing only the custom client_id or agent_id fields still allowed access because this policy does not inspect those fields. A second role accepted the same valid JWT but could not invoke Lambda; unsigned invocation was also rejected.

These are live AWS observations, not simulated policy checks. The operator profile was used only to read identity and stack outputs during testing; invocation used isolated temporary STS credentials. Some InvalidIdentityToken responses are generic and do not identify the exact internal validation check. The wrong-issuer probe uses an unregistered issuer, not yet a second configured IdP. GCP, Azure, and the two-configured-issuer/shared-key scenario remain untested.

The discovery document downloaded by browsers was accepted by AWS in this run. The original test run found a reporting bug for ExpiredTokenException; after correcting its classification, the complete suite was rerun successfully.

Reproduce and clean up using AWS.md in the repository. No credentials or JWTs are included in this report.
