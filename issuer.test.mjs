import test from 'node:test';
import assert from 'node:assert/strict';
import { createPublicKey, verify } from 'node:crypto';
import { generateKey, jwkFor, mint, cases } from './issuer.mjs';

test('public JWKS verifies issued JWT and rejects altered payload', () => {
  const key = generateKey();
  const jwk = jwkFor(key);
  for (const secret of ['d', 'p', 'q', 'dp', 'dq', 'qi']) assert.equal(jwk[secret], undefined);
  const publicKey = createPublicKey({ key: jwk, format: 'jwk' });
  const claims = cases('https://example.org/poc', 'test-audience').valid;
  const [header, payload, signature] = mint(key, claims).split('.');
  assert.equal(JSON.parse(Buffer.from(header, 'base64url')).kid, jwk.kid);
  assert.equal(verify('RSA-SHA256', Buffer.from(`${header}.${payload}`), publicKey, Buffer.from(signature, 'base64url')), true);
  const tampered = Buffer.from(JSON.stringify({ ...claims, client_id: 'client-b' })).toString('base64url');
  assert.equal(verify('RSA-SHA256', Buffer.from(`${header}.${tampered}`), publicKey, Buffer.from(signature, 'base64url')), false);
});

test('claim-only probes keep subject fixed; identity probes change subject', () => {
  const c = cases('https://example.org/poc', 'aud', 10000);
  assert.equal(c.changed_client_claim_only.sub, c.valid.sub);
  assert.equal(c.changed_agent_claim_only.sub, c.valid.sub);
  assert.notEqual(c.other_client.sub, c.valid.sub);
  assert.notEqual(c.other_agent.sub, c.valid.sub);
  assert.ok(c.expired.exp < 10000);
  assert.ok(c.future_not_before.nbf > 10000);
});
