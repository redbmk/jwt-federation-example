import { generateKeyPairSync, createPublicKey, createHash, sign } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export function generateKey() {
  return generateKeyPairSync('rsa', { modulusLength: 2048 }).privateKey
    .export({ type: 'pkcs8', format: 'pem' });
}
export function jwkFor(key) {
  const jwk = createPublicKey(key).export({ format: 'jwk' });
  const kid = createHash('sha256').update(JSON.stringify({ e: jwk.e, kty: jwk.kty, n: jwk.n })).digest('base64url');
  return { ...jwk, kid, use: 'sig', alg: 'RS256' };
}
export function mint(key, claims) {
  const encode = x => Buffer.from(JSON.stringify(x)).toString('base64url');
  const input = `${encode({ alg: 'RS256', typ: 'JWT', kid: jwkFor(key).kid })}.${encode(claims)}`;
  return `${input}.${sign('RSA-SHA256', Buffer.from(input), key).toString('base64url')}`;
}
export function cases(issuer, audience, now = Math.floor(Date.now() / 1000)) {
  const valid = { iss: issuer, aud: audience, sub: 'client:client-a:agent:agent-a', client_id: 'client-a', agent_id: 'agent-a', iat: now - 30, exp: now + 300 };
  const without = name => Object.fromEntries(Object.entries(valid).filter(([k]) => k !== name));
  return {
    valid,
    wrong_issuer: { ...valid, iss: `${issuer}/untrusted` },
    wrong_audience: { ...valid, aud: 'other-audience' },
    other_client: { ...valid, sub: 'client:client-b:agent:agent-a', client_id: 'client-b' },
    other_agent: { ...valid, sub: 'client:client-a:agent:agent-b', agent_id: 'agent-b' },
    changed_client_claim_only: { ...valid, client_id: 'client-b' },
    changed_agent_claim_only: { ...valid, agent_id: 'agent-b' },
    missing_client_claim: without('client_id'),
    missing_agent_claim: without('agent_id'),
    missing_subject: without('sub'),
    expired: { ...valid, iat: now - 7200, exp: now - 3600 },
    future_not_before: { ...valid, nbf: now + 3600, exp: now + 7200 },
    wrong_authorized_party: { ...valid, azp: 'other-client' }
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [command, issuer, audience] = process.argv.slice(2);
  if (!['init', 'mint'].includes(command) || !issuer || (command === 'mint' && !audience)) {
    throw new Error('Usage: node issuer.mjs init https://OWNER.github.io/REPO | node issuer.mjs mint ISSUER AUDIENCE');
  }
  const url = new URL(issuer);
  if (url.protocol !== 'https:' || url.search || url.hash || url.username || url.password || issuer.endsWith('/')) {
    throw new Error('Issuer must be HTTPS, without credentials, query, fragment or trailing slash.');
  }
  mkdirSync('.local', { recursive: true, mode: 0o700 });
  if (command === 'init') {
    // Exclusive creation prevents accidental key rotation after deployment.
    const key = generateKey();
    writeFileSync('.local/private.pem', key, { mode: 0o600, flag: 'wx' });
    mkdirSync('docs/.well-known', { recursive: true });
    writeFileSync('docs/.nojekyll', '');
    writeFileSync('docs/jwks.json', JSON.stringify({ keys: [jwkFor(key)] }, null, 2) + '\n');
    writeFileSync('docs/.well-known/openid-configuration', JSON.stringify({
      issuer, jwks_uri: `${issuer}/jwks.json`,
      response_types_supported: ['id_token'], subject_types_supported: ['public'],
      id_token_signing_alg_values_supported: ['RS256']
    }, null, 2) + '\n');
    console.log('Created public discovery/JWKS in docs/ and local-only signing key in .local/.');
  } else {
    const key = readFileSync('.local/private.pem');
    const publicKeys = JSON.parse(readFileSync('docs/jwks.json')).keys;
    if (!publicKeys.some(k => k.kid === jwkFor(key).kid)) throw new Error('Key does not match published JWKS.');
    const claims = cases(issuer, audience);
    mkdirSync('.local/tokens', { recursive: true, mode: 0o700 });
    for (const [name, value] of Object.entries(claims)) {
      writeFileSync(`.local/tokens/${name}.jwt`, mint(key, value), { mode: 0o600 });
    }
    // Use the trusted kid with a different signing key to isolate signature rejection.
    const validToken = mint(key, claims.valid);
    const input = validToken.split('.').slice(0, 2).join('.');
    const signature = sign('RSA-SHA256', Buffer.from(input), generateKey()).toString('base64url');
    writeFileSync('.local/tokens/invalid_signature.jwt', `${input}.${signature}`, { mode: 0o600 });
    console.log(`Created ${Object.keys(claims).length + 1} local test tokens. No cloud requests made.`);
  }
}
