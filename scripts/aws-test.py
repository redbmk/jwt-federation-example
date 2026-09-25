"""Live AWS federation tests. Requires AWS CLI, Node, and a deployed stack.

Credentials are captured in memory only. Test invocations cannot inherit the
operator's profile or ambient credentials. Errors are recorded as codes only.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--profile', default='jwt-federation-example')
parser.add_argument('--region', default='us-west-2')
parser.add_argument('--stack', default='jwt-federation-example')
args = parser.parse_args()
args.account = os.environ.get('AWS_ACCOUNT_ID', '')
if len(args.account) != 12 or not args.account.isascii() or not args.account.isdigit():
    raise SystemExit('Set AWS_ACCOUNT_ID to the intended 12-digit account ID; no requests made.')
root = Path(__file__).resolve().parents[1]
os.chdir(root)
local = root / '.local'
local.mkdir(mode=0o700, exist_ok=True)
last_error_message = None

def call(parts, credentials=None, operator=False):
    global last_error_message
    last_error_message = None
    env = {k: v for k, v in os.environ.items() if not k.startswith('AWS_')}
    env.update(AWS_PAGER='', AWS_EC2_METADATA_DISABLED='true')
    command = ['aws', '--region', args.region, '--output', 'json', '--no-cli-pager']
    if operator:
        command += ['--profile', args.profile]
    else:
        env.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull)
        if credentials:
            env.update(AWS_ACCESS_KEY_ID=credentials['AccessKeyId'],
                       AWS_SECRET_ACCESS_KEY=credentials['SecretAccessKey'],
                       AWS_SESSION_TOKEN=credentials['SessionToken'])
        else:
            command += ['--no-sign-request']
    p = subprocess.run(command + parts, env=env, capture_output=True, text=True, timeout=90)
    if p.returncode:
        match = re.search(r'An error occurred \(([^)]+)\)', p.stderr)
        # Keep the service explanation, not command arguments or credentials.
        message = p.stderr.split('operation: ', 1)[-1].strip() if match else ''
        message = re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[JWT REDACTED]', message)
        last_error_message = message[:1000] or None
        return None, match.group(1) if match else 'CLI_OR_NETWORK_ERROR'
    return json.loads(p.stdout) if p.stdout.strip() else {}, None

def require(parts):
    data, error = call(parts, operator=True)
    if error:
        raise RuntimeError(f'Operator request failed: {error}')
    return data

identity = require(['sts', 'get-caller-identity'])
if identity['Account'] != args.account:
    sys.exit('Account mismatch; no tests run.')
stack = require(['cloudformation', 'describe-stacks', '--stack-name', args.stack])['Stacks'][0]
outputs = {x['OutputKey']: x['OutputValue'] for x in stack['Outputs']}
for value in outputs.values():
    if f':{args.account}:' not in value:
        sys.exit('Unexpected output account.')
subprocess.run(['node', 'issuer.mjs', 'mint', 'https://redbmk.github.io/jwt-federation-example', 'byo-idp-poc'], check=True)

def exchange(name, denied=False):
    return call(['sts', 'assume-role-with-web-identity',
                 '--role-arn', outputs['DeniedRoleArn' if denied else 'InvokerRoleArn'],
                 '--role-session-name', 'poc-' + name.replace('_', '-')[:40],
                 '--duration-seconds', '900',
                 '--web-identity-token', 'file://' + str(local / 'tokens' / f'{name}.jwt')])

def invoke(credentials=None):
    target = local / 'invoke-response.json'
    target.unlink(missing_ok=True)
    data, error = call(['lambda', 'invoke', '--function-name', outputs['FunctionArn'], str(target)], credentials)
    if error:
        return {'status': 'denied' if error in {'AccessDeniedException', 'MissingAuthenticationTokenException'} else 'error', 'code': error}
    body = json.loads(target.read_text())
    if data.get('FunctionError') or body.get('message') != 'hello world':
        return {'status': 'error', 'code': 'FUNCTION_FAILED'}
    return {'status': 'allowed', 'body': body}

expected = {
    'valid': 'allow', 'wrong_issuer': 'deny', 'wrong_audience': 'deny',
    'other_client': 'deny', 'other_agent': 'deny',
    'changed_client_claim_only': 'allow', 'changed_agent_claim_only': 'allow',
    'missing_client_claim': 'allow', 'missing_agent_claim': 'allow',
    'missing_subject': 'deny', 'expired': 'deny', 'invalid_signature': 'deny',
    'future_not_before': 'observe', 'wrong_authorized_party': 'deny'
}
results = []
for name, expectation in list(expected.items()) + [('valid', 'allow')]:
    data, error = exchange(name)
    row = {'case': name if not (name == 'valid' and results) else 'valid_after_negatives', 'expected': expectation}
    if error:
        # Fetch failures and transient STS failures are not successful denials.
        infrastructure_error = any(text in (last_error_message or '').lower() for text in [
            'retrieve verification key', 'could not connect', 'could not be reached',
            'communication', 'timed out', 'timeout', 'jwks', 'discovery'
        ])
        denial = not infrastructure_error and error in {'AccessDenied', 'InvalidIdentityToken', 'ExpiredToken', 'ExpiredTokenException', 'IDPRejectedClaim'}
        row.update(exchange='denied' if denial else 'error', code=error)
        row['message'] = last_error_message
        row['pass'] = denial and expectation == 'deny'
        if error == 'InvalidIdentityToken':
            # Baselines bracket the negatives; retain the code for manual review.
            row['note'] = 'Review alongside successful baselines; may also indicate issuer/JWKS configuration errors.'
    else:
        row['exchange'] = 'allowed'
        row['invocation'] = invoke(data['Credentials'])
        row['pass'] = expectation == 'allow' and row['invocation']['status'] == 'allowed'
    if expectation == 'observe':
        row['pass'] = None
    results.append(row)
    print(json.dumps(row), flush=True)
    if name == 'valid' and not row['pass']:
        break

if len(results) == len(expected) + 1:
    data, error = exchange('valid', denied=True)
    row = {'case': 'valid_identity_without_invoke_permission', 'exchange': 'allowed' if data else 'error', 'code': error}
    if data:
        row['invocation'] = invoke(data['Credentials'])
    row['pass'] = bool(data and row['invocation']['status'] == 'denied')
    results.append(row)
    print(json.dumps(row), flush=True)
    row = {'case': 'unsigned_invocation', 'invocation': invoke()}
    row['pass'] = row['invocation']['status'] == 'denied'
    results.append(row)
    print(json.dumps(row), flush=True)

report = {'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'region': args.region, 'results': results}
(local / 'aws-results.json').write_text(json.dumps(report, indent=2) + '\n')
sys.exit(1 if any(r.get('pass') is False for r in results) else 0)
