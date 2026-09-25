"""Deploy only after checking the account and published issuer. No dependencies."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--profile', default='jwt-federation-example')
p.add_argument('--region', default='us-west-2')
args = p.parse_args()
args.account = os.environ.get('AWS_ACCOUNT_ID', '')
if len(args.account) != 12 or not args.account.isascii() or not args.account.isdigit():
    raise SystemExit('Set AWS_ACCOUNT_ID to the intended 12-digit account ID; no requests made.')
root = Path(__file__).resolve().parents[1]
os.chdir(root)
env = {k: v for k, v in os.environ.items() if not k.startswith('AWS_')}
env['AWS_PAGER'] = ''
command = ['aws', '--profile', args.profile, '--region', args.region, '--no-cli-pager']
identity = json.loads(subprocess.check_output(command + ['sts', 'get-caller-identity', '--output', 'json'], env=env))
if identity['Account'] != args.account:
    raise SystemExit('Wrong AWS account; no resources created.')
issuer = 'https://redbmk.github.io/jwt-federation-example'
for name in ['.well-known/openid-configuration', 'jwks.json']:
    try:
        with urllib.request.urlopen(issuer + '/' + name, timeout=20) as response:
            published = json.load(response)
    except Exception as error:
        raise SystemExit(f'Cannot read public issuer file {name}: {error}. No resources created.')
    if published != json.loads((root / 'docs' / name).read_text()):
        raise SystemExit(f'Published {name} differs from local file. No resources created.')
subprocess.run(['node', 'scripts/validate-pages.mjs'], check=True, env=env)
subprocess.run(command + [
    'cloudformation', 'deploy', '--stack-name', 'jwt-federation-example',
    '--template-file', 'infra/aws-template.json', '--capabilities', 'CAPABILITY_IAM',
    '--tags', 'Project=jwt-federation-example', '--no-fail-on-empty-changeset'
], env=env, check=True)
