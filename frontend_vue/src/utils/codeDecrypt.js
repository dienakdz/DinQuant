/**
 * Indicator code decryption tool
 * Used to decrypt encrypted indicator code purchased by users
 */

import CryptoJS from 'crypto-js'
import request from '@/utils/request'

/**
 * Decrypt indicator code
 *
 * @param {string} encryptedCode - base64 encoded encrypted code
 * @param {number} userId - User ID
 * @param {number} indicatorId - Indicator ID
 * @param {string} serverSecret - Server secret (needs to be from backend or config)
 * @returns {string} - Decrypted code
 */
export function decryptCode (encryptedCode, userId, indicatorId, encryptedKey) {
  if (!encryptedCode || !userId || !indicatorId || !encryptedKey) {
    return encryptedCode
  }

  try {
    // Decode base64 encrypted code
    const combined = CryptoJS.enc.Base64.parse(encryptedCode)

    // Extract IV (first 16 bytes) and encrypted data
    const ivWords = CryptoJS.lib.WordArray.create(combined.words.slice(0, 4)) // First 16 bytes (4 words)
    const encryptedWords = CryptoJS.lib.WordArray.create(combined.words.slice(4)) // Remaining part

    // Decryption key (base64 encoded key from backend)
    // encryptedKey is the base64 encoded key from backend, decode directly for use
    const key = CryptoJS.enc.Base64.parse(encryptedKey)

    // Decrypt
    const decrypted = CryptoJS.AES.decrypt(
      { ciphertext: encryptedWords },
      key,
      {
        iv: ivWords,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
      }
    )

    // Convert to string
    const decryptedText = decrypted.toString(CryptoJS.enc.Utf8)

    if (!decryptedText) {
      return encryptedCode
    }

    return decryptedText
  } catch (error) {
    // Decryption failed, return original code (backward compatibility)
    return encryptedCode
  }
}

/**
 * Get decryption key from backend (dynamic key)
 *
 * @param {number} userId - User ID
 * @param {number} indicatorId - Indicator ID
 * @returns {Promise<string>} - Decryption key (base64 encoded)
 */
export async function getDecryptKey (userId, indicatorId) {
  if (!userId || !indicatorId) {
    throw new Error('User ID and Indicator ID cannot be empty')
  }

  try {
    // Dynamic request: get from backend API
    const response = await request({
      url: '/api/indicator/getDecryptKey',
      method: 'post',
      data: {
        userid: userId,
        indicatorId: indicatorId
      }
    })

    if (response.code === 1 && response.data && response.data.key) {
      // Return base64 encoded key
      return response.data.key
    } else {
      throw new Error(response.msg || 'Failed to get decryption key')
    }
  } catch (error) {
    // If backend fails, throw error instead of using backup key (more secure)
    throw new Error('Cannot get decryption key, please check network or contact admin: ' + (error.message || 'Unknown error'))
  }
}

/**
 * Smart code decryption (auto-fetch key)
 *
 * @param {string} encryptedCode - Encrypted code
 * @param {number} userId - User ID
 * @param {number} indicatorId - Indicator ID
 * @returns {Promise<string>} - Decrypted code
 */
export async function decryptCodeAuto (encryptedCode, userId, indicatorId) {
  // Dynamically get decryption key from backend (base64 encoded)
  const encryptedKey = await getDecryptKey(userId, indicatorId)
  // Decrypt using the fetched key
  return decryptCode(encryptedCode, userId, indicatorId, encryptedKey)
}

/**
 * Check if code needs decryption
 *
 * @param {string} code - The code
 * @param {number} isEncrypted - Encryption flag
 * @returns {boolean}
 */
export function needsDecrypt (code, isEncrypted) {
  // If explicitly marked as encrypted, or code is long and base64 formatted, it might need decryption
  if (isEncrypted === 1 || isEncrypted === true) {
    return true
  }

  // Simple check: encrypted code is usually long (base64 increases size by ~33%)
  if (code && code.length > 100) {
    // Attempt base64 decode check
    try {
      const decoded = atob(code)
      // If decoded length is reasonable, it might be encrypted
      if (decoded.length > 50) {
        return true
      }
    } catch (e) {
      // Not base64, no decryption needed
    }
  }

  return false
}
