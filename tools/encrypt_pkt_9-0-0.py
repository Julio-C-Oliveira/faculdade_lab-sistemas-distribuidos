#!/usr/bin/env python3
"""
encrypt_pkt_9-0-0.py — Compila/Criptografa arquivos XML para .pkt do Cisco Packet Tracer 9.x.

Uso:
    python3 tools/encrypt_pkt_9-0-0.py <arquivo.xml> [saida.pkt]

O arquivo compilado (.pkt) é compatível nativamente com o Cisco Packet Tracer 9.x.
"""

import argparse
import importlib.util
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

# Importar o motor criptográfico de decrypt_pkt_9-0-0.py no mesmo diretório
_decrypt_script = Path(__file__).resolve().parent / "decrypt_pkt_9-0-0.py"
if not _decrypt_script.exists():
    raise FileNotFoundError(f"Não foi possível localizar {_decrypt_script}")

_spec = importlib.util.spec_from_file_location("decrypt_pkt_module", _decrypt_script)
_dp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dp)


def eax_encrypt(eax_obj, nonce: bytes, plaintext: bytes, aad: bytes = b""):
    """Executa a cifragem autenticada EAX em modo CTR + tag CMAC."""
    n_tag = _dp._omac_with_prefix(eax_obj.cmac, 0x00, nonce)
    ctr = _dp.CTR(eax_obj.encrypt_block, n_tag)
    ciphertext = ctr.process(plaintext)
    h_tag = _dp._omac_with_prefix(eax_obj.cmac, 0x01, aad)
    c_tag = _dp._omac_with_prefix(eax_obj.cmac, 0x02, ciphertext)
    tag = _dp.xor_bytes(_dp.xor_bytes(n_tag, h_tag), c_tag)
    return ciphertext, tag


def obf_stage1_invert(stage1: bytes) -> bytes:
    """Inverte a ordem dos bytes e restaura a máscara XOR do primeiro estágio."""
    L = len(stage1)
    res = bytearray(L)
    for i in range(L):
        res[L - 1 - i] = stage1[i] ^ ((L - i * L) & 0xFF)
    return bytes(res)


def compress_qt(xml_bytes: bytes) -> bytes:
    """Compacta com zlib e adiciona prefixo big-endian de 32 bits com o tamanho descompactado."""
    return struct.pack(">I", len(xml_bytes)) + zlib.compress(xml_bytes)


def encrypt_pkt(xml_bytes: bytes) -> bytes:
    """Transforma XML em bytes binários de um arquivo .pkt compatível com o Cisco Packet Tracer 9.x."""
    blob = compress_qt(xml_bytes)
    plain = _dp.deobf_stage2(blob)
    eax = _dp.EAX(_dp.Twofish(_dp.PKT_KEY).encrypt)
    ciphertext, tag = eax_encrypt(eax, nonce=_dp.PKT_NONCE, plaintext=plain)
    stage1 = ciphertext + tag
    return obf_stage1_invert(stage1)


def main():
    parser = argparse.ArgumentParser(
        description="Compila/criptografa arquivos XML para o formato .pkt do Cisco Packet Tracer 9.x."
    )
    parser.add_argument("xml_file", help="Caminho do arquivo .xml a ser compilado")
    parser.add_argument(
        "pkt_file",
        nargs="?",
        help="Caminho opcional do arquivo de saída .pkt (padrão: mesmo nome com .pkt)",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    if not xml_path.exists():
        print(f"Erro: arquivo XML não encontrado: {xml_path}", file=sys.stderr)
        sys.exit(1)

    if xml_path.suffix.lower() != ".xml":
        print(
            f"Aviso: extensão inesperada '{xml_path.suffix}', esperado '.xml'"
        )

    out_path = Path(args.pkt_file) if args.pkt_file else xml_path.with_suffix(".pkt")

    print(f"Lendo XML: {xml_path} ({xml_path.stat().st_size:,} bytes)...")
    xml_bytes = xml_path.read_bytes()

    try:
        root = ET.fromstring(xml_bytes)
        pt_version = root.findtext("VERSION") or "Desconhecida"
        print(f"Versão detectada do Packet Tracer: {pt_version}")
    except Exception as e:
        print(f"Aviso: Não foi possível validar sintaxe XML ({e}), prosseguindo.")

    print("Criptografando com Twofish-EAX + zlib...")
    try:
        pkt_bytes = encrypt_pkt(xml_bytes)
    except Exception as e:
        print(f"Erro ao criptografar: {e}", file=sys.stderr)
        sys.exit(1)

    out_path.write_bytes(pkt_bytes)
    ratio = (len(pkt_bytes) / len(xml_bytes)) * 100
    print(
        f"[+] Sucesso: {len(pkt_bytes):,} bytes gravados em -> {out_path} ({ratio:.1f}% do tamanho XML)"
    )


if __name__ == "__main__":
    main()
