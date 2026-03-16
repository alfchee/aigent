export type E2EEState = {
  enabled: boolean
  hasKey: boolean
}

async function getKeyMaterial(passphrase: string) {
  const enc = new TextEncoder()
  return crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, [
    'deriveKey',
  ])
}

async function deriveKey(passphrase: string, salt: Uint8Array) {
  const material = await getKeyMaterial(passphrase)
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: 150_000,
      hash: 'SHA-256',
    },
    material,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export type EncryptedPayload = {
  v: 1
  salt: string
  iv: string
  ct: string
}

function b64(bytes: Uint8Array) {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s)
}

function unb64(s: string) {
  const bin = atob(s)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

export async function encryptText(
  passphrase: string,
  plaintext: string,
): Promise<EncryptedPayload> {
  const enc = new TextEncoder()
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(passphrase, salt)
  const ct = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    enc.encode(plaintext),
  )
  return {
    v: 1,
    salt: b64(salt),
    iv: b64(iv),
    ct: b64(new Uint8Array(ct)),
  }
}

export async function decryptText(
  passphrase: string,
  payload: EncryptedPayload,
): Promise<string> {
  const dec = new TextDecoder()
  const salt = unb64(payload.salt)
  const iv = unb64(payload.iv)
  const data = unb64(payload.ct)
  const key = await deriveKey(passphrase, salt)
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, data)
  return dec.decode(pt)
}
