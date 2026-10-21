#!/usr/bin/env python3
"""
pkt_decrypt.py — Decompila arquivos .pkt do Cisco Packet Tracer.

Uso:
    ./pkt_decrypt.py <arquivo.pkt>

O XML resultante é salvo no mesmo diretório com a extensão .xml.
"""

import struct
import sys
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Twofish ────────────────────────────────────────────────────────────────────

WORD_BIGENDIAN = 0
if sys.byteorder == 'big':
    WORD_BIGENDIAN = 1

def rotr32(x, n):
    return (x >> n) | ((x << (32 - n)) & 0xFFFFFFFF)

def rotl32(x, n):
    return ((x << n) & 0xFFFFFFFF) | (x >> (32 - n))

def byteswap32(x):
    return ((x & 0xff) << 24) | (((x >> 8) & 0xff) << 16) | \
           (((x >> 16) & 0xff) << 8) | ((x >> 24) & 0xff)

class TWI:
    def __init__(self):
        self.k_len = 0
        self.l_key = [0]*40
        self.s_key = [0]*4
        self.qt_gen = 0
        self.q_tab = [[0]*256, [0]*256]
        self.mt_gen = 0
        self.m_tab = [[0]*256, [0]*256, [0]*256, [0]*256]
        self.mk_tab = [[0]*256, [0]*256, [0]*256, [0]*256]

def byte(x, n):
    return (x >> (8 * n)) & 0xff

tab_5b = [0, 90, 180, 238]
tab_ef = [0, 238, 180, 90]
ror4 = [0, 8, 1, 9, 2, 10, 3, 11, 4, 12, 5, 13, 6, 14, 7, 15]
ashx = [0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12, 5, 14, 7]
qt0 = [[8, 1, 7, 13, 6, 15, 3, 2, 0, 11, 5, 9, 14, 12, 10, 4],
       [2, 8, 11, 13, 15, 7, 6, 14, 3, 1, 9, 4, 0, 10, 12, 5]]
qt1 = [[14, 12, 11, 8, 1, 2, 3, 5, 15, 4, 10, 6, 7, 0, 9, 13],
       [1, 14, 2, 11, 4, 12, 3, 7, 6, 13, 10, 5, 15, 9, 0, 8]]
qt2 = [[11, 10, 5, 14, 6, 13, 9, 0, 12, 8, 15, 3, 2, 4, 7, 1],
       [4, 12, 7, 5, 1, 6, 9, 10, 0, 14, 13, 8, 2, 11, 3, 15]]
qt3 = [[13, 7, 15, 4, 1, 2, 6, 14, 9, 11, 3, 0, 8, 5, 12, 10],
       [11, 9, 5, 1, 12, 3, 13, 14, 6, 4, 7, 15, 2, 0, 8, 10]]

def qp(n, x):
    n %= 0x100000000
    x %= 0x100
    a0 = x >> 4
    b0 = x & 15
    a1 = a0 ^ b0
    b1 = ror4[b0] ^ ashx[a0]
    a2 = qt0[n][a1]
    b2 = qt1[n][b1]
    a3 = a2 ^ b2
    b3 = ror4[b2] ^ ashx[a2]
    a4 = qt2[n][a3]
    b4 = qt3[n][b3]
    return (b4 << 4) | a4

def gen_qtab(pkey):
    for i in range(256):
        pkey.q_tab[0][i] = qp(0, i)
        pkey.q_tab[1][i] = qp(1, i)

def gen_mtab(pkey):
    for i in range(256):
        f01 = pkey.q_tab[1][i]
        f5b = ((f01) ^ ((f01) >> 2) ^ tab_5b[(f01) & 3])
        fef = ((f01) ^ ((f01) >> 1) ^ ((f01) >> 2) ^ tab_ef[(f01) & 3])
        pkey.m_tab[0][i] = f01 + (f5b << 8) + (fef << 16) + (fef << 24)
        pkey.m_tab[2][i] = f5b + (fef << 8) + (f01 << 16) + (fef << 24)
        f01 = pkey.q_tab[0][i]
        f5b = ((f01) ^ ((f01) >> 2) ^ tab_5b[(f01) & 3])
        fef = ((f01) ^ ((f01) >> 1) ^ ((f01) >> 2) ^ tab_ef[(f01) & 3])
        pkey.m_tab[1][i] = fef + (fef << 8) + (f5b << 16) + (f01 << 24)
        pkey.m_tab[3][i] = f5b + (f01 << 8) + (fef << 16) + (f5b << 24)

def gen_mk_tab(pkey, key):
    if pkey.k_len == 2:
        for i in range(256):
            by = i % 0x100
            pkey.mk_tab[0][i] = pkey.m_tab[0][pkey.q_tab[0][pkey.q_tab[0][by] ^ byte(key[1],0)] ^ byte(key[0],0)]
            pkey.mk_tab[1][i] = pkey.m_tab[1][pkey.q_tab[0][pkey.q_tab[1][by] ^ byte(key[1],1)] ^ byte(key[0],1)]
            pkey.mk_tab[2][i] = pkey.m_tab[2][pkey.q_tab[1][pkey.q_tab[0][by] ^ byte(key[1],2)] ^ byte(key[0],2)]
            pkey.mk_tab[3][i] = pkey.m_tab[3][pkey.q_tab[1][pkey.q_tab[1][by] ^ byte(key[1],3)] ^ byte(key[0],3)]
    if pkey.k_len == 3:
        for i in range(256):
            by = i % 0x100
            pkey.mk_tab[0][i] = pkey.m_tab[0][pkey.q_tab[0][pkey.q_tab[0][pkey.q_tab[1][by] ^ byte(key[2], 0)] ^ byte(key[1], 0)] ^ byte(key[0], 0)]
            pkey.mk_tab[1][i] = pkey.m_tab[1][pkey.q_tab[0][pkey.q_tab[1][pkey.q_tab[1][by] ^ byte(key[2], 1)] ^ byte(key[1], 1)] ^ byte(key[0], 1)]
            pkey.mk_tab[2][i] = pkey.m_tab[2][pkey.q_tab[1][pkey.q_tab[0][pkey.q_tab[0][by] ^ byte(key[2], 2)] ^ byte(key[1], 2)] ^ byte(key[0], 2)]
            pkey.mk_tab[3][i] = pkey.m_tab[3][pkey.q_tab[1][pkey.q_tab[1][pkey.q_tab[0][by] ^ byte(key[2], 3)] ^ byte(key[1], 3)] ^ byte(key[0], 3)]
    if pkey.k_len == 4:
        for i in range(256):
            by = i % 0x100
            pkey.mk_tab[0][i] = pkey.m_tab[0][pkey.q_tab[0][pkey.q_tab[0][pkey.q_tab[1][pkey.q_tab[1][by] ^ byte(key[3], 0)] ^ byte(key[2], 0)] ^ byte(key[1], 0)] ^ byte(key[0], 0)]
            pkey.mk_tab[1][i] = pkey.m_tab[1][pkey.q_tab[0][pkey.q_tab[1][pkey.q_tab[1][pkey.q_tab[0][by] ^ byte(key[3], 1)] ^ byte(key[2], 1)] ^ byte(key[1], 1)] ^ byte(key[0], 1)]
            pkey.mk_tab[2][i] = pkey.m_tab[2][pkey.q_tab[1][pkey.q_tab[0][pkey.q_tab[0][pkey.q_tab[0][by] ^ byte(key[3], 2)] ^ byte(key[2], 2)] ^ byte(key[1], 2)] ^ byte(key[0], 2)]
            pkey.mk_tab[3][i] = pkey.m_tab[3][pkey.q_tab[1][pkey.q_tab[1][pkey.q_tab[0][pkey.q_tab[1][by] ^ byte(key[3], 3)] ^ byte(key[2], 3)] ^ byte(key[1], 3)] ^ byte(key[0], 3)]

def h_fun(pkey, x, key):
    b0 = byte(x, 0)
    b1 = byte(x, 1)
    b2 = byte(x, 2)
    b3 = byte(x, 3)
    if pkey.k_len >= 4:
        b0 = pkey.q_tab[1][b0] ^ byte(key[3], 0)
        b1 = pkey.q_tab[0][b1] ^ byte(key[3], 1)
        b2 = pkey.q_tab[0][b2] ^ byte(key[3], 2)
        b3 = pkey.q_tab[1][b3] ^ byte(key[3], 3)
    if pkey.k_len >= 3:
        b0 = pkey.q_tab[1][b0] ^ byte(key[2], 0)
        b1 = pkey.q_tab[1][b1] ^ byte(key[2], 1)
        b2 = pkey.q_tab[0][b2] ^ byte(key[2], 2)
        b3 = pkey.q_tab[0][b3] ^ byte(key[2], 3)
    if pkey.k_len >= 2:
        b0 = pkey.q_tab[0][pkey.q_tab[0][b0] ^ byte(key[1], 0)] ^ byte(key[0], 0)
        b1 = pkey.q_tab[0][pkey.q_tab[1][b1] ^ byte(key[1], 1)] ^ byte(key[0], 1)
        b2 = pkey.q_tab[1][pkey.q_tab[0][b2] ^ byte(key[1], 2)] ^ byte(key[0], 2)
        b3 = pkey.q_tab[1][pkey.q_tab[1][b3] ^ byte(key[1], 3)] ^ byte(key[0], 3)
    return pkey.m_tab[0][b0] ^ pkey.m_tab[1][b1] ^ pkey.m_tab[2][b2] ^ pkey.m_tab[3][b3]

def mds_rem(p0, p1):
    for _ in range(8):
        t = p1 >> 24
        p1 = ((p1 << 8) & 0xffffffff) | (p0 >> 24)
        p0 = (p0 << 8) & 0xffffffff
        u = (t << 1) & 0xffffffff
        if t & 0x80:
            u ^= 0x0000014d
        p1 ^= t ^ ((u << 16) & 0xffffffff)
        u ^= (t >> 1)
        if t & 0x01:
            u ^= 0x0000014d >> 1
        p1 ^= ((u << 24) & 0xffffffff) | ((u << 8) & 0xffffffff)
    return p1

def set_key(pkey, in_key, key_len):
    pkey.qt_gen = 0
    if not pkey.qt_gen:
        gen_qtab(pkey)
        pkey.qt_gen = 1
    pkey.mt_gen = 0
    if not pkey.mt_gen:
        gen_mtab(pkey)
        pkey.mt_gen = 1
    pkey.k_len = (key_len * 8) // 64
    me_key = [0, 0, 0, 0]
    mo_key = [0, 0, 0, 0]
    for i in range(pkey.k_len):
        if WORD_BIGENDIAN:
            a = byteswap32(in_key[i + 1])
            me_key[i] = a
            b = byteswap32(in_key[i + i + 1])
        else:
            a = in_key[i + i]
            me_key[i] = a
            b = in_key[i + i + 1]
        mo_key[i] = b
        pkey.s_key[pkey.k_len - i - 1] = mds_rem(a, b)
    for i in range(0, 40, 2):
        a = (0x01010101 * i) % 0x100000000
        b = (a + 0x01010101) % 0x100000000
        a = h_fun(pkey, a, me_key)
        b = rotl32(h_fun(pkey, b, mo_key), 8)
        pkey.l_key[i] = (a + b) % 0x100000000
        pkey.l_key[i + 1] = rotl32((a + 2 * b) % 0x100000000, 9)
    gen_mk_tab(pkey, pkey.s_key)

def _decrypt_block(pkey, in_blk):
    blk = [0, 0, 0, 0]
    if WORD_BIGENDIAN:
        blk[0] = byteswap32(in_blk[0]) ^ pkey.l_key[4]
        blk[1] = byteswap32(in_blk[1]) ^ pkey.l_key[5]
        blk[2] = byteswap32(in_blk[2]) ^ pkey.l_key[6]
        blk[3] = byteswap32(in_blk[3]) ^ pkey.l_key[7]
    else:
        blk[0] = in_blk[0] ^ pkey.l_key[4]
        blk[1] = in_blk[1] ^ pkey.l_key[5]
        blk[2] = in_blk[2] ^ pkey.l_key[6]
        blk[3] = in_blk[3] ^ pkey.l_key[7]
    for i in range(7, -1, -1):
        t1 = (pkey.mk_tab[0][byte(blk[1],3)] ^ pkey.mk_tab[1][byte(blk[1],0)] ^ pkey.mk_tab[2][byte(blk[1],1)] ^ pkey.mk_tab[3][byte(blk[1],2)])
        t0 = (pkey.mk_tab[0][byte(blk[0],0)] ^ pkey.mk_tab[1][byte(blk[0],1)] ^ pkey.mk_tab[2][byte(blk[0],2)] ^ pkey.mk_tab[3][byte(blk[0],3)])
        blk[2] = rotl32(blk[2], 1) ^ ((t0 + t1 + pkey.l_key[4*i + 10]) % 0x100000000)
        blk[3] = rotr32(blk[3] ^ ((t0 + 2*t1 + pkey.l_key[4*i + 11]) % 0x100000000), 1)
        t1 = (pkey.mk_tab[0][byte(blk[3],3)] ^ pkey.mk_tab[1][byte(blk[3],0)] ^ pkey.mk_tab[2][byte(blk[3],1)] ^ pkey.mk_tab[3][byte(blk[3],2)])
        t0 = (pkey.mk_tab[0][byte(blk[2],0)] ^ pkey.mk_tab[1][byte(blk[2],1)] ^ pkey.mk_tab[2][byte(blk[2],2)] ^ pkey.mk_tab[3][byte(blk[2],3)])
        blk[0] = rotl32(blk[0], 1) ^ ((t0 + t1 + pkey.l_key[4*i + 8]) % 0x100000000)
        blk[1] = rotr32(blk[1] ^ ((t0 + 2*t1 + pkey.l_key[4*i + 9]) % 0x100000000), 1)
    if WORD_BIGENDIAN:
        in_blk[0] = byteswap32(blk[2] ^ pkey.l_key[0])
        in_blk[1] = byteswap32(blk[3] ^ pkey.l_key[1])
        in_blk[2] = byteswap32(blk[0] ^ pkey.l_key[2])
        in_blk[3] = byteswap32(blk[1] ^ pkey.l_key[3])
    else:
        in_blk[0] = blk[2] ^ pkey.l_key[0]
        in_blk[1] = blk[3] ^ pkey.l_key[1]
        in_blk[2] = blk[0] ^ pkey.l_key[2]
        in_blk[3] = blk[1] ^ pkey.l_key[3]

def _encrypt_block(pkey, in_blk):
    blk = [0, 0, 0, 0]
    if WORD_BIGENDIAN:
        blk[0] = byteswap32(in_blk[0]) ^ pkey.l_key[0]
        blk[1] = byteswap32(in_blk[1]) ^ pkey.l_key[1]
        blk[2] = byteswap32(in_blk[2]) ^ pkey.l_key[2]
        blk[3] = byteswap32(in_blk[3]) ^ pkey.l_key[3]
    else:
        blk[0] = in_blk[0] ^ pkey.l_key[0]
        blk[1] = in_blk[1] ^ pkey.l_key[1]
        blk[2] = in_blk[2] ^ pkey.l_key[2]
        blk[3] = in_blk[3] ^ pkey.l_key[3]
    for i in range(8):
        t1 = (pkey.mk_tab[0][byte(blk[1],3)] ^ pkey.mk_tab[1][byte(blk[1],0)] ^ pkey.mk_tab[2][byte(blk[1],1)] ^ pkey.mk_tab[3][byte(blk[1],2)])
        t0 = (pkey.mk_tab[0][byte(blk[0],0)] ^ pkey.mk_tab[1][byte(blk[0],1)] ^ pkey.mk_tab[2][byte(blk[0],2)] ^ pkey.mk_tab[3][byte(blk[0],3)])
        blk[2] = rotr32(blk[2] ^ ((t0 + t1 + pkey.l_key[4*i + 8]) % 0x100000000), 1)
        blk[3] = rotl32(blk[3], 1) ^ ((t0 + 2*t1 + pkey.l_key[4*i + 9]) % 0x100000000)
        t1 = (pkey.mk_tab[0][byte(blk[3],3)] ^ pkey.mk_tab[1][byte(blk[3],0)] ^ pkey.mk_tab[2][byte(blk[3],1)] ^ pkey.mk_tab[3][byte(blk[3],2)])
        t0 = (pkey.mk_tab[0][byte(blk[2],0)] ^ pkey.mk_tab[1][byte(blk[2],1)] ^ pkey.mk_tab[2][byte(blk[2],2)] ^ pkey.mk_tab[3][byte(blk[2],3)])
        blk[0] = rotr32(blk[0] ^ ((t0 + t1 + pkey.l_key[4*i + 10]) % 0x100000000), 1)
        blk[1] = rotl32(blk[1], 1) ^ ((t0 + 2*t1 + pkey.l_key[4*i + 11]) % 0x100000000)
    if WORD_BIGENDIAN:
        in_blk[0] = byteswap32(blk[2] ^ pkey.l_key[4])
        in_blk[1] = byteswap32(blk[3] ^ pkey.l_key[5])
        in_blk[2] = byteswap32(blk[0] ^ pkey.l_key[6])
        in_blk[3] = byteswap32(blk[1] ^ pkey.l_key[7])
    else:
        in_blk[0] = blk[2] ^ pkey.l_key[4]
        in_blk[1] = blk[3] ^ pkey.l_key[5]
        in_blk[2] = blk[0] ^ pkey.l_key[6]
        in_blk[3] = blk[1] ^ pkey.l_key[7]

class Twofish:
    def __init__(self, key=None):
        if key:
            self.set_key(key)

    def set_key(self, key):
        key_len = len(key)
        if key_len not in [16, 24, 32]:
            raise KeyError("key must be 16, 24 or 32 bytes")
        if key_len % 4:
            raise KeyError("key not a multiple of 4")
        if key_len > 32:
            raise KeyError("key_len > 32")
        self.context = TWI()
        key_word32 = [0] * 32
        i = 0
        while key:
            key_word32[i] = struct.unpack("<L", key[0:4])[0]
            key = key[4:]
            i += 1
        set_key(self.context, key_word32, key_len)

    def decrypt(self, block):
        if len(block) % 16:
            raise ValueError("block size must be a multiple of 16")
        plaintext = b''
        while block:
            a, b, c, d = struct.unpack("<4L", block[:16])
            temp = [a, b, c, d]
            _decrypt_block(self.context, temp)
            plaintext += struct.pack("<4L", *temp)
            block = block[16:]
        return plaintext

    def encrypt(self, block):
        if len(block) % 16:
            raise ValueError("block size must be a multiple of 16")
        ciphertext = b''
        while block:
            a, b, c, d = struct.unpack("<4L", block[0:16])
            temp = [a, b, c, d]
            _encrypt_block(self.context, temp)
            ciphertext += struct.pack("<4L", *temp)
            block = block[16:]
        return ciphertext

# ── CMAC ───────────────────────────────────────────────────────────────────────

BLOCK_SIZE = 16

def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def left_shift_one(bitstring):
    out = bytearray(len(bitstring))
    carry = 0
    for i in reversed(range(len(bitstring))):
        new = (bitstring[i] << 1) & 0xFF
        out[i] = new | carry
        carry = (bitstring[i] & 0x80) >> 7
    return bytes(out)

def generate_subkeys(encrypt_block):
    const_rb = 0x87
    zero = bytes(BLOCK_SIZE)
    L = encrypt_block(zero)
    K1 = left_shift_one(L)
    if L[0] & 0x80:
        K1 = xor_bytes(K1, b'\x00' * 15 + bytes([const_rb]))
    K2 = left_shift_one(K1)
    if K1[0] & 0x80:
        K2 = xor_bytes(K2, b'\x00' * 15 + bytes([const_rb]))
    return K1, K2

def pad_block(block):
    padded = block + b'\x80'
    return padded + b'\x00' * (BLOCK_SIZE - len(padded))

class CMAC:
    def __init__(self, encrypt_block):
        self.encrypt_block = encrypt_block
        self.K1, self.K2 = generate_subkeys(encrypt_block)

    def digest(self, data):
        if len(data) == 0:
            last = xor_bytes(pad_block(b''), self.K2)
            blocks = []
        else:
            blocks = [data[i:i+BLOCK_SIZE] for i in range(0, len(data), BLOCK_SIZE)]
            if len(blocks[-1]) == BLOCK_SIZE:
                last = xor_bytes(blocks[-1], self.K1)
                blocks = blocks[:-1]
            else:
                last = xor_bytes(pad_block(blocks[-1]), self.K2)
                blocks = blocks[:-1]
        X = bytes(BLOCK_SIZE)
        for block in blocks:
            X = self.encrypt_block(xor_bytes(X, block))
        return self.encrypt_block(xor_bytes(X, last))

# ── CTR ────────────────────────────────────────────────────────────────────────

def inc_counter_be(counter):
    for i in range(BLOCK_SIZE - 1, -1, -1):
        counter[i] = (counter[i] + 1) & 0xFF
        if counter[i] != 0:
            break

class CTR:
    def __init__(self, encrypt_block, initial_counter):
        assert len(initial_counter) == BLOCK_SIZE
        self.encrypt_block = encrypt_block
        self.counter = bytearray(initial_counter)

    def process(self, data):
        out = bytearray()
        offset = 0
        while offset < len(data):
            keystream = self.encrypt_block(bytes(self.counter))
            inc_counter_be(self.counter)
            block = data[offset:offset + BLOCK_SIZE]
            ks = keystream[:len(block)]
            out.extend(b ^ k for b, k in zip(block, ks))
            offset += BLOCK_SIZE
        return bytes(out)

# ── EAX ────────────────────────────────────────────────────────────────────────

def _omac_with_prefix(cmac, prefix, data):
    P = b'\x00' * (BLOCK_SIZE - 1) + bytes([prefix])
    return cmac.digest(P + data)

class EAX:
    def __init__(self, encrypt_block):
        self.encrypt_block = encrypt_block
        self.cmac = CMAC(encrypt_block)

    def decrypt(self, nonce, ciphertext, tag, aad=b''):
        n_tag = _omac_with_prefix(self.cmac, 0x00, nonce)
        ctr = CTR(self.encrypt_block, n_tag)
        plaintext = ctr.process(ciphertext)
        h_tag = _omac_with_prefix(self.cmac, 0x01, aad)
        c_tag = _omac_with_prefix(self.cmac, 0x02, ciphertext)
        expected_tag = xor_bytes(xor_bytes(n_tag, h_tag), c_tag)
        if expected_tag != tag:
            raise ValueError("EAX authentication failed")
        return plaintext

# ── Pipeline PKT ───────────────────────────────────────────────────────────────

PKT_KEY   = bytes([0x89]) * 16
PKT_NONCE = bytes([0x10]) * 16

def deobf_stage1(data):
    L = len(data)
    return bytes(data[L - 1 - i] ^ ((L - i * L) & 0xFF) for i in range(L))

def deobf_stage2(data):
    L = len(data)
    return bytes(b ^ ((L - i) & 0xFF) for i, b in enumerate(data))

def uncompress_qt(blob):
    size = struct.unpack(">I", blob[:4])[0]
    return zlib.decompress(blob[4:])[:size]

def decrypt_pkt(pkt: bytes) -> bytes:
    stage1 = deobf_stage1(pkt)
    eax = EAX(Twofish(PKT_KEY).encrypt)
    plain = eax.decrypt(nonce=PKT_NONCE, ciphertext=stage1[:-16], tag=stage1[-16:])
    return uncompress_qt(deobf_stage2(plain))

# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} <arquivo.pkt>", file=sys.stderr)
        sys.exit(1)

    pkt_path = Path(sys.argv[1])

    if not pkt_path.exists():
        print(f"Erro: arquivo não encontrado: {pkt_path}", file=sys.stderr)
        sys.exit(1)

    if pkt_path.suffix.lower() != ".pkt":
        print(f"Aviso: extensão inesperada '{pkt_path.suffix}', esperado '.pkt'")

    print(f"Decifrando: {pkt_path} ({pkt_path.stat().st_size:,} bytes)...")

    try:
        xml_bytes = decrypt_pkt(pkt_path.read_bytes())
    except ValueError as e:
        print(f"Erro na decifragem: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = pkt_path.with_suffix(".xml")
    tree = ET.ElementTree(ET.fromstring(xml_bytes))
    ET.indent(tree, space="  ")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

    print(f"{len(xml_bytes):,} bytes de XML -> {out_path}")
    print("Versão do Packet Tracer:", tree.getroot().findtext("VERSION"))

if __name__ == "__main__":
    main()
