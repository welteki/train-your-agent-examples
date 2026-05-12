#!/usr/bin/env node
// encrypt-test.js — generate a test cipher payload for local-run testing
// Usage: node encrypt-test.js '{"user":"alice","amount":42}'
'use strict'

const crypto = require('crypto')
const fs = require('fs')

const KEY_FILE = '.secrets/master-key'
const key = Buffer.from(fs.readFileSync(KEY_FILE, 'utf8').trim(), 'hex')

const plaintext = process.argv[2] || JSON.stringify({ hello: 'world', value: 123 })

const iv = crypto.randomBytes(16)
const cipher = crypto.createCipheriv('aes-128-cbc', key, iv)
const encrypted = Buffer.concat([cipher.update(Buffer.from(plaintext, 'utf8')), cipher.final()])

// prepend IV to ciphertext, then base64-encode the whole thing
const combined = Buffer.concat([iv, encrypted])
const cipherB64 = combined.toString('base64')

const payload = { cipher: cipherB64 }
console.log(JSON.stringify(payload, null, 2))
console.log('\n# curl command:')
console.log(`curl -s http://127.0.0.1:8080 -H 'Content-Type: application/json' -d '${JSON.stringify(payload)}'`)
