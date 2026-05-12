'use strict'

const crypto = require('crypto')
const fs = require('fs')

const SECRET_PATH = '/var/openfaas/secrets/master-key'
const ALGORITHM = 'aes-128-cbc'
const IV_LENGTH = 16 // bytes

function loadMasterKey () {
  const raw = fs.readFileSync(SECRET_PATH, 'utf8').trim()
  const key = Buffer.from(raw, 'hex')
  if (key.length !== 16) {
    throw new Error(`master-key must be 16 bytes (32 hex chars), got ${key.length}`)
  }
  return key
}

function decrypt (cipherB64, key) {
  const buf = Buffer.from(cipherB64, 'base64')
  if (buf.length <= IV_LENGTH) {
    throw new Error('cipher text too short — expected IV prepended to ciphertext')
  }
  const iv = buf.subarray(0, IV_LENGTH)
  const encrypted = buf.subarray(IV_LENGTH)
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv)
  const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()])
  return decrypted.toString('utf8')
}

module.exports = async (event, context) => {
  let body
  try {
    body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body
  } catch (e) {
    return context.status(400).fail('invalid JSON body')
  }

  if (!body || !body.cipher) {
    return context.status(400).fail('missing required field: cipher')
  }

  let key
  try {
    key = loadMasterKey()
  } catch (e) {
    console.error('failed to load master-key:', e.message)
    return context.status(500).fail('could not load master key')
  }

  let plaintext
  try {
    plaintext = decrypt(body.cipher, key)
  } catch (e) {
    console.error('decryption failed:', e.message)
    return context.status(422).fail('decryption failed: ' + e.message)
  }

  let payload
  try {
    payload = JSON.parse(plaintext)
  } catch (e) {
    return context.status(422).fail('decrypted payload is not valid JSON')
  }

  payload.processedAt = new Date().toUTCString()

  return context
    .status(200)
    .headers({ 'Content-Type': 'application/json' })
    .succeed(JSON.stringify(payload))
}
