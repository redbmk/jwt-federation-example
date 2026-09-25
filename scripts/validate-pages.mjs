import assert from 'node:assert/strict';
import { readFileSync, readdirSync, lstatSync } from 'node:fs';
import { createPublicKey } from 'node:crypto';

const issuer = 'https://redbmk.github.io/jwt-federation-example';
const allowed = new Set(['.nojekyll', '.well-known/openid-configuration', 'jwks.json']);
function walk(dir, prefix = '') {
  for (const name of readdirSync(dir)) {
    const relative = `${prefix}${name}`;
    const path = `${dir}/${name}`;
    const stat = lstatSync(path);
    assert.ok(!stat.isSymbolicLink(), `Unexpected symlink: ${path}`);
    if (stat.isDirectory()) {
      assert.equal(relative, '.well-known', `Unexpected directory: ${path}`);
      walk(path, `${relative}/`);
    } else {
      assert.ok(allowed.has(relative), `Unexpected public file: ${path}`);
      assert.ok(stat.isFile(), `Not a regular file: ${path}`);
      assert.equal(stat.nlink, 1, `Unexpected hard link: ${path}`);
    }
  }
}
walk('docs');
const metadata = JSON.parse(readFileSync('docs/.well-known/openid-configuration'));
assert.equal(metadata.issuer, issuer);
assert.equal(metadata.jwks_uri, `${issuer}/jwks.json`);
assert.ok(metadata.id_token_signing_alg_values_supported.includes('RS256'));
const { keys } = JSON.parse(readFileSync('docs/jwks.json'));
assert.ok(Array.isArray(keys) && keys.length > 0, 'JWKS must contain a key');
const kids = new Set();
for (const key of keys) {
  assert.equal(key.kty, 'RSA');
  assert.equal(key.use, 'sig');
  assert.equal(key.alg, 'RS256');
  assert.ok(typeof key.kid === 'string' && key.kid.length > 0);
  assert.ok(!kids.has(key.kid), 'Duplicate kid');
  kids.add(key.kid);
  for (const field of Object.keys(key)) {
    assert.ok(['kty', 'n', 'e', 'kid', 'use', 'alg'].includes(field), `Unexpected JWK field: ${field}`);
  }
  const publicKey = createPublicKey({ key, format: 'jwk' });
  assert.ok(publicKey.asymmetricKeyDetails.modulusLength >= 2048);
}
console.log('Public discovery and JWKS validated; only expected public files will be uploaded.');
