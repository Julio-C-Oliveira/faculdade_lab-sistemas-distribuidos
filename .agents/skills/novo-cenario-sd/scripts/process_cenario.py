#!/usr/bin/env python3
"""
process_cenario.py — Motor de automação da skill 'novo-cenario-sd'.

Responsável por:
1. Criar a estrutura simétrica de diretórios do cenário (cenario_XX/).
2. Extrair pacotes de archives/ (.tar.xz, .zip, .tar.gz) ou copiar .pkt direto (modo híbrido:
   funciona tanto apenas com pacote pré-gerado quanto com .pkt/.xml como fonte da verdade absoluta).
3. Padronizar cenario_XX_equipe_08_Lab_SD.pkt e decodificar para .xml.
4. Extrair 100% dos dispositivos (incluindo modelo real via CUSTOM_VARS e nº de série),
   enlaces, portas físicas (mapeamento 1-para-1 entre RUNNINGCONFIG e <PORT>), IPs, VLANs, DHCP e protocolos.
5. Calcular a RIB esperada por menor caminho (Dijkstra com suporte a ECMP preservando a ordem das interfaces).
6. Gerar tabelas LaTeX encapsuladas (ifaces.tex, switchports.tex, pcs.tex, rib.tex, configs.tex, tabelas_geradas.tex).
7. Gerar relatórios analíticos completos de 9 seções (.md e .html estilizado com CSS).
8. Renderizar diagrama visual da topologia (cenario_real.png) via PIL caso não haja imagens no pacote.
9. Gerar main.tex, introduction.tex, body.tex (com detecção automática de Núcleo WAN vs Borda, OSPF, DHCP, VLANs) e README.md.
10. Compilar PDF via pdflatex (2 passadas) e fechar pacote cenario_XX_equipe_08_Lab_SD.zip (--package).
"""

import argparse
import base64
import heapq
import html
import ipaddress
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

ORDINAIS = {
    1: ("1º", "primeira", "primeiro"),
    2: ("2º", "segunda", "segundo"),
    3: ("3º", "terceira", "terceiro"),
    4: ("4º", "quarta", "quarto"),
    5: ("5º", "quinta", "quinto"),
    6: ("6º", "sexta", "sexto"),
    7: ("7º", "sétima", "sétimo"),
    8: ("8º", "oitava", "oitavo"),
    9: ("9º", "nona", "nono"),
    10: ("10º", "décima", "décimo"),
}


def natural_key(text: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text or "")]


def short_ifname(name: str) -> str:
    if not name:
        return "—"
    return (
        name.replace("GigabitEthernet", "Gi")
        .replace("FastEthernet", "Fa")
        .replace("Serial", "Se")
    )


def mask_to_prefix(mask: str) -> str:
    if not mask or mask == "—":
        return "—"
    try:
        net = ipaddress.IPv4Network(f"0.0.0.0/{mask}", strict=False)
        return f"/{net.prefixlen}"
    except Exception:
        return mask


def wildcard_to_prefix(ip: str, wildcard: str) -> str:
    try:
        w_int = int(ipaddress.IPv4Address(wildcard))
        m_int = 0xFFFFFFFF ^ w_int
        mask_str = str(ipaddress.IPv4Address(m_int))
        net = ipaddress.IPv4Network(f"{ip}/{mask_str}", strict=False)
        return f"{net.network_address}/{net.prefixlen}"
    except Exception:
        return f"{ip} {wildcard}"


def ip_to_subnet(ip: str, mask: str) -> str:
    try:
        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
        return str(net)
    except Exception:
        return f"{ip}/{mask}"


def format_bw(bw_kbps_str: str, iface_name: str = "") -> str:
    try:
        val = int(bw_kbps_str)
        if val >= 1000000:
            return f"{val // 1000000} Gb/s"
        if val >= 10000 and val % 1000 == 0:
            return f"{val // 1000} Mb/s"
        return f"{val} kb/s"
    except Exception:
        if iface_name.startswith("Serial"):
            return "1544 kb/s"
        if "Gigabit" in iface_name:
            return "1 Gb/s"
        return "100 Mb/s"


def decode_pt_model(custom_vars_b64: str, fallback_type: str) -> str:
    if custom_vars_b64:
        try:
            raw = base64.b64decode(custom_vars_b64)
            clean_ascii = raw.replace(b"\x00", b"").decode("latin1", errors="ignore")
            m = re.search(r"PT_MODEL[^A-Za-z0-9]+([A-Za-z0-9_\-\.]+?)(?:PT_VERSION|$|[^A-Za-z0-9_\-\.])", clean_ascii)
            if m:
                return m.group(1)
        except Exception:
            pass
    if fallback_type == "Router":
        return "Router-PT"
    if "Switch" in fallback_type:
        return "Switch-PT"
    if fallback_type == "Pc":
        return "PC-PT"
    return fallback_type


def latex_escape(text: str) -> str:
    if text is None or text == "":
        return "--"
    s = str(text)
    if s == "—":
        return "--"
    return (
        s.replace("_", r"\_")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
    )


END_HOST_TYPES = (
    "Pc",
    "Laptop",
    "Server",
    "Printer",
    "IpPhone",
    "WirelessEndDevice",
    "Tv",
    "Tablet",
    "SmartPhone",
    "GenericEndDevice",
    "Voip",
)

IGNORED_DEVICE_TYPES = ("Power Distribution Device",)


def parse_running_config(cfg_text: str) -> dict:
    info = {
        "hostname": None,
        "interfaces": {},
        "interface_order": [],
        "ospf": [],
        "rip": [],
        "eigrp": [],
        "static_routes": [],
        "dhcp_pools": [],
        "dhcp_excluded": [],
        "vlans": {},
        "acls": [],
        "nat": [],
        "spanning_tree": None,
        "essential_lines": [],
    }
    if not cfg_text:
        return info

    lines = cfg_text.splitlines()
    current_iface = None
    current_router = None
    current_dhcp = None
    current_vlan = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped == "!":
            current_iface = None
            current_vlan = None
            continue

        m = re.match(r"^hostname\s+(\S+)", stripped)
        if m:
            info["hostname"] = m.group(1)
            continue

        m = re.match(r"^spanning-tree mode\s+(\S+)", stripped)
        if m:
            info["spanning_tree"] = m.group(1)
            continue

        m_gw_sw = re.match(r"^ip default-gateway\s+([\d\.]+)", stripped)
        if m_gw_sw:
            info["default_gateway"] = m_gw_sw.group(1)
            continue

        if stripped.startswith("ip dhcp excluded-address"):
            info["dhcp_excluded"].append(stripped)
            continue

        m = re.match(r"^ip dhcp pool\s+(\S+)", stripped)
        if m:
            current_dhcp = {"name": m.group(1), "network": None, "default_router": None, "dns": None}
            info["dhcp_pools"].append(current_dhcp)
            current_iface = None
            current_router = None
            continue

        if current_dhcp is not None and raw_line.startswith(" "):
            m_net = re.match(r"^network\s+([\d\.]+)\s+([\d\.]+)", stripped)
            if m_net:
                current_dhcp["network"] = f"{m_net.group(1)} {m_net.group(2)}"
            m_gw = re.match(r"^default-router\s+([\d\.]+)", stripped)
            if m_gw:
                current_dhcp["default_router"] = m_gw.group(1)
            m_dns = re.match(r"^dns-server\s+([\d\.]+)", stripped)
            if m_dns:
                current_dhcp["dns"] = m_dns.group(1)
            continue
        else:
            current_dhcp = None

        m = re.match(r"^vlan\s+(\d+)", stripped)
        if m:
            current_vlan = m.group(1)
            info["vlans"][current_vlan] = f"VLAN{current_vlan}"
            continue
        if current_vlan is not None and raw_line.startswith(" "):
            m_vn = re.match(r"^name\s+(.+)", stripped)
            if m_vn:
                info["vlans"][current_vlan] = m_vn.group(1).strip()
            continue

        m = re.match(r"^interface\s+(\S+)", stripped)
        if m:
            current_iface = m.group(1)
            current_router = None
            if current_iface not in info["interfaces"]:
                info["interface_order"].append(current_iface)
                info["interfaces"][current_iface] = {
                    "ip": None,
                    "mask": None,
                    "clock_rate": None,
                    "description": None,
                    "shutdown": False,
                    "encapsulation": None,
                    "switchport_mode": None,
                    "access_vlan": None,
                    "trunk_native_vlan": None,
                    "trunk_allowed_vlan": None,
                }
            continue

        if current_iface is not None and raw_line.startswith(" "):
            ifobj = info["interfaces"][current_iface]
            m_ip = re.match(r"^ip address\s+([\d\.]+)\s+([\d\.]+)", stripped)
            if m_ip:
                ifobj["ip"] = m_ip.group(1)
                ifobj["mask"] = m_ip.group(2)
            m_clk = re.match(r"^clock rate\s+(\d+)", stripped)
            if m_clk:
                ifobj["clock_rate"] = m_clk.group(1)
            m_desc = re.match(r"^description\s+(.+)", stripped)
            if m_desc:
                ifobj["description"] = m_desc.group(1).strip()
            if stripped == "shutdown":
                ifobj["shutdown"] = True
            m_enc = re.match(r"^encapsulation dot1Q\s+(\d+)(?:\s+native)?", stripped, re.I)
            if m_enc:
                is_nat = "native" in stripped.lower()
                ifobj["encapsulation"] = f"dot1Q {m_enc.group(1)}" + (" native" if is_nat else "")
            m_swm = re.match(r"^switchport mode\s+(\S+)", stripped)
            if m_swm:
                ifobj["switchport_mode"] = m_swm.group(1)
            m_swa = re.match(r"^switchport access vlan\s+(\d+)", stripped)
            if m_swa:
                ifobj["access_vlan"] = m_swa.group(1)
            m_swn = re.match(r"^switchport trunk native vlan\s+(\d+)", stripped)
            if m_swn:
                ifobj["trunk_native_vlan"] = m_swn.group(1)
            m_swt = re.match(r"^switchport trunk allowed vlan\s+(\S+)", stripped)
            if m_swt:
                ifobj["trunk_allowed_vlan"] = m_swt.group(1)
            if stripped.startswith("ip nat"):
                info["nat"].append(f"{current_iface}: {stripped}")
            continue

        m_ospf = re.match(r"^router ospf\s+(\d+)", stripped)
        if m_ospf:
            current_router = ("ospf", {"process": m_ospf.group(1), "router_id": None, "networks": [], "passives": []})
            info["ospf"].append(current_router[1])
            continue

        if re.match(r"^router rip", stripped):
            current_router = ("rip", {"version": 1, "networks": [], "passives": []})
            info["rip"].append(current_router[1])
            continue

        m_eigrp = re.match(r"^router eigrp\s+(\d+)", stripped)
        if m_eigrp:
            current_router = ("eigrp", {"as": m_eigrp.group(1), "networks": [], "passives": []})
            info["eigrp"].append(current_router[1])
            continue

        if current_router is not None and raw_line.startswith(" "):
            rtype, robj = current_router
            m_rid = re.match(r"^router-id\s+([\d\.]+)", stripped)
            if m_rid:
                robj["router_id"] = m_rid.group(1)
            m_pas = re.match(r"^passive-interface\s+(\S+)", stripped)
            if m_pas:
                robj["passives"].append(m_pas.group(1))
            m_net_ospf = re.match(r"^network\s+([\d\.]+)\s+([\d\.]+)\s+area\s+(\S+)", stripped)
            if m_net_ospf:
                robj["networks"].append((m_net_ospf.group(1), m_net_ospf.group(2), m_net_ospf.group(3)))
            else:
                m_net_gen = re.match(r"^network\s+([\d\.]+)(?:\s+([\d\.]+))?", stripped)
                if m_net_gen:
                    robj["networks"].append((m_net_gen.group(1), m_net_gen.group(2) or "", ""))
            m_ver = re.match(r"^version\s+(\d+)", stripped)
            if m_ver and rtype == "rip":
                robj["version"] = int(m_ver.group(1))
            continue
        else:
            current_router = None

        m_sr = re.match(r"^ip route\s+([\d\.]+)\s+([\d\.]+)\s+(\S+)", stripped)
        if m_sr:
            info["static_routes"].append((m_sr.group(1), m_sr.group(2), m_sr.group(3)))
            continue

        if stripped.startswith("access-list") or stripped.startswith("ip access-list"):
            info["acls"].append(stripped)
        elif stripped.startswith("ip nat"):
            info["nat"].append(stripped)

    # Reconstruir essential_lines (sem description cosmética nas interfaces para igualar configs.tex)
    clean_essential = []
    if info["hostname"]:
        clean_essential.append(f"hostname {info['hostname']}")
    for ex in info["dhcp_excluded"]:
        clean_essential.append(ex)
    for pool in info["dhcp_pools"]:
        clean_essential.append(f"ip dhcp pool {pool['name']}")
        if pool["network"]:
            clean_essential.append(f" network {pool['network']}")
        if pool["default_router"]:
            clean_essential.append(f" default-router {pool['default_router']}")
        if pool["dns"]:
            clean_essential.append(f" dns-server {pool['dns']}")
    for vid, vname in sorted(info["vlans"].items(), key=lambda x: int(x[0])):
        if vid == "1":
            continue
        clean_essential.append(f"vlan {vid}")
        clean_essential.append(f" name {vname}")
    for ifname in info["interface_order"]:
        ifdata = info["interfaces"][ifname]
        has_cfg = any(
            ifdata.get(k)
            for k in (
                "ip",
                "clock_rate",
                "encapsulation",
                "switchport_mode",
                "access_vlan",
                "trunk_native_vlan",
                "trunk_allowed_vlan",
            )
        )
        if has_cfg:
            clean_essential.append(f"interface {ifname}")
            if ifdata["encapsulation"]:
                clean_essential.append(f" encapsulation {ifdata['encapsulation']}")
            if ifdata["ip"]:
                clean_essential.append(f" ip address {ifdata['ip']} {ifdata['mask']}")
            if ifdata["clock_rate"]:
                clean_essential.append(f" clock rate {ifdata['clock_rate']}")
            if ifdata["switchport_mode"]:
                clean_essential.append(f" switchport mode {ifdata['switchport_mode']}")
            if ifdata["access_vlan"]:
                clean_essential.append(f" switchport access vlan {ifdata['access_vlan']}")
            if ifdata["trunk_native_vlan"]:
                clean_essential.append(f" switchport trunk native vlan {ifdata['trunk_native_vlan']}")
            if ifdata["trunk_allowed_vlan"]:
                clean_essential.append(f" switchport trunk allowed vlan {ifdata['trunk_allowed_vlan']}")
    for ospf in info["ospf"]:
        clean_essential.append(f"router ospf {ospf['process']}")
        if ospf["router_id"]:
            clean_essential.append(f" router-id {ospf['router_id']}")
        for pas in ospf["passives"]:
            clean_essential.append(f" passive-interface {pas}")
        for net, wc, area in ospf["networks"]:
            clean_essential.append(f" network {net} {wc} area {area}")
    for rip in info["rip"]:
        clean_essential.append("router rip")
        if rip["version"] != 1:
            clean_essential.append(f" version {rip['version']}")
        for pas in rip["passives"]:
            clean_essential.append(f" passive-interface {pas}")
        for net, _, _ in rip["networks"]:
            clean_essential.append(f" network {net}")
    for eigrp in info["eigrp"]:
        clean_essential.append(f"router eigrp {eigrp['as']}")
        for pas in eigrp["passives"]:
            clean_essential.append(f" passive-interface {pas}")
        for net, wc, _ in eigrp["networks"]:
            clean_essential.append(f" network {net} {wc}".rstrip())
    for dst, msk, nh in info["static_routes"]:
        clean_essential.append(f"ip route {dst} {msk} {nh}")
    for acl in info["acls"]:
        clean_essential.append(acl)
    for nat_rule in info["nat"]:
        if not nat_rule.startswith("interface "):
            clean_essential.append(nat_rule)
    info["essential_lines"] = clean_essential
    return info


def parse_packet_tracer_xml(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    version = root.findtext("VERSION") or "9.0.1"

    devices = []
    id_to_dev = {}
    name_to_dev = {}

    for d in root.findall(".//NETWORK/DEVICES/DEVICE"):
        eng = d.find("ENGINE")
        if eng is None:
            continue
        name = eng.findtext("NAME") or "Unknown"
        dtype = eng.findtext("TYPE") or "Unknown"
        ref_id = eng.findtext("SAVE_REF_ID") or ""
        sys_name = eng.findtext("SYS_NAME") or ""
        serial = eng.findtext("SERIALNUMBER") or "—"
        custom_vars = eng.findtext("CUSTOM_VARS") or ""
        model = decode_pt_model(custom_vars, dtype)

        ws_log = d.find("WORKSPACE/LOGICAL")
        x = float(ws_log.findtext("X") or 0.0) if ws_log is not None else 0.0
        y = float(ws_log.findtext("Y") or 0.0) if ws_log is not None else 0.0

        rc_node = eng.find("RUNNINGCONFIG")
        rc_text = ""
        if rc_node is not None:
            rc_lines = [l.text for l in rc_node.findall("LINE") if l.text is not None]
            rc_text = "\n".join(rc_lines)

        parsed_cfg = parse_running_config(rc_text)

        # Extrair VLANs do banco vlan.dat (<VLAN number="..." name="..."/> no XML de Switches)
        for vnode in eng.findall(".//VLAN"):
            vnum = vnode.attrib.get("number") or vnode.findtext("NUMBER") or ""
            vname = vnode.attrib.get("name") or vnode.findtext("NAME") or ""
            if vnum and vnum not in ("1", "1002", "1003", "1004", "1005"):
                parsed_cfg["vlans"].setdefault(vnum, vname or f"VLAN{vnum}")

        hostname = parsed_cfg["hostname"] or (sys_name if sys_name else "—")

        gw_dev = eng.findtext("GATEWAY") or eng.findtext("DEFAULT_GATEWAY") or "—"
        dns_dev = eng.findtext("DNS_SERVER_IP") or "—"

        # Extrair lista ordenada de <PORT> físicos reais (excluindo Console/Aux/Bluetooth/vazio)
        xml_hw_ports = []
        for p in eng.findall(".//PORT"):
            ptype = p.findtext("TYPE") or ""
            if not ptype or ptype in ("eConsole", "eAux", "eBluetooth", "eUsb"):
                continue
            pip = p.findtext("IP") or p.findtext("IP_ADDRESS") or ""
            pmask = p.findtext("SUBNET") or p.findtext("SUBNET_MASK") or ""
            pbw = p.findtext("BANDWIDTH") or ""
            pfull = p.findtext("FULLDUPLEX")
            pclock = p.findtext("CLOCKRATE") or p.findtext("CLOCK_RATE") or ""
            pgw = p.findtext("GATEWAY") or ""
            pdns = p.findtext("PORT_DNS") or p.findtext("DNS_SERVER") or ""
            pdhcp = p.findtext("PORT_DHCP_ENABLE")
            if pgw and pgw != "0.0.0.0" and gw_dev == "—":
                gw_dev = pgw
            if pdns and pdns != "0.0.0.0" and dns_dev == "—":
                dns_dev = pdns
            xml_hw_ports.append(
                {
                    "type": ptype,
                    "ip": pip if pip != "0.0.0.0" else "",
                    "mask": pmask if pmask != "0.0.0.0" else "",
                    "bandwidth": pbw,
                    "duplex": "full" if pfull == "true" else ("half" if pfull == "false" else "—"),
                    "clock_rate": pclock,
                    "dhcp": pdhcp == "true",
                }
            )

        # Associar nomes de interfaces físicas do RUNNINGCONFIG aos <PORT> do XML (1-para-1 em ordem)
        phys_ifnames = [
            ifn
            for ifn in parsed_cfg["interface_order"]
            if not ifn.startswith(("Vlan", "Loopback", "Port-channel", "Tunnel")) and "." not in ifn
        ]
        ports_by_name = {}
        if dtype in END_HOST_TYPES:
            p0 = xml_hw_ports[0] if xml_hw_ports else {"bandwidth": "100000", "duplex": "full", "ip": "", "mask": "", "dhcp": True, "type": "eCopperFastEthernet"}
            default_ifname = "GigabitEthernet0" if "Gigabit" in p0.get("type", "") else ("Wireless0" if "Wireless" in p0.get("type", "") else "FastEthernet0")
            ports_by_name[default_ifname] = {
                "name": default_ifname,
                "ip": p0.get("ip", ""),
                "mask": p0.get("mask", ""),
                "bandwidth": p0.get("bandwidth", "100000"),
                "duplex": p0.get("duplex", "full"),
                "dhcp": p0.get("dhcp", True) or not p0.get("ip"),
            }
        else:
            for idx, ifn in enumerate(phys_ifnames):
                hw = xml_hw_ports[idx] if idx < len(xml_hw_ports) else {}
                ports_by_name[ifn] = {
                    "name": ifn,
                    "ip": hw.get("ip", ""),
                    "mask": hw.get("mask", ""),
                    "bandwidth": hw.get("bandwidth", ""),
                    "duplex": hw.get("duplex", "full"),
                    "clock_rate": hw.get("clock_rate", ""),
                }

        dev_info = {
            "name": name,
            "type": dtype,
            "model": model,
            "hostname": hostname,
            "serial": serial,
            "ref_id": ref_id,
            "x": x,
            "y": y,
            "gw": gw_dev if gw_dev != "0.0.0.0" else "—",
            "dns": dns_dev if dns_dev != "0.0.0.0" else "—",
            "phys_ifaces_count": len(ports_by_name),
            "ports": ports_by_name,
            "config": parsed_cfg,
        }
        devices.append(dev_info)
        if ref_id:
            id_to_dev[ref_id] = dev_info
        name_to_dev[name] = dev_info

    # Links
    links = []
    port_peer = {}
    host_link_port = {}  # dev_name -> port_name usada no link
    for l in root.findall(".//NETWORK/LINKS/LINK"):
        cable = l.find("CABLE")
        if cable is None:
            continue
        from_ref = cable.findtext("FROM") or ""
        to_ref = cable.findtext("TO") or ""
        d1 = id_to_dev.get(from_ref, {}).get("name", from_ref)
        d2 = id_to_dev.get(to_ref, {}).get("name", to_ref)
        if d1 not in name_to_dev or d2 not in name_to_dev:
            continue
        p_nodes = cable.findall("PORT")
        p1 = p_nodes[0].text if len(p_nodes) > 0 else "?"
        p2 = p_nodes[1].text if len(p_nodes) > 1 else "?"
        ctype_raw = cable.findtext("TYPE") or "Unknown"
        ctype_map = {
            "eStraightThrough": "Direto",
            "eCrossOver": "Cruzado",
            "eSerial": "Serial",
            "eSmartSerial": "Serial",
            "eFiber": "Fibra",
            "eConsole": "Console",
        }
        if "Serial" in p1 or "Serial" in p2:
            ctype = "Serial"
        else:
            ctype = ctype_map.get(ctype_raw, ctype_raw)
        func = cable.findtext("FUNCTIONAL") == "true"
        links.append(
            {
                "from_dev": d1,
                "from_port": p1,
                "to_dev": d2,
                "to_port": p2,
                "cable_type": ctype,
                "functional": func,
            }
        )
        port_peer[(d1, p1)] = (d2, p2, ctype)
        port_peer[(d2, p2)] = (d1, p1, ctype)
        host_link_port[d1] = p1
        host_link_port[d2] = p2

    # Consolidar interfaces com IP nos roteadores/switches
    router_ifaces = []
    subnets_set = set()
    vlan_to_subnet = {}
    for d in sorted(devices, key=lambda x: natural_key(x["name"])):
        if d["type"] not in ("Router", "Switch", "Multilayer Switch"):
            continue
        cfg_ifaces = d["config"]["interfaces"]
        for order_idx, ifname in enumerate(d["config"]["interface_order"]):
            ifdata = cfg_ifaces[ifname]
            ip = ifdata["ip"]
            mask = ifdata["mask"]
            if not ip:
                continue
            subnet = ip_to_subnet(ip, mask)
            subnets_set.add(subnet)
            if ifdata["encapsulation"]:
                m_v = re.search(r"dot1Q\s+(\d+)", ifdata["encapsulation"], re.I)
                if m_v:
                    vlan_to_subnet[m_v.group(1)] = subnet
            elif ifname.lower().startswith("vlan"):
                v_id = re.sub(r"\D", "", ifname)
                if v_id:
                    vlan_to_subnet[v_id] = subnet

            peer_info = port_peer.get((d["name"], ifname))
            if not peer_info and "." in ifname:
                parent_port = ifname.split(".")[0]
                peer_info = port_peer.get((d["name"], parent_port))
            peer_str = f"{peer_info[0]} {peer_info[1]}" if peer_info else "—"
            peer_short_str = f"{peer_info[0]} {short_ifname(peer_info[1])}" if peer_info else "—"

            hw_port = d["ports"].get(ifname.split(".")[0], {})
            bw_str = format_bw(hw_port.get("bandwidth", ""), ifname)
            try:
                bw_kbps = int(hw_port.get("bandwidth") or (1544 if ifname.startswith("Serial") else 1000000))
            except Exception:
                bw_kbps = 1544 if ifname.startswith("Serial") else 1000000
            cost_ospf = max(1, 100000 // bw_kbps)

            clk_type = "--"
            if ifname.startswith("Serial"):
                clk_type = "DCE" if ifdata["clock_rate"] else "DTE"
            elif ifdata["encapsulation"]:
                clk_type = ifdata["encapsulation"]

            router_ifaces.append(
                {
                    "dev_name": d["name"],
                    "hostname": d["hostname"],
                    "iface": ifname,
                    "short_iface": short_ifname(ifname),
                    "order_idx": order_idx,
                    "ip": ip,
                    "mask": mask,
                    "prefix": mask_to_prefix(mask),
                    "subnet": subnet,
                    "bw": bw_str,
                    "bw_kbps": bw_kbps,
                    "description": ifdata["description"] or "—",
                    "status": "shutdown" if ifdata["shutdown"] else ("conectada" if peer_info else "sem cabo"),
                    "clock_type": clk_type,
                    "peer": peer_str,
                    "peer_short": peer_short_str,
                    "cost_ospf": cost_ospf,
                }
            )

    # Consolidar portas de Switch (usando ports_by_name extraídos de RUNNINGCONFIG + <PORT>)
    switch_ports_table = []
    sw_port_vlan_map = {}
    for d in sorted(devices, key=lambda x: natural_key(x["name"])):
        if "Switch" not in d["type"]:
            continue
        all_pnames = sorted(d["ports"].keys(), key=natural_key)
        for pname in all_pnames:
            pinfo = d["ports"][pname]
            short_p = short_ifname(pname)
            peer = port_peer.get((d["name"], pname))
            bw_str = format_bw(pinfo.get("bandwidth", ""), pname)
            duplex_str = pinfo.get("duplex", "full")
            if peer:
                peer_dev_obj = name_to_dev.get(peer[0], {})
                peer_label = peer_dev_obj.get("hostname") if peer_dev_obj.get("type") == "Router" else peer[0]
                conn_str = f"{peer_label} {peer[1]}"
                conn_dev_full = f"{peer[0]} {peer[1]}"
                conn_dev_short = f"{peer[0]} {short_ifname(peer[1])}"
                situacao = "conectada"
            else:
                conn_str = "livre"
                conn_dev_full = "—"
                conn_dev_short = "--"
                situacao = "sem cabo"

            cfg_if = d["config"]["interfaces"].get(pname, {})
            if cfg_if.get("shutdown"):
                situacao = "shutdown"
            mode = cfg_if.get("switchport_mode") or "access"
            if mode == "trunk":
                base_vlan = cfg_if.get("trunk_allowed_vlan") or "1-1005"
                vlan = f"{base_vlan} (nativa {cfg_if['trunk_native_vlan']})" if cfg_if.get("trunk_native_vlan") else base_vlan
            else:
                vlan = cfg_if.get("access_vlan") or "1"
            sw_port_vlan_map[(d["name"], pname)] = vlan

            switch_ports_table.append(
                {
                    "switch": d["name"],
                    "port": short_p,
                    "full_port": pname,
                    "bw": bw_str,
                    "duplex": duplex_str,
                    "connected_to": conn_str,
                    "connected_dev_full": conn_dev_full,
                    "connected_dev_short": conn_dev_short,
                    "situacao": situacao,
                    "mode": mode,
                    "vlan": vlan,
                    "shutdown": cfg_if.get("shutdown", False),
                }
            )

    # Mapear Gateway IP -> Sub-rede para inferência de rede dos Hosts via DHCP
    gw_to_subnet = {rif["ip"]: rif["subnet"] for rif in router_ifaces}
    for d in devices:
        for pool in d["config"]["dhcp_pools"]:
            if pool.get("default_router") and pool.get("network"):
                parts = pool["network"].split()
                if len(parts) == 2:
                    gw_to_subnet.setdefault(pool["default_router"], ip_to_subnet(parts[0], parts[1]))

    # Consolidar Estações Finais / Hosts (PCs, Laptops, Servidores, Impressoras, etc.)
    pcs_table = []
    for d in sorted(devices, key=lambda x: natural_key(x["name"])):
        if d["type"] not in END_HOST_TYPES:
            continue
        h_ifname = host_link_port.get(d["name"]) or next(iter(d["ports"].keys()), "FastEthernet0")
        peer = port_peer.get((d["name"], h_ifname))
        if peer:
            short_sp = short_ifname(peer[1])
            conn_sw_short = f"{peer[0]} {short_sp}"
            conn_sw_full = f"{peer[0]} {peer[1]}"
        else:
            conn_sw_short = "—"
            conn_sw_full = "—"

        p0 = next(iter(d["ports"].values()), {})
        pip = p0.get("ip", "")
        pmask = p0.get("mask", "")
        if pip:
            addr_str = f"{pip}{mask_to_prefix(pmask)}"
            net_str = ip_to_subnet(pip, pmask)
            subnets_set.add(net_str)
        else:
            addr_str = "DHCP"
            inferred_sub = gw_to_subnet.get(d["gw"])
            if not inferred_sub and peer:
                sw_vlan = sw_port_vlan_map.get((peer[0], peer[1]))
                if sw_vlan and sw_vlan in vlan_to_subnet:
                    inferred_sub = vlan_to_subnet[sw_vlan]
            net_str = f"{inferred_sub} (inferida)" if inferred_sub else "—"

        type_label_map = {
            "Pc": "PC",
            "Laptop": "Laptop",
            "Server": "Servidor",
            "Printer": "Impressora",
            "IpPhone": "Telefone IP",
        }
        pcs_table.append(
            {
                "pc": d["name"],
                "host_type": type_label_map.get(d["type"], d["type"]),
                "iface_full": h_ifname,
                "iface_short": short_ifname(h_ifname),
                "addressing": addr_str,
                "gw": d["gw"],
                "dns": d["dns"],
                "network": net_str,
                "connected_to": conn_sw_short,
                "connected_to_full": conn_sw_full,
            }
        )

    # Detectar protocolos globais ativos
    protocols_detected = set()
    for d in devices:
        cfg = d["config"]
        if cfg["ospf"]:
            protocols_detected.add("OSPF")
        if cfg["rip"]:
            protocols_detected.add("RIP")
        if cfg["eigrp"]:
            protocols_detected.add("EIGRP")
        if cfg["static_routes"]:
            protocols_detected.add("STATIC_ROUTING")
        if cfg["dhcp_pools"]:
            protocols_detected.add("DHCP")
        if cfg["vlans"] or any(
            i.get("encapsulation") or i.get("access_vlan") or i.get("switchport_mode") == "trunk"
            for i in cfg["interfaces"].values()
        ):
            protocols_detected.add("VLAN")
        if cfg["acls"]:
            protocols_detected.add("ACL")
        if cfg["nat"]:
            protocols_detected.add("NAT")

    # Calcular RIB esperada multi-protocolo (OSPF, RIP, EIGRP, Rotas Estáticas e Conectadas)
    rib_by_router = compute_expected_rib(devices, router_ifaces, sorted(subnets_set, key=natural_key))

    return {
        "version": version,
        "devices": devices,
        "links": links,
        "router_ifaces": router_ifaces,
        "switch_ports": switch_ports_table,
        "pcs": pcs_table,
        "subnets": sorted(subnets_set, key=natural_key),
        "protocols": sorted(protocols_detected),
        "rib": rib_by_router,
    }


def compute_expected_rib(devices: list, router_ifaces: list, all_subnets: list) -> dict:
    """
    Calcula a RIB esperada suportando qualquer topologia e protocolo de roteamento:
    - Conectadas diretamente ('C')
    - Rotas Estáticas ('S', AD=1)
    - EIGRP ('D', AD=90, métrica composta)
    - OSPF ('O', AD=110, métrica por custo 10^8/bw)
    - RIP ('R', AD=120, métrica por contagem de saltos)
    """
    routers = [d for d in devices if d["type"] in ("Router", "Multilayer Switch") and any(ifd["ip"] for ifd in d["config"]["interfaces"].values())]
    if not routers:
        return {}

    subnet_attachments = {}
    router_hostname = {r["name"]: r["hostname"] for r in routers}
    for rif in router_ifaces:
        if rif["dev_name"] not in router_hostname:
            continue
        subnet_attachments.setdefault(rif["subnet"], []).append(rif)

    adj = {r["name"]: [] for r in routers}
    for sub, rifs in subnet_attachments.items():
        if len(rifs) >= 2:
            for a in rifs:
                for b in rifs:
                    if a["dev_name"] != b["dev_name"]:
                        adj[a["dev_name"]].append((b["dev_name"], a["iface"], b["ip"], a["cost_ospf"], a.get("bw_kbps", 1544)))

    def run_dijkstra(start_router: str, mode: str):
        dist = {rn: float("inf") for rn in adj}
        first_hops = {rn: [] for rn in adj}
        dist[start_router] = 0
        pq = [(0, start_router)]

        while pq:
            d_u, u = heapq.heappop(pq)
            if d_u > dist[u]:
                continue
            for v, out_if, nh_ip, cost_ospf, bw_kbps in adj[u]:
                if mode == "RIP":
                    w = 1
                elif mode == "EIGRP":
                    w = max(256, int(256 * (10000000 // max(bw_kbps, 1) + (2000 if bw_kbps <= 2000 else 10))))
                else:
                    w = cost_ospf
                new_cost = d_u + w
                hops_to_v = [(out_if, nh_ip)] if u == start_router else list(first_hops[u])
                if new_cost < dist[v]:
                    dist[v] = new_cost
                    first_hops[v] = list(hops_to_v)
                    heapq.heappush(pq, (new_cost, v))
                elif new_cost == dist[v]:
                    for h in hops_to_v:
                        if h not in first_hops[v]:
                            first_hops[v].append(h)
        return dist, first_hops

    rib_result = {}
    for r in sorted(routers, key=lambda x: natural_key(x["name"])):
        rname = r["name"]
        rcfg = r["config"]
        r_ifaces = [rif for rif in router_ifaces if rif["dev_name"] == rname]

        # Resolver rotas estáticas configuradas localmente no roteador
        static_map = {}
        for dst_ip, mask_str, nh_val in rcfg["static_routes"]:
            sub = ip_to_subnet(dst_ip, mask_str)
            out_if = nh_val
            nh_ip = "--"
            try:
                nh_addr = ipaddress.IPv4Address(nh_val)
                nh_ip = nh_val
                out_if = "—"
                for rif in r_ifaces:
                    if nh_addr in ipaddress.IPv4Network(rif["subnet"], strict=False):
                        out_if = rif["iface"]
                        break
            except Exception:
                pass
            static_map.setdefault(sub, []).append((out_if, nh_ip))

        # Determinar protocolo dinâmico preferencial ativo no roteador (menor Distância Administrativa)
        dyn_mode = None
        dyn_code = None
        if rcfg["eigrp"]:
            dyn_mode, dyn_code = "EIGRP", "D"
        elif rcfg["ospf"]:
            dyn_mode, dyn_code = "OSPF", "O"
        elif rcfg["rip"]:
            dyn_mode, dyn_code = "RIP", "R"

        dist, first_hops = run_dijkstra(rname, dyn_mode or "OSPF") if dyn_mode else ({}, {})

        entries = []
        for sub in sorted(all_subnets, key=natural_key):
            rifs_on_sub = subnet_attachments.get(sub, [])
            direct = [x for x in rifs_on_sub if x["dev_name"] == rname]
            if direct:
                entries.append(
                    {
                        "subnet": sub,
                        "code": "C",
                        "out_ifaces": direct[0]["iface"],
                        "metric": "--",
                        "next_hops": "--",
                    }
                )
            elif sub in static_map:
                shocks = static_map[sub]
                out_ifs = ", ".join(dict.fromkeys(h[0] for h in shocks))
                nh_ips = ", ".join(dict.fromkeys(h[1] for h in shocks))
                entries.append(
                    {
                        "subnet": sub,
                        "code": "S",
                        "out_ifaces": out_ifs,
                        "metric": "0",
                        "next_hops": nh_ips,
                    }
                )
            elif dyn_mode:
                best_cost = float("inf")
                best_hops = []
                for owner in rifs_on_sub:
                    owner_name = owner["dev_name"]
                    if dist.get(owner_name, float("inf")) < float("inf"):
                        leaf_cost = 0 if dyn_mode == "RIP" else (2560 if dyn_mode == "EIGRP" else owner["cost_ospf"])
                        total_c = dist[owner_name] + leaf_cost
                        if total_c < best_cost:
                            best_cost = total_c
                            best_hops = list(first_hops[owner_name])
                        elif total_c == best_cost:
                            for h in first_hops[owner_name]:
                                if h not in best_hops:
                                    best_hops.append(h)
                if best_cost < float("inf"):
                    out_ifs = ", ".join(dict.fromkeys(h[0] for h in best_hops))
                    nh_ips = ", ".join(dict.fromkeys(h[1] for h in best_hops))
                    entries.append(
                        {
                            "subnet": sub,
                            "code": dyn_code,
                            "out_ifaces": out_ifs,
                            "metric": str(best_cost),
                            "next_hops": nh_ips,
                        }
                    )
        rib_result[f"{r['hostname']} ({rname})"] = entries

    return rib_result


def build_9_sections_data(parsed_data: dict) -> dict:
    """Constrói todas as 9 seções analíticas para .md, .html e tabelas_geradas.tex."""
    devices = sorted(
        parsed_data["devices"],
        key=lambda d: (0 if d["type"] == "Router" else (1 if "Switch" in d["type"] else 2), natural_key(d["name"])),
    )
    routers = [d for d in devices if d["type"] == "Router"]
    switches = [d for d in devices if "Switch" in d["type"]]
    end_hosts = [d for d in devices if d["type"] in END_HOST_TYPES]

    # 1. Resumo
    resumo_rows = [
        ("Versão do Packet Tracer", parsed_data["version"]),
        ("Roteador(s)", str(len(routers))),
        ("Switch(s)", str(len(switches))),
        ("PC(s)", str(len(end_hosts))),
        ("Enlaces (cabos)", str(len(parsed_data["links"]))),
        ("Sub-redes IPv4 distintas", str(len(parsed_data["subnets"]))),
        ("Interfaces com IP", str(len(parsed_data["router_ifaces"]))),
    ]

    # 2. Dispositivos
    type_pt = {
        "Router": "Roteador",
        "Switch": "Switch",
        "Multilayer Switch": "Switch Multicamada",
        "Pc": "PC",
        "Laptop": "Laptop",
        "Server": "Servidor",
        "Printer": "Impressora",
        "IpPhone": "Telefone IP",
        "Voip": " Adaptador VoIP",
        "WirelessEndDevice": "Host Sem Fio",
        "Tv": "TV",
        "Tablet": "Tablet",
        "SmartPhone": "Smartphone",
        "GenericEndDevice": "Host Genérico",
        "AccessPoint": "Access Point",
        "Cloud": "Nuvem WAN",
    }
    disp_rows = []
    for d in devices:
        disp_rows.append(
            (
                d["name"],
                type_pt.get(d["type"], d["type"]),
                d["model"],
                d["hostname"],
                d["serial"],
                str(d["phys_ifaces_count"]),
                d["gw"],
                d["dns"],
            )
        )

    # 3. Interfaces de roteadores e SVIs (ordenadas por nome do dispositivo e interface natural)
    rif_sorted = sorted(parsed_data["router_ifaces"], key=lambda x: (natural_key(x["dev_name"]), natural_key(x["iface"])))

    # 6. Enlaces
    enlaces_rows = []
    for idx, l in enumerate(parsed_data["links"], 1):
        enlaces_rows.append(
            (
                str(idx),
                l["from_dev"],
                l["from_port"],
                short_ifname(l["from_port"]),
                l["to_dev"],
                l["to_port"],
                short_ifname(l["to_port"]),
                l["cable_type"],
            )
        )

    # 7. Sub-redes
    sub_rows = []
    for sub in parsed_data["subnets"]:
        net = ipaddress.IPv4Network(sub, strict=False)
        hosts = list(net.hosts()) if net.num_addresses <= 1024 else [net.network_address + 1, net.broadcast_address - 1]
        range_str = f"{hosts[0]} – {hosts[-1]}" if len(hosts) >= 2 else str(net)
        rifs = [r for r in rif_sorted if r["subnet"] == sub]
        if_str = "; ".join(f"{r['dev_name']} {r['short_iface']} – {r['ip']}" for r in rifs)
        sub_rows.append((sub, str(net.netmask), range_str, if_str))

    # 8. VLANs
    vlan_rows = []
    for sw in switches:
        sw_ports = [sp for sp in parsed_data["switch_ports"] if sp["switch"] == sw["name"] and not sp["shutdown"] and sp["mode"] == "access"]
        vlans_in_sw = {"1": "default"}
        vlans_in_sw.update(sw["config"]["vlans"])
        for vid in sorted(vlans_in_sw.keys(), key=lambda x: int(x)):
            vname = vlans_in_sw[vid]
            ports_in_v = [sp["port"] for sp in sw_ports if sp["vlan"] == vid]
            vlan_rows.append((sw["name"], vid, vname, ", ".join(ports_in_v) or "—"))

    # 9. Protocolos de roteamento (Roteadores e Switches Multicamada)
    proto_rows = []
    verificacoes = []
    l3_devs = [d for d in devices if d["type"] in ("Router", "Multilayer Switch")]
    for r in l3_devs:
        cfg = r["config"]
        r_if_ips = [ipaddress.IPv4Address(ifd["ip"]) for ifd in cfg["interfaces"].values() if ifd["ip"]]
        for ospf in cfg["ospf"]:
            nets_fmt = [f"{wildcard_to_prefix(n, wc)} (área {a})" for n, wc, a in ospf["networks"]]
            pas_fmt = ", ".join(short_ifname(p) for p in ospf["passives"]) or "—"
            proto_rows.append((r["name"], f"ospf {ospf['process']}", ospf["router_id"] or "—", "; ".join(nets_fmt), pas_fmt))
        for eigrp in cfg.get("eigrp", []):
            nets_fmt = [wildcard_to_prefix(n, wc) if wc else n for n, wc, _ in eigrp["networks"]]
            pas_fmt = ", ".join(short_ifname(p) for p in eigrp["passives"]) or "—"
            asn = eigrp.get("as") or eigrp.get("asn") or "1"
            proto_rows.append((r["name"], f"eigrp {asn}", eigrp.get("router_id") or "—", "; ".join(nets_fmt), pas_fmt))
        for rip in cfg["rip"]:
            nets_fmt = [n for n, _, _ in rip["networks"]]
            pas_fmt = ", ".join(short_ifname(p) for p in rip["passives"]) or "—"
            proto_rows.append((r["name"], "rip", "—", "; ".join(nets_fmt), pas_fmt))
            for n, _, _ in rip["networks"]:
                try:
                    cnet = ipaddress.IPv4Network(f"{n}/16" if n.startswith("172.") or n.startswith("170.") else f"{n}/24", strict=False)
                    if not any(ip in cnet for ip in r_if_ips):
                        verificacoes.append(f"{r['name']}: router rip anuncia '{n}', que não contém nenhuma interface do equipamento.")
                except Exception:
                    pass
        if cfg.get("static_routes"):
            st_fmt = []
            for sr in cfg["static_routes"]:
                dest_s, mask_s, nh_s = sr if isinstance(sr, tuple) else (sr["dest"], sr["mask"], sr["next_hop"])
                try:
                    snet = str(ipaddress.IPv4Network(f"{dest_s}/{mask_s}", strict=False))
                except Exception:
                    snet = f"{dest_s} {mask_s}"
                st_fmt.append(f"{snet} via {nh_s}")
            proto_rows.append((r["name"], "estático", "—", "; ".join(st_fmt), "—"))

    # 10. Pools DHCP (Roteadores e Switches L2/L3)
    dhcp_rows = []
    for d in routers + switches:
        cfg = d["config"]
        if not cfg["dhcp_pools"]:
            continue
        excl_list = []
        for ex in cfg["dhcp_excluded"]:
            parts = ex.replace("ip dhcp excluded-address", "").strip().split()
            if len(parts) == 2:
                excl_list.append(f"{parts[0]} – {parts[1]}")
            elif len(parts) == 1:
                excl_list.append(parts[0])
        excl_str = "; ".join(excl_list) or "—"
        for pool in cfg["dhcp_pools"]:
            net_mask = pool["network"].replace(" ", " / ") if pool["network"] else "—"
            dhcp_rows.append((d["name"], pool["name"], net_mask, pool["default_router"] or "—", pool["dns"] or "—", excl_str))

    return {
        "resumo": resumo_rows,
        "dispositivos": disp_rows,
        "rif_sorted": rif_sorted,
        "enlaces": enlaces_rows,
        "subredes": sub_rows,
        "vlans": vlan_rows,
        "protocolos": proto_rows,
        "dhcp": dhcp_rows,
        "verificacoes": verificacoes,
    }


def write_latex_tables(parsed_data: dict, tabelas_dir: Path):
    tabelas_dir.mkdir(parents=True, exist_ok=True)
    sec9 = build_9_sections_data(parsed_data)

    # 1. ifaces.tex
    ifaces_lines = [
        r"\begin{tabular}{llllll}",
        r"\toprule",
        r"Roteador & Interface & IP & Prefixo & Banda & Clock/Tipo\\",
        r"\midrule",
    ]
    last_host = None
    for rif in parsed_data["router_ifaces"]:
        if last_host is not None and rif["hostname"] != last_host:
            ifaces_lines.append(r"\midrule")
        last_host = rif["hostname"]
        ifaces_lines.append(
            f"{latex_escape(rif['hostname'])} & {latex_escape(rif['iface'])} & "
            f"{latex_escape(rif['ip'])} & {latex_escape(rif['prefix'])} & "
            f"{latex_escape(rif['bw'])} & {latex_escape(rif['clock_type'])}\\\\"
        )
    ifaces_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (tabelas_dir / "ifaces.tex").write_text("\n".join(ifaces_lines) + "\n", encoding="utf-8")

    # 2. switchports.tex
    sw_lines = [
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"Switch & Porta & Banda & Conectado a\\",
        r"\midrule",
    ]
    last_sw = None
    for sp in parsed_data["switch_ports"]:
        if last_sw is not None and sp["switch"] != last_sw:
            sw_lines.append(r"\midrule")
        last_sw = sp["switch"]
        sw_lines.append(
            f"{latex_escape(sp['switch'])} & {latex_escape(sp['port'])} & "
            f"{latex_escape(sp['bw'])} & {latex_escape(sp['connected_to'])}\\\\"
        )
    sw_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (tabelas_dir / "switchports.tex").write_text("\n".join(sw_lines) + "\n", encoding="utf-8")

    # 2b. vlans.tex (gerado automaticamente quando existem VLANs customizadas > 1)
    custom_vlans = [row for row in sec9["vlans"] if row[1] != "1"]
    if custom_vlans:
        v_lines = [
            r"\begin{tabular}{llll}",
            r"\toprule",
            r"Switch & VLAN & Nome & Portas Access\\",
            r"\midrule",
        ]
        last_vsw = None
        for sw_n, vid, vname, p_list in sec9["vlans"]:
            if last_vsw is not None and sw_n != last_vsw:
                v_lines.append(r"\midrule")
            last_vsw = sw_n
            v_lines.append(f"{latex_escape(sw_n)} & {latex_escape(vid)} & {latex_escape(vname)} & {latex_escape(p_list)}\\\\")
        v_lines.extend([r"\bottomrule", r"\end{tabular}"])
        (tabelas_dir / "vlans.tex").write_text("\n".join(v_lines) + "\n", encoding="utf-8")

    # 3. pcs.tex
    pcs_lines = [
        r"\begin{tabular}{ll}",
        r"\toprule",
        r"PC & Conectado ao Switch\\",
        r"\midrule",
    ]
    for pc in parsed_data["pcs"]:
        pcs_lines.append(f"{latex_escape(pc['pc'])} & {latex_escape(pc['connected_to'])}\\\\")
    pcs_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (tabelas_dir / "pcs.tex").write_text("\n".join(pcs_lines) + "\n", encoding="utf-8")

    # 4. rib.tex
    rib_lines = []
    for rtitle, entries in parsed_data["rib"].items():
        rib_lines.append(f"\\subsection*{{{latex_escape(rtitle)}}}")
        rib_lines.append(
            r"\begin{tabular}{@{}llllp{3.6cm}@{}}\toprule Destino & Cód. & Interface de saída & Métrica & Próximo salto\\\midrule"
        )
        for e in entries:
            rib_lines.append(
                f"{latex_escape(e['subnet'])} & {latex_escape(e['code'])} & "
                f"{latex_escape(e['out_ifaces'])} & {latex_escape(e['metric'])} & "
                f"{latex_escape(e['next_hops'])}\\\\"
            )
        rib_lines.append(r"\bottomrule\end{tabular}" + "\n")
    (tabelas_dir / "rib.tex").write_text("\n".join(rib_lines), encoding="utf-8")

    # 5. configs.tex (inclui Roteadores e Switches que possuam configurações L2/L3 customizadas)
    cfg_lines = []
    for d in sorted(parsed_data["devices"], key=lambda x: natural_key(x["name"])):
        if not d["config"]["essential_lines"]:
            continue
        is_router = d["type"] == "Router"
        has_custom_sw_cfg = ("Switch" in d["type"]) and (
            bool(d["config"]["vlans"])
            or bool(d["config"]["dhcp_pools"])
            or any(
                ifd.get("ip") or ifd.get("switchport_mode") == "trunk" or (ifd.get("access_vlan") or "1") != "1"
                for ifd in d["config"]["interfaces"].values()
            )
        )
        if not (is_router or has_custom_sw_cfg):
            continue
        cfg_lines.append(f"\\subsection*{{{latex_escape(d['name'])}}}")
        cfg_lines.append(r"\begin{lstlisting}")
        cfg_lines.extend(d["config"]["essential_lines"])
        cfg_lines.append(r"\end{lstlisting}")
    (tabelas_dir / "configs.tex").write_text("\n".join(cfg_lines), encoding="utf-8")

    # 6. tabelas_geradas.tex (9 seções completas em longtable)
    tg = []
    tg.extend(
        [
            r"\subsection{Resumo}",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-8pt)*26/40\relax}p{\dimexpr(\linewidth-8pt)*14/40\relax}@{}}",
            r"\toprule \textbf{Item} & \textbf{Quantidade} \\\midrule\endfirsthead",
            r"\toprule \textbf{Item} & \textbf{Quantidade} \\\midrule\endhead",
        ]
    )
    for k, v in sec9["resumo"]:
        tg.append(f"{latex_escape(k)} & {latex_escape(v)} \\\\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Dispositivos}",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-44pt)*9/101\relax}p{\dimexpr(\linewidth-44pt)*10/101\relax}p{\dimexpr(\linewidth-44pt)*17/101\relax}p{\dimexpr(\linewidth-44pt)*12/101\relax}p{\dimexpr(\linewidth-44pt)*14/101\relax}p{\dimexpr(\linewidth-44pt)*14/101\relax}p{\dimexpr(\linewidth-44pt)*16/101\relax}p{\dimexpr(\linewidth-44pt)*9/101\relax}@{}}",
            r"\toprule \textbf{Nome} & \textbf{Tipo} & \textbf{Modelo} & \textbf{Hostname (config)} & \textbf{Nº de série} & \textbf{Interfaces físicas} & \textbf{Gateway padrão} & \textbf{DNS} \\\midrule\endfirsthead",
            r"\toprule \textbf{Nome} & \textbf{Tipo} & \textbf{Modelo} & \textbf{Hostname (config)} & \textbf{Nº de série} & \textbf{Interfaces físicas} & \textbf{Gateway padrão} & \textbf{DNS} \\\midrule\endhead",
        ]
    )
    for row in sec9["dispositivos"]:
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Interfaces de roteadores e SVIs}",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-56pt)*16/134\relax}p{\dimexpr(\linewidth-56pt)*12/134\relax}p{\dimexpr(\linewidth-56pt)*13/134\relax}p{\dimexpr(\linewidth-56pt)*16/134\relax}p{\dimexpr(\linewidth-56pt)*15/134\relax}p{\dimexpr(\linewidth-56pt)*11/134\relax}p{\dimexpr(\linewidth-56pt)*11/134\relax}p{\dimexpr(\linewidth-56pt)*13/134\relax}p{\dimexpr(\linewidth-56pt)*12/134\relax}p{\dimexpr(\linewidth-56pt)*15/134\relax}@{}}",
            r"\toprule \textbf{Dispositivo} & \textbf{Hostname} & \textbf{Interface} & \textbf{IP} & \textbf{Máscara} & \textbf{Prefixo} & \textbf{Banda} & \textbf{Descrição} & \textbf{Situação} & \textbf{Conectado a} \\\midrule\endfirsthead",
            r"\toprule \textbf{Dispositivo} & \textbf{Hostname} & \textbf{Interface} & \textbf{IP} & \textbf{Máscara} & \textbf{Prefixo} & \textbf{Banda} & \textbf{Descrição} & \textbf{Situação} & \textbf{Conectado a} \\\midrule\endhead",
        ]
    )
    for r in sec9["rif_sorted"]:
        row = (
            r["dev_name"],
            r["hostname"],
            r["short_iface"],
            r["ip"],
            r["mask"],
            r["prefix"],
            r["bw"],
            r["description"],
            r["status"],
            r["peer_short"],
        )
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Portas de switch}",
            r"\noindent\textit{Modo/VLAN vêm da running-config; porta sem 'switchport' explícito é access na VLAN 1.}\par\smallskip",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-44pt)*10/84\relax}p{\dimexpr(\linewidth-44pt)*8/84\relax}p{\dimexpr(\linewidth-44pt)*10/84\relax}p{\dimexpr(\linewidth-44pt)*10/84\relax}p{\dimexpr(\linewidth-44pt)*8/84\relax}p{\dimexpr(\linewidth-44pt)*11/84\relax}p{\dimexpr(\linewidth-44pt)*12/84\relax}p{\dimexpr(\linewidth-44pt)*15/84\relax}@{}}",
            r"\toprule \textbf{Switch} & \textbf{Porta} & \textbf{Banda} & \textbf{Duplex} & \textbf{Modo} & \textbf{VLAN(s)} & \textbf{Situação} & \textbf{Conectado a} \\\midrule\endfirsthead",
            r"\toprule \textbf{Switch} & \textbf{Porta} & \textbf{Banda} & \textbf{Duplex} & \textbf{Modo} & \textbf{VLAN(s)} & \textbf{Situação} & \textbf{Conectado a} \\\midrule\endhead",
        ]
    )
    for sp in parsed_data["switch_ports"]:
        row = (
            sp["switch"],
            sp["port"],
            sp["bw"],
            sp["duplex"],
            sp["mode"],
            sp["vlan"],
            sp["situacao"],
            sp["connected_dev_short"],
        )
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Hosts}",
            r"\noindent\textit{IP vazio com endereçamento DHCP: a concessão não é salva no .pkt.}\par\smallskip",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-44pt)*16/122\relax}p{\dimexpr(\linewidth-44pt)*7/122\relax}p{\dimexpr(\linewidth-44pt)*13/122\relax}p{\dimexpr(\linewidth-44pt)*18/122\relax}p{\dimexpr(\linewidth-44pt)*16/122\relax}p{\dimexpr(\linewidth-44pt)*9/122\relax}p{\dimexpr(\linewidth-44pt)*28/122\relax}p{\dimexpr(\linewidth-44pt)*15/122\relax}@{}}",
            r"\toprule \textbf{Dispositivo} & \textbf{Tipo} & \textbf{Interface} & \textbf{Endereçamento} & \textbf{Gateway} & \textbf{DNS} & \textbf{Rede} & \textbf{Conectado a} \\\midrule\endfirsthead",
            r"\toprule \textbf{Dispositivo} & \textbf{Tipo} & \textbf{Interface} & \textbf{Endereçamento} & \textbf{Gateway} & \textbf{DNS} & \textbf{Rede} & \textbf{Conectado a} \\\midrule\endhead",
        ]
    )
    for pc in parsed_data["pcs"]:
        row = (
            pc["pc"],
            pc.get("host_type", "PC"),
            pc["iface_short"],
            pc["addressing"],
            pc["gw"],
            pc["dns"],
            pc["network"],
            pc["connected_to"],
        )
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Enlaces}",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-32pt)*4/60\relax}p{\dimexpr(\linewidth-32pt)*16/60\relax}p{\dimexpr(\linewidth-32pt)*8/60\relax}p{\dimexpr(\linewidth-32pt)*16/60\relax}p{\dimexpr(\linewidth-32pt)*8/60\relax}p{\dimexpr(\linewidth-32pt)*8/60\relax}@{}}",
            r"\toprule \textbf{\#} & \textbf{Dispositivo A} & \textbf{Porta A} & \textbf{Dispositivo B} & \textbf{Porta B} & \textbf{Cabo} \\\midrule\endfirsthead",
            r"\toprule \textbf{\#} & \textbf{Dispositivo A} & \textbf{Porta A} & \textbf{Dispositivo B} & \textbf{Porta B} & \textbf{Cabo} \\\midrule\endhead",
        ]
    )
    for idx_s, d1, _p1_full, p1_short, d2, _p2_full, p2_short, ctype in sec9["enlaces"]:
        tg.append(" & ".join(latex_escape(c) for c in (idx_s, d1, p1_short, d2, p2_short, ctype)) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{Sub-redes}",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-20pt)*17/92\relax}p{\dimexpr(\linewidth-20pt)*15/92\relax}p{\dimexpr(\linewidth-20pt)*30/92\relax}p{\dimexpr(\linewidth-20pt)*30/92\relax}@{}}",
            r"\toprule \textbf{Rede} & \textbf{Máscara} & \textbf{Faixa de hosts} & \textbf{Interfaces (dispositivo interface – IP)} \\\midrule\endfirsthead",
            r"\toprule \textbf{Rede} & \textbf{Máscara} & \textbf{Faixa de hosts} & \textbf{Interfaces (dispositivo interface – IP)} \\\midrule\endhead",
        ]
    )
    for row in sec9["subredes"]:
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    tg.extend(
        [
            r"\subsection{VLANs}",
            r"\noindent\textit{Portas em shutdown e trunks não entram na lista de portas access.}\par\smallskip",
            r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{@{}p{\dimexpr(\linewidth-20pt)*10/54\relax}p{\dimexpr(\linewidth-20pt)*7/54\relax}p{\dimexpr(\linewidth-20pt)*9/54\relax}p{\dimexpr(\linewidth-20pt)*28/54\relax}@{}}",
            r"\toprule \textbf{Switch} & \textbf{VLAN} & \textbf{Nome} & \textbf{Portas access} \\\midrule\endfirsthead",
            r"\toprule \textbf{Switch} & \textbf{VLAN} & \textbf{Nome} & \textbf{Portas access} \\\midrule\endhead",
        ]
    )
    for row in sec9["vlans"]:
        tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
    tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    if sec9["protocolos"]:
        tg.extend(
            [
                r"\subsection{Protocolos de roteamento}",
                r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
                r"\begin{longtable}{@{}p{\dimexpr(\linewidth-26pt)*16/86\relax}p{\dimexpr(\linewidth-26pt)*13/86\relax}p{\dimexpr(\linewidth-26pt)*13/86\relax}p{\dimexpr(\linewidth-26pt)*30/86\relax}p{\dimexpr(\linewidth-26pt)*14/86\relax}@{}}",
                r"\toprule \textbf{Dispositivo} & \textbf{Protocolo} & \textbf{Router-ID} & \textbf{Redes anunciadas} & \textbf{Interfaces passivas} \\\midrule\endfirsthead",
                r"\toprule \textbf{Dispositivo} & \textbf{Protocolo} & \textbf{Router-ID} & \textbf{Redes anunciadas} & \textbf{Interfaces passivas} \\\midrule\endhead",
            ]
        )
        for row in sec9["protocolos"]:
            tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
        tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    if sec9["dhcp"]:
        tg.extend(
            [
                r"\subsection{Pools DHCP (roteadores)}",
                r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
                r"\begin{longtable}{@{}p{\dimexpr(\linewidth-32pt)*16/118\relax}p{\dimexpr(\linewidth-32pt)*17/118\relax}p{\dimexpr(\linewidth-32pt)*30/118\relax}p{\dimexpr(\linewidth-32pt)*16/118\relax}p{\dimexpr(\linewidth-32pt)*9/118\relax}p{\dimexpr(\linewidth-32pt)*30/118\relax}@{}}",
                r"\toprule \textbf{Dispositivo} & \textbf{Pool} & \textbf{Rede / máscara} & \textbf{Gateway} & \textbf{DNS} & \textbf{Endereços excluídos} \\\midrule\endfirsthead",
                r"\toprule \textbf{Dispositivo} & \textbf{Pool} & \textbf{Rede / máscara} & \textbf{Gateway} & \textbf{DNS} & \textbf{Endereços excluídos} \\\midrule\endhead",
            ]
        )
        for row in sec9["dhcp"]:
            tg.append(" & ".join(latex_escape(c) for c in row) + r" \\")
        tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    if sec9["verificacoes"]:
        tg.extend(
            [
                r"\subsection{Verificações}",
                r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}",
                r"\begin{longtable}{@{}p{\dimexpr(\linewidth-8pt)*3/33\relax}p{\dimexpr(\linewidth-8pt)*30/33\relax}@{}}",
                r"\toprule \textbf{\#} & \textbf{Observação} \\\midrule\endfirsthead",
                r"\toprule \textbf{\#} & \textbf{Observação} \\\midrule\endhead",
            ]
        )
        for i, obs in enumerate(sec9["verificacoes"], 1):
            tg.append(f"{i} & {latex_escape(obs)} \\\\")
        tg.extend([r"\bottomrule", r"\end{longtable}\endgroup", ""])

    (tabelas_dir / "tabelas_geradas.tex").write_text("\n".join(tg).rstrip() + "\n", encoding="utf-8")


def write_analysis_md_and_html(parsed_data: dict, analise_dir: Path, num_int: int):
    analise_dir.mkdir(parents=True, exist_ok=True)
    sec9 = build_9_sections_data(parsed_data)
    num_str = f"{num_int:02d}"
    ts_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 1. Markdown completo de 9 seções
    md = [
        f"# Relatório de rede — cenario_{num_str}_equipe_08_Lab_SD",
        "",
        f"Origem: `cenario_{num_str}_equipe_08_Lab_SD.xml` · Packet Tracer {parsed_data['version']} · gerado em {ts_str}",
        "",
        "### Resumo",
        "",
        "| Item | Quantidade |",
        "|---|---|",
    ]
    for k, v in sec9["resumo"]:
        md.append(f"| {k} | {v} |")

    md.extend(
        [
            "",
            "### Dispositivos",
            "",
            "| Nome | Tipo | Modelo | Hostname (config) | Nº de série | Interfaces físicas | Gateway padrão | DNS |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in sec9["dispositivos"]:
        md.append("| " + " | ".join(row) + " |")

    md.extend(
        [
            "",
            "### Interfaces de roteadores e SVIs",
            "",
            "| Dispositivo | Hostname | Interface | IP | Máscara | Prefixo | Banda | Descrição | Situação | Conectado a |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for r in sec9["rif_sorted"]:
        md.append(
            f"| {r['dev_name']} | {r['hostname']} | {r['iface']} | {r['ip']} | {r['mask']} | "
            f"{r['prefix']} | {r['bw']} | {r['description']} | {r['status']} | {r['peer']} |"
        )

    md.extend(
        [
            "",
            "### Portas de switch",
            "",
            "_Modo/VLAN vêm da running-config; porta sem 'switchport' explícito é access na VLAN 1._",
            "",
            "| Switch | Porta | Banda | Duplex | Modo | VLAN(s) | Situação | Conectado a |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for sp in parsed_data["switch_ports"]:
        md.append(
            f"| {sp['switch']} | {sp['full_port']} | {sp['bw']} | {sp['duplex']} | "
            f"{sp['mode']} | {sp['vlan']} | {sp['situacao']} | {sp['connected_dev_full']} |"
        )

    md.extend(
        [
            "",
            "### Hosts",
            "",
            "_IP vazio com endereçamento DHCP: a concessão não é salva no .pkt._",
            "",
            "| Dispositivo | Tipo | Interface | Endereçamento | Gateway | DNS | Rede | Conectado a |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for pc in parsed_data["pcs"]:
        md.append(
            f"| {pc['pc']} | {pc.get('host_type', 'PC')} | {pc['iface_full']} | {pc['addressing']} | "
            f"{pc['gw']} | {pc['dns']} | {pc['network']} | {pc['connected_to_full']} |"
        )

    md.extend(
        [
            "",
            "### Enlaces",
            "",
            "| # | Dispositivo A | Porta A | Dispositivo B | Porta B | Cabo |",
            "|---|---|---|---|---|---|",
        ]
    )
    for idx_s, d1, p1_full, _p1_s, d2, p2_full, _p2_s, ctype in sec9["enlaces"]:
        md.append(f"| {idx_s} | {d1} | {p1_full} | {d2} | {p2_full} | {ctype} |")

    md.extend(
        [
            "",
            "### Sub-redes",
            "",
            "| Rede | Máscara | Faixa de hosts | Interfaces (dispositivo interface – IP) |",
            "|---|---|---|---|",
        ]
    )
    for row in sec9["subredes"]:
        md.append("| " + " | ".join(row) + " |")

    md.extend(
        [
            "",
            "### VLANs",
            "",
            "_Portas em shutdown e trunks não entram na lista de portas access._",
            "",
            "| Switch | VLAN | Nome | Portas access |",
            "|---|---|---|---|",
        ]
    )
    for row in sec9["vlans"]:
        md.append("| " + " | ".join(row) + " |")

    if sec9["protocolos"]:
        md.extend(
            [
                "",
                "### Protocolos de roteamento",
                "",
                "| Dispositivo | Protocolo | Router-ID | Redes anunciadas | Interfaces passivas |",
                "|---|---|---|---|---|",
            ]
        )
        for row in sec9["protocolos"]:
            md.append("| " + " | ".join(row) + " |")

    if sec9["dhcp"]:
        md.extend(
            [
                "",
                "### Pools DHCP (roteadores)",
                "",
                "| Dispositivo | Pool | Rede / máscara | Gateway | DNS | Endereços excluídos |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in sec9["dhcp"]:
            md.append("| " + " | ".join(row) + " |")

    if sec9["verificacoes"]:
        md.extend(["", "### Verificações", "", "| # | Observação |", "|---|---|"])
        for i, obs in enumerate(sec9["verificacoes"], 1):
            md.append(f"| {i} | {obs} |")

    md_text = "\n".join(md) + "\n"
    md_file = analise_dir / f"relatorio_cenario{num_int}_equipe8_lab_SD.md"
    md_file.write_text(md_text, encoding="utf-8")

    # 2. HTML estilizado com CSS (.rpt)
    def html_table(caption: str, headers: list, rows: list, note: str = "") -> str:
        ths = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        trs = []
        for r in rows:
            tds = "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
            trs.append(f"<tr>{tds}</tr>")
        tbl = f'<table class="rpt"><caption>{html.escape(caption)}</caption><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
        if note:
            tbl += f'<p class="rpt-note">{html.escape(note)}</p>'
        return tbl

    h_parts = [
        f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório de rede — cenario_{num_str}_equipe_08_Lab_SD</title>",
        "<style>",
        ".rpt { border-collapse: collapse; font: 13px/1.4 system-ui, sans-serif; margin: .6em 0 1.2em; }",
        ".rpt caption { text-align: left; font-weight: 600; padding: 4px 0; }",
        ".rpt th, .rpt td { border: 1px solid #8884; padding: 3px 9px; text-align: left; vertical-align: top; }",
        ".rpt th { background: #8882; }",
        ".rpt tr:nth-child(even) td { background: #8881; }",
        ".rpt-note { font: 12px system-ui, sans-serif; opacity: .75; margin: 0 0 .4em; }",
        "</style>",
        "<style>body{max-width:1300px;margin:2em auto;padding:0 1em;font-family:system-ui,sans-serif}@media (prefers-color-scheme: dark){body{background:#16181c;color:#e6e6e6}}</style></head><body>",
        f"<h1>Relatório de rede — cenario_{num_str}_equipe_08_Lab_SD</h1>",
        f"<p>Origem: cenario_{num_str}_equipe_08_Lab_SD.xml · Packet Tracer {html.escape(parsed_data['version'])} · gerado em {ts_str}</p>",
    ]
    h_parts.append(html_table("Resumo", ["Item", "Quantidade"], sec9["resumo"]))
    h_parts.append(
        html_table(
            f"Dispositivos ({len(sec9['dispositivos'])})",
            ["Nome", "Tipo", "Modelo", "Hostname (config)", "Nº de série", "Interfaces físicas", "Gateway padrão", "DNS"],
            sec9["dispositivos"],
        )
    )
    h_parts.append(
        html_table(
            f"Interfaces de roteadores e SVIs ({len(sec9['rif_sorted'])})",
            ["Dispositivo", "Hostname", "Interface", "IP", "Máscara", "Prefixo", "Banda", "Descrição", "Situação", "Conectado a"],
            [
                (r["dev_name"], r["hostname"], r["iface"], r["ip"], r["mask"], r["prefix"], r["bw"], r["description"], r["status"], r["peer"])
                for r in sec9["rif_sorted"]
            ],
        )
    )
    h_parts.append(
        html_table(
            f"Portas de switch ({len(parsed_data['switch_ports'])})",
            ["Switch", "Porta", "Banda", "Duplex", "Modo", "VLAN(s)", "Situação", "Conectado a"],
            [
                (sp["switch"], sp["full_port"], sp["bw"], sp["duplex"], sp["mode"], sp["vlan"], sp["situacao"], sp["connected_dev_full"])
                for sp in parsed_data["switch_ports"]
            ],
            note="Modo/VLAN vêm da running-config; porta sem 'switchport' explícito é access na VLAN 1.",
        )
    )
    h_parts.append(
        html_table(
            f"Hosts ({len(parsed_data['pcs'])})",
            ["Dispositivo", "Tipo", "Interface", "Endereçamento", "Gateway", "DNS", "Rede", "Conectado a"],
            [
                (pc["pc"], pc.get("host_type", "PC"), pc["iface_full"], pc["addressing"], pc["gw"], pc["dns"], pc["network"], pc["connected_to_full"])
                for pc in parsed_data["pcs"]
            ],
            note="IP vazio com endereçamento DHCP: a concessão não é salva no .pkt.",
        )
    )
    h_parts.append(
        html_table(
            f"Enlaces ({len(sec9['enlaces'])})",
            ["#", "Dispositivo A", "Porta A", "Dispositivo B", "Porta B", "Cabo"],
            [(i, d1, p1f, d2, p2f, ct) for i, d1, p1f, _p1s, d2, p2f, _p2s, ct in sec9["enlaces"]],
        )
    )
    h_parts.append(
        html_table(
            f"Sub-redes ({len(sec9['subredes'])})",
            ["Rede", "Máscara", "Faixa de hosts", "Interfaces (dispositivo interface – IP)"],
            sec9["subredes"],
        )
    )
    h_parts.append(
        html_table(
            f"VLANs ({len(sec9['vlans'])})",
            ["Switch", "VLAN", "Nome", "Portas access"],
            sec9["vlans"],
            note="Portas em shutdown e trunks não entram na lista de portas access.",
        )
    )
    if sec9["protocolos"]:
        h_parts.append(
            html_table(
                f"Protocolos de roteamento ({len(sec9['protocolos'])})",
                ["Dispositivo", "Protocolo", "Router-ID", "Redes anunciadas", "Interfaces passivas"],
                sec9["protocolos"],
            )
        )
    if sec9["dhcp"]:
        h_parts.append(
            html_table(
                f"Pools DHCP (roteadores) ({len(sec9['dhcp'])})",
                ["Dispositivo", "Pool", "Rede / máscara", "Gateway", "DNS", "Endereços excluídos"],
                sec9["dhcp"],
            )
        )
    if sec9["verificacoes"]:
        h_parts.append(
            html_table(
                f"Verificações ({len(sec9['verificacoes'])})",
                ["#", "Observação"],
                [(str(i), obs) for i, obs in enumerate(sec9["verificacoes"], 1)],
            )
        )
    h_parts.append("</body></html>\n")
    html_file = analise_dir / f"relatorio_cenario{num_int}_equipe8_lab_SD.html"
    html_file.write_text("\n".join(h_parts), encoding="utf-8")


def render_topology_diagram(parsed_data: dict, output_png: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    connected_names = set()
    for l in parsed_data["links"]:
        connected_names.add(l["from_dev"])
        connected_names.add(l["to_dev"])

    devs = [
        d
        for d in parsed_data["devices"]
        if d["name"] in connected_names or d["type"] in ("Router", "Switch", "Multilayer Switch") or d["type"] in END_HOST_TYPES
    ]
    if not devs:
        return False

    xs = [d["x"] for d in devs if d["x"] > 0]
    ys = [d["y"] for d in devs if d["y"] > 0]
    if not xs or not ys:
        return False

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 100.0)
    span_y = max(max_y - min_y, 100.0)

    width, height = 1400, 900
    pad = 110

    def to_px(x: float, y: float) -> tuple:
        px = int(pad + ((x - min_x) / span_x) * (width - 2 * pad))
        py = int(pad + ((y - min_y) / span_y) * (height - 2 * pad))
        return px, py

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    dev_pos = {d["name"]: to_px(d["x"], d["y"]) for d in devs}

    for l in parsed_data["links"]:
        p1 = dev_pos.get(l["from_dev"])
        p2 = dev_pos.get(l["to_dev"])
        if not p1 or not p2:
            continue
        is_serial = "Serial" in l["from_port"] or "Serial" in l["to_port"]
        color = (200, 40, 40) if is_serial else (60, 60, 60)
        draw.line([p1, p2], fill=color, width=3 if is_serial else 2)

    for d in devs:
        cx, cy = dev_pos[d["name"]]
        dtype = d["type"]
        label = f"{d['hostname']}" if d["hostname"] not in ("—", d["name"]) and dtype == "Router" else d["name"]
        if dtype == "Router":
            r = 26
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(45, 110, 180), outline=(20, 50, 90), width=3)
        elif "Switch" in dtype:
            w, h = 30, 20
            draw.rectangle([cx - w, cy - h, cx + w, cy + h], fill=(50, 155, 95), outline=(25, 80, 50), width=3)
        else:
            w, h = 22, 18
            draw.rectangle([cx - w, cy - h, cx + w, cy + h], fill=(120, 130, 140), outline=(60, 65, 70), width=2)
        draw.text((cx - 18, cy + 30), label, fill=(20, 20, 20))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    return True


def ensure_latex_files_and_readme(parsed_data: dict, cenario_dir: Path, num_int: int, force_regen: bool = False):
    num_str = f"{num_int:02d}"
    ord_simbolo, ord_extenso_f, ord_extenso_m = ORDINAIS.get(num_int, (f"{num_int}º", f"{num_int}ª", f"{num_int}º"))
    rel_dir = cenario_dir / "relatorio"
    sec_dir = rel_dir / "sections"

    # 1. main.tex
    main_tex = rel_dir / "main.tex"
    if not main_tex.exists() or force_regen:
        main_tex.write_text(
            rf"""\documentclass[a4paper, 12pt]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[brazil]{{babel}}
\usepackage[lmargin=3cm, tmargin=3cm, rmargin=2cm, bmargin=2cm]{{geometry}}
\usepackage[portuguese, ruled, linesnumbered]{{algorithm2e}}
\usepackage{{graphicx}}
\usepackage{{listings}}
\usepackage{{enumitem}}
\usepackage{{booktabs}}
\usepackage{{longtable}}
\usepackage{{array}}
\usepackage{{float}}

\usepackage[hypertexnames=false]{{hyperref}}
\hypersetup{{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,      
    urlcolor=cyan,
    pdftitle={{Relatório de Atividades - Laboratório de Sistemas Distribuídos}},
}}

\renewcommand{{\labelitemii}}{{$\circ$}}

\begin{{document}}
\begin{{figure}}
    \centering
    \includegraphics[width=4cm]{{pics/Logo_UFPA.png}}
\end{{figure}}

\begin{{center}}
\textbf{{Universidade Federal do Pará}}\\
\textbf{{Instituto de Ciências Exatas e Naturais}}\\
\textbf{{Faculdade de Ciências da Computação}}\\
\textbf{{Laboratório de Sistemas Distribuídos}}\\
\end{{center}}

\begin{{center}}
\textbf{{{ord_simbolo} Relatório}}
\end{{center}}

\begin{{flushleft}}
\textbf{{Discentes:}}
\begin{{itemize}}[itemsep=0px, label=-]
    \item Júlio Costa Oliveira
    \item Luiz Gabriel Santos Moreira
\end{{itemize}}
\textbf{{Matrículas:}} 
\begin{{itemize}}[itemsep=0px, label=-]
    \item 202104940025
    \item 202304940001
\end{{itemize}}
\textbf{{Data:}} \today
\end{{flushleft}}

\newpage

\input{{sections/introduction}}
\input{{sections/body}}
% \input{{sections/conclusion}}
% \input{{sections/appendix}}
\input{{sections/references}}

\end{{document}}
""",
            encoding="utf-8",
        )

    routers = sorted([d for d in parsed_data["devices"] if d["type"] == "Router"], key=lambda x: natural_key(x["name"]))
    switches = sorted([d for d in parsed_data["devices"] if "Switch" in d["type"]], key=lambda x: natural_key(x["name"]))
    end_hosts = sorted([d for d in parsed_data["devices"] if d["type"] in END_HOST_TYPES], key=lambda x: natural_key(x["name"]))
    protos = ", ".join(parsed_data["protocols"]) if parsed_data["protocols"] else "roteamento e comutação"

    # Detectar arquétipo da topologia automaticamente:
    # 1) WAN Core (apenas Serial) + Edge (Serial + Ethernet) com OSPF (ex: Cenário 02)
    # 2) Topologia com VLANs / Trunks 802.1Q / Router-on-a-Stick / SVI (ex: Cenário 01)
    # 3) Topologia Geral (Roteamento Dinâmico Misto / Estático / LAN-WAN Arbitrária)
    core_routers = []
    edge_routers = []
    for r in routers:
        r_ifs = [ifn for ifn, ifd in r["config"]["interfaces"].items() if ifd["ip"]]
        if r_ifs and all(ifn.startswith("Serial") for ifn in r_ifs):
            core_routers.append(r)
        elif any(ifn.startswith("Serial") for ifn in r_ifs) and any("Ethernet" in ifn for ifn in r_ifs):
            edge_routers.append(r)

    is_core_edge_ospf = bool(core_routers and edge_routers and "OSPF" in parsed_data["protocols"])
    has_custom_vlans = any(bool(sw["config"]["vlans"]) for sw in switches) or "VLANs" in parsed_data["protocols"]
    pt_ver_short = ".".join(parsed_data["version"].split(".")[:3])

    # 2. introduction.tex
    intro_tex = sec_dir / "introduction.tex"
    if not intro_tex.exists() or force_regen:
        if is_core_edge_ospf:
            intro_tex.write_text(
                rf"""\section{{INTRODUÇÃO}}

Este relatório apresenta a documentação e análise detalhada da arquitetura de rede do {ord_extenso_m} cenário do Laboratório de Sistemas Distribuídos, implementada e simulada no Cisco Packet Tracer (v{pt_ver_short}). O cenário compreende uma topologia de rede distribuída com núcleo WAN em malha completa (\textit{{full-mesh}}), roteadores de borda para atendimento a redes locais (LANs), distribuição de hosts e protocolo de roteamento dinâmico OSPF (Open Shortest Path First) operando em área única 0.

O objetivo deste trabalho é analisar os aspectos de camadas física, de enlace e de rede da infraestrutura, detalhando os esquemas de endereçamento IPv4, cálculo de métricas e tabelas de roteamento esperadas (RIB), bem como a redundância e tolerância a falhas provida pelo backbone de interconexão.

\subsection{{Contextualização e Visão Geral da Topologia}}

A topologia interliga quatro localidades departamentais (Sites de A a D) a um núcleo central de comutação de pacotes de alta disponibilidade. O núcleo é formado por quatro roteadores interconectados por enlaces seriais ponto a ponto dedicados, assegurando múltiplos caminhos alternativos para o encaminhamento de tráfego entre qualquer par de redes locais.
""",
                encoding="utf-8",
            )
        else:
            intro_tex.write_text(
                rf"""\section{{INTRODUÇÃO}}

Este relatório apresenta a análise e documentação técnica da arquitetura de rede do {ord_extenso_m} cenário (Cenário {num_str}) do Laboratório de Sistemas Distribuídos, implementada e simulada no Cisco Packet Tracer (v{pt_ver_short}). A topologia exercita conceitos de \textbf{{{protos}}}, interconectando {len(routers)} roteador(es), {len(switches)} comutador(es) e {len(end_hosts)} dispositivos finais através de {len(parsed_data['links'])} enlaces físicos.

\subsection{{Contextualização e Visão Geral da Topologia}}

O experimento avalia a configuração integrada das camadas física, de enlace e de rede, verificando o particionamento lógico em {len(parsed_data['subnets'])} sub-redes IPv4 distintas, o comportamento do encaminhamento de pacotes entre domínios de broadcast e a consistência das tabelas de roteamento (RIB) e políticas de serviços configuradas nos ativos da infraestrutura.
""",
                encoding="utf-8",
            )

    # 3. body.tex
    body_tex = sec_dir / "body.tex"
    if not body_tex.exists() or force_regen:
        if is_core_edge_ospf:
            c_first, c_last = core_routers[0]["hostname"], core_routers[-1]["hostname"]
            e_first, e_last = edge_routers[0]["hostname"], edge_routers[-1]["hostname"]
            sw_first, sw_last = switches[0]["name"], switches[-1]["name"]
            pc_first, pc_last = end_hosts[0]["name"], end_hosts[-1]["name"]
            r_model = core_routers[0]["model"]
            sw_model = switches[0]["model"]
            body_tex.write_text(
                rf"""\section{{ARQUITETURA DA INFRAESTRUTURA}}

\subsection{{Topologia Física e Lógica}}

A infraestrutura é constituída por {len(parsed_data['devices'])} dispositivos interconectados através de {len(parsed_data['links'])} enlaces:
\begin{{itemize}}[leftmargin=2em]
  \item \textbf{{Núcleo WAN ({c_first} a {c_last}):}} {len(core_routers)} roteadores modelo \textit{{{r_model}}} equipados com módulos seriais inteligentes (\texttt{{PT-ROUTER-NM-1SS}}), formando uma topologia de malha completa (\textit{{full-mesh}}) com 6 enlaces seriais ponto a ponto.
  \item \textbf{{Roteadores de Borda ({e_first} a {e_last}):}} {len(edge_routers)} roteadores de borda responsáveis pelo atendimento das LANs departamentais, cada um conectado por enlace serial a um roteador de núcleo específico e por interface GigabitEthernet ao respectivo switch de acesso.
  \item \textbf{{Comutadores de Acesso ({sw_first} a {sw_last}):}} {len(switches)} switches modelo \textit{{{sw_model}}} com portas GigabitEthernet interligando as estações de trabalho e os roteadores de borda.
  \item \textbf{{Estações Finais ({pc_first} a {pc_last}):}} {len(end_hosts)} computadores com conectividade FastEthernet recebendo endereçamento dinâmico via pools DHCP configurados nos roteadores de borda.
\end{{itemize}}

\begin{{figure}}[H]
    \centering
    \includegraphics[width=0.85\linewidth]{{pics/cenario_real.png}}
    \caption{{Topologia física do Cenário {num_str} no Cisco Packet Tracer.}}
    \label{{fig:topologia_real}}
\end{{figure}}

\subsection{{Interfaces e Endereçamento de Roteadores}}

A Tabela~\ref{{tab:ifaces}} detalha a distribuição das {len(parsed_data['router_ifaces'])} interfaces de roteamento ativas, seus endereços IPv4, máscaras e larguras de banda atribuídas aos enlaces.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/ifaces.tex}}
\caption{{Interfaces dos roteadores e enlaces de interconexão.}}
\label{{tab:ifaces}}
\end{{table}}

\subsection{{Portas de Switch e Estações de Trabalho}}

A Tabela~\ref{{tab:switchports}} resume a ocupação de portas nos switches de acesso, e a Tabela~\ref{{tab:pcs}} apresenta as estações de trabalho conectadas a cada equipamento.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/switchports.tex}}
\caption{{Mapeamento de portas dos comutadores.}}
\label{{tab:switchports}}
\end{{table}}

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/pcs.tex}}
\caption{{Estações de trabalho conectadas.}}
\label{{tab:pcs}}
\end{{table}}

\section{{ROTEAMENTO DINÂMICO E TABELA RIB}}

O roteamento da infraestrutura baseia-se exclusivamente no protocolo OSPF processo 1 operando em área única (\textit{{Area 0}}). O custo OSPF dos enlaces seriais é determinado pela relação $\lfloor 10^8 / bw_{{bps}} \rfloor$, resultando no custo métrico padrão de 64 para links seriais T1 (1544 kb/s), e custo 1 para interfaces locais GigabitEthernet. As interfaces LAN dos roteadores de borda são configuradas como \texttt{{passive-interface}} para conter o tráfego de controle desnecessário nas redes de acesso.

\subsection{{Base de Informações de Roteamento (RIB)}}

A seguir são apresentadas as entradas calculadas da RIB esperada para os roteadores da topologia:

\input{{sections/tabelas/rib.tex}}

\subsection{{Configurações dos Roteadores (Running-Configs)}}

A listagem a seguir apresenta as configurações essenciais extraídas diretamente dos dispositivos no arquivo Packet Tracer, compreendendo os endereçamentos, escopos DHCP locais e parâmetros OSPF:

\input{{sections/tabelas/configs.tex}}
""",
                encoding="utf-8",
            )
        else:
            vlan_sec_tex = ""
            if has_custom_vlans and (sec_dir / "tabelas" / "vlans.tex").exists():
                vlan_sec_tex = rf"""
\subsection{{Segmentação em VLANs e Enlaces Trunk}}

A Tabela~\ref{{tab:vlans}} apresenta o mapeamento das redes locais virtuais (VLANs) configuradas nos comutadores e a respectiva atribuição de portas de acesso.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/vlans.tex}}
\caption{{VLANs configuradas e portas de acesso por comutador.}}
\label{{tab:vlans}}
\end{{table}}
"""
            body_tex.write_text(
                rf"""\section{{ARQUITETURA DA INFRAESTRUTURA}}

\subsection{{Topologia Física e Lógica}}

A infraestrutura analisada conta com {len(parsed_data['devices'])} dispositivos ativos interconectados através de {len(parsed_data['links'])} enlaces:
\begin{{itemize}}[leftmargin=2em]
  \item \textbf{{Camada de Roteamento:}} {len(routers)} roteador(es) responsáveis pelo encaminhamento entre as {len(parsed_data['subnets'])} sub-redes IPv4 configuradas.
  \item \textbf{{Camada de Comutação:}} {len(switches)} switch(es) provendo conectividade de enlace e segmentação de domínios.
  \item \textbf{{Dispositivos Finais (Hosts):}} {len(end_hosts)} equipamentos terminais distribuídos nos segmentos de rede local.
\end{{itemize}}

\begin{{figure}}[H]
    \centering
    \includegraphics[width=0.85\linewidth]{{pics/cenario_real.png}}
    \caption{{Topologia física do Cenário {num_str} no Cisco Packet Tracer.}}
    \label{{fig:topologia_real}}
\end{{figure}}

\subsection{{Interfaces e Endereçamento de Roteadores}}

A Tabela~\ref{{tab:ifaces}} detalha as {len(parsed_data['router_ifaces'])} interfaces de roteamento e subinterfaces ativas na topologia.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/ifaces.tex}}
\caption{{Interfaces de camada 3 e enlaces de interconexão.}}
\label{{tab:ifaces}}
\end{{table}}

\subsection{{Portas de Switch e Dispositivos Finais}}

A Tabela~\ref{{tab:switchports}} resume a ocupação de portas nos comutadores e a Tabela~\ref{{tab:pcs}} lista os dispositivos finais conectados.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/switchports.tex}}
\caption{{Mapeamento de portas dos comutadores.}}
\label{{tab:switchports}}
\end{{table}}

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/pcs.tex}}
\caption{{Dispositivos finais conectados à infraestrutura.}}
\label{{tab:pcs}}
\end{{table}}
{vlan_sec_tex}
\section{{ENCAMINHAMENTO, TABELA RIB E CONFIGURAÇÕES}}

Protocolos e mecanismos de rede identificados na auditoria da topologia: \textbf{{{protos}}}.

\subsection{{Base de Informações de Roteamento (RIB)}}

\input{{sections/tabelas/rib.tex}}

\subsection{{Configurações Essenciais dos Ativos (Running-Configs)}}

\input{{sections/tabelas/configs.tex}}
""",
                encoding="utf-8",
            )

    # 4. README.md do cenário
    readme_cenario = cenario_dir / "README.md"
    if is_core_edge_ospf:
        c_first, c_last = core_routers[0]["hostname"], core_routers[-1]["hostname"]
        e_first, e_last = edge_routers[0]["hostname"], edge_routers[-1]["hostname"]
        sw_first, sw_last = switches[0]["name"], switches[-1]["name"]
        serial_links = sum(1 for l in parsed_data["links"] if l.get("cable_type") == "Serial")
        eth_links = len(parsed_data["links"]) - serial_links
        lan_subs = sum(1 for s in parsed_data["subnets"] if s.endswith("/24"))
        wan_subs = len(parsed_data["subnets"]) - lan_subs
        readme_cenario.write_text(
            f"""# Cenário {num_str} — Topologia Distribuída, Roteamento OSPF e RIB

## 🎯 Objetivo
Análise e auditoria completa de infraestrutura de rede distribuída com núcleo WAN em malha completa (*full-mesh* com OSPF área 0 entre os roteadores de núcleo {c_first}–{c_last}), roteadores de borda ({e_first}–{e_last}) atendendo quatro redes locais (LANs), cálculo de métricas de custos e tabela esperada de roteamento (RIB).

---

## ✉️ Modelo de E-mail para Envio da Atividade

- **Título (Assunto):** `Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos`
- **Arquivo a anexar (Ficheiro):** `cenario_{num_str}_equipe_08_Lab_SD.zip` (em `entregas/`)

```text
Assunto: Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos
Anexo: cenario_{num_str}_equipe_08_Lab_SD.zip

Bom dia professor, segue em anexo a {ord_extenso_f} atividade cenario_{num_str}_equipe_08_Lab_SD.zip

Discentes: 
- Júlio Costa Oliveira
- Luiz Gabriel Santos Moreira
```

---

## 📊 Resumo da Topologia
- **Roteadores**: {len(routers)} ({len(core_routers)} de núcleo {c_first}–{c_last} em malha completa, {len(edge_routers)} de borda {e_first}–{e_last})
- **Switches de Acesso**: {len(switches)} ({sw_first} a {sw_last})
- **Estações de Trabalho**: {len(end_hosts)} PCs
- **Enlaces**: {len(parsed_data['links'])} ({serial_links} seriais WAN + {eth_links} Ethernet LAN)
- **Sub-redes**: {len(parsed_data['subnets'])} ({lan_subs} LANs `/24` + {wan_subs} enlaces seriais `/16`)
- **Protocolo de Roteamento**: OSPF Processo 1, Área única 0

---

## 📂 Estrutura de Arquivos

- **`packet_tracer/`**:
  - Diretório reservado para os arquivos `cenario_{num_str}_equipe_08_Lab_SD.pkt` e `cenario_{num_str}_equipe_08_Lab_SD.xml`.
- **`relatorio/`**:
  - `main.tex`: Documento principal em LaTeX com capa padrão da UFPA ({ord_simbolo} Relatório) e dados dos discentes.
  - `pics/`: Brasão `Logo_UFPA.png` e diagramas da rede (`cenario_ideal.png`, `cenario_real.png`).
  - `sections/`: Seções modulares (`introduction.tex`, `body.tex`, `references.tex`, `references.bib`, etc.).
  - `sections/tabelas/`: Módulos de tabelas (`ifaces.tex`, `switchports.tex`, `pcs.tex`, `rib.tex`, etc.).
  - `template/sbc.bst`: Arquivo de estilo bibliográfico da SBC.
- **`analise/`**:
  - `relatorio_cenario{num_int}_equipe8_lab_SD.md`: Documentação técnica gerada a partir dos dados do Packet Tracer.
  - `relatorio_cenario{num_int}_equipe8_lab_SD.html`: Versão visual em HTML dos dados e tabelas.
- **`entregas/`**:
  - `cenario_{num_str}_equipe_08_Lab_SD.pdf`: Relatório final compilado.
  - `cenario_{num_str}_equipe_08_Lab_SD.zip`: Pacote oficial de submissão (PDF + PKT).
""",
            encoding="utf-8",
        )
    else:
        readme_cenario.write_text(
            f"""# Cenário {num_str} — Topologia Distribuída ({protos})

## 🎯 Objetivo
Análise, configuração e auditoria completa da topologia de rede do Cenário {num_str} do Laboratório de Sistemas Distribuídos, composta por {len(routers)} roteador(es), {len(switches)} switch(es), {len(end_hosts)} dispositivos finais e {len(parsed_data['subnets'])} sub-redes IPv4.

---

## ✉️ Modelo de E-mail para Envio da Atividade

- **Título (Assunto):** `Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos`
- **Arquivo a anexar (Ficheiro):** `cenario_{num_str}_equipe_08_Lab_SD.zip` (em `entregas/`)

```text
Assunto: Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos
Anexo: cenario_{num_str}_equipe_08_Lab_SD.zip

Bom dia professor, segue em anexo a {ord_extenso_f} atividade cenario_{num_str}_equipe_08_Lab_SD.zip

Discentes: 
- Júlio Costa Oliveira
- Luiz Gabriel Santos Moreira
```

---

## 📊 Resumo da Topologia
- **Roteadores**: {len(routers)}
- **Switches**: {len(switches)}
- **Dispositivos Finais (Hosts)**: {len(end_hosts)}
- **Enlaces**: {len(parsed_data['links'])}
- **Sub-redes IPv4**: {len(parsed_data['subnets'])}
- **Protocolos / Recursos Ativos**: {protos}

---

## 📂 Estrutura de Arquivos

- **`packet_tracer/`**:
  - `cenario_{num_str}_equipe_08_Lab_SD.pkt` e `cenario_{num_str}_equipe_08_Lab_SD.xml`
- **`relatorio/`**:
  - `main.tex`: Documento principal em LaTeX ({ord_simbolo} Relatório) com capa da UFPA e dados dos discentes.
  - `pics/`: `Logo_UFPA.png` e diagramas da topologia (`cenario_real.png`).
  - `sections/`: Seções modulares (`introduction.tex`, `body.tex`, `references.tex`, `tabelas/`).
  - `template/sbc.bst`: Estilo bibliográfico da SBC.
- **`analise/`**:
  - `relatorio_cenario{num_int}_equipe8_lab_SD.md` e `.html`
- **`entregas/`**:
  - `cenario_{num_str}_equipe_08_Lab_SD.pdf`: Relatório final compilado.
  - `cenario_{num_str}_equipe_08_Lab_SD.zip`: Pacote oficial de submissão (PDF + PKT).
""",
            encoding="utf-8",
        )


def normalize_extracted_table_tex(tex_path: Path):
    """Se um arquivo ifaces.tex, switchports.tex ou pcs.tex do pacote vier sem \\begin{tabular}, encapsula."""
    txt = tex_path.read_text(encoding="utf-8").strip()
    if r"\begin{tabular}" in txt or r"\begin{longtable}" in txt or r"\subsection" in txt:
        return
    headers = {
        "ifaces.tex": ("llllll", r"Roteador & Interface & IP & Prefixo & Banda & Clock/Tipo\\"),
        "switchports.tex": ("llll", r"Switch & Porta & Banda & Conectado a\\"),
        "pcs.tex": ("ll", r"PC & Conectado ao Switch\\"),
    }
    if tex_path.name in headers:
        cols, hdr = headers[tex_path.name]
        wrapped = f"\\begin{{tabular}}{{{cols}}}\n\\toprule\n{hdr}\n\\midrule\n{txt}\n\\bottomrule\n\\end{{tabular}}\n"
        tex_path.write_text(wrapped, encoding="utf-8")


def fallback_parsed_data_from_archive(tab_dir: Path, analise_dir: Path) -> dict:
    """Reconstrói metadados dinamicamente a partir das tabelas/markdown extraídos caso o .pkt/.xml não esteja presente."""
    data = {
        "version": "9.0.1",
        "devices": [],
        "links": [],
        "router_ifaces": [],
        "switch_ports": [],
        "pcs": [],
        "subnets": [],
        "protocols": [],
        "rib": {},
    }
    # Tentar extrair de ifaces.tex, switchports.tex e pcs.tex
    ifaces_f = tab_dir / "ifaces.tex"
    routers_map = {}
    subnets_set = set()
    serial_count = 0
    if ifaces_f.exists():
        for line in ifaces_f.read_text(encoding="utf-8").splitlines():
            if "&" not in line or "Roteador" in line:
                continue
            parts = [p.strip().replace(r"\_", "_").replace(r"\\", "") for p in line.split("&")]
            if len(parts) >= 4:
                rhost, ifn, ip_s, pfx = parts[0], parts[1], parts[2], parts[3]
                data["router_ifaces"].append({"hostname": rhost, "iface": ifn, "ip": ip_s, "prefix": pfx})
                routers_map.setdefault(rhost, {})[ifn if not ifn.startswith("Se") else f"Serial{ifn[2:]}"] = {"ip": ip_s}
                if ifn.startswith("Se"):
                    serial_count += 1
                try:
                    plen = pfx.lstrip("/")
                    subnets_set.add(str(ipaddress.IPv4Network(f"{ip_s}/{plen}", strict=False)))
                except Exception:
                    pass

    for idx, (rhost, ifmap) in enumerate(sorted(routers_map.items(), key=lambda x: natural_key(x[0]))):
        data["devices"].append(
            {"name": f"Router{idx}", "type": "Router", "hostname": rhost, "model": "Router-PT-Empty", "config": {"interfaces": ifmap, "vlans": {}}}
        )

    sw_f = tab_dir / "switchports.tex"
    sw_names = set()
    eth_links = 0
    if sw_f.exists():
        for line in sw_f.read_text(encoding="utf-8").splitlines():
            if "&" not in line or "Switch" in line:
                continue
            parts = [p.strip().replace(r"\_", "_").replace(r"\\", "") for p in line.split("&")]
            if len(parts) >= 2:
                sw_names.add(parts[0])
                eth_links += 1
    for swn in sorted(sw_names, key=natural_key):
        data["devices"].append({"name": swn, "type": "Switch", "hostname": "Switch", "model": "Switch-PT-Empty", "config": {"interfaces": {}, "vlans": {}}})

    pcs_f = tab_dir / "pcs.tex"
    if pcs_f.exists():
        for line in pcs_f.read_text(encoding="utf-8").splitlines():
            if "&" not in line or "Conectado" in line:
                continue
            parts = [p.strip().replace(r"\_", "_").replace(r"\\", "") for p in line.split("&")]
            if len(parts) >= 2:
                data["devices"].append({"name": parts[0], "type": "Pc", "hostname": parts[0], "model": "PC-PT", "config": {"interfaces": {}, "vlans": {}}})

    data["links"] = [{"cable_type": "Serial"}] * (serial_count // 2) + [{"cable_type": "Direto"}] * eth_links
    data["subnets"] = sorted(subnets_set, key=lambda s: ipaddress.IPv4Network(s).network_address)
    rib_f = tab_dir / "rib.tex"
    if rib_f.exists():
        rib_txt = rib_f.read_text(encoding="utf-8")
        if " & O & " in rib_txt:
            data["protocols"].append("OSPF")
        if " & D & " in rib_txt:
            data["protocols"].append("EIGRP")
        if " & R & " in rib_txt:
            data["protocols"].append("RIP")
        if " & S & " in rib_txt:
            data["protocols"].append("Rotas Estáticas")
    return data


def compile_and_package(cenario_dir: Path, num_str: str) -> bool:
    rel_dir = cenario_dir / "relatorio"
    entregas_dir = cenario_dir / "entregas"
    pt_dir = cenario_dir / "packet_tracer"
    entregas_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Compilando LaTeX em {rel_dir} (2 passadas pdflatex)...")
    for pass_num in (1, 2):
        res = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=rel_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if res.returncode != 0:
            print(f"[!] Erro na passada {pass_num} do pdflatex:")
            print("\n".join(res.stdout.splitlines()[-30:]))
            return False

    pdf_built = rel_dir / "main.pdf"
    target_pdf = entregas_dir / f"cenario_{num_str}_equipe_08_Lab_SD.pdf"
    shutil.copy2(pdf_built, target_pdf)

    for ext in ("aux", "log", "out", "toc", "fls", "fdb_latexmk", "pdf"):
        p = rel_dir / f"main.{ext}"
        if p.exists():
            p.unlink()

    print(f"[+] PDF compilado com sucesso: {target_pdf} ({target_pdf.stat().st_size:,} bytes)")

    pkt_file = pt_dir / f"cenario_{num_str}_equipe_08_Lab_SD.pkt"
    zip_target = entregas_dir / f"cenario_{num_str}_equipe_08_Lab_SD.zip"
    if pkt_file.exists():
        with zipfile.ZipFile(zip_target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(target_pdf, arcname=target_pdf.name)
            zf.write(pkt_file, arcname=pkt_file.name)
        print(f"[+] Pacote de entrega gerado: {zip_target}")
        with zipfile.ZipFile(zip_target, "r") as zf:
            for info in zf.infolist():
                print(f"    - {info.filename} ({info.file_size:,} bytes)")
    else:
        print(
            f"[!] AVISO: O arquivo {pkt_file} ainda não foi adicionado. "
            f"Adicione o .pkt em {pt_dir} e rode novamente com --package para gerar o .zip!"
        )
    return True


def main():
    parser = argparse.ArgumentParser(description="Motor de automação da skill novo-cenario-sd.")
    parser.add_argument("--cenario", required=True, help="Número do cenário (ex: 03 ou 3)")
    parser.add_argument("--archive", help="Caminho opcional do arquivo em archives/")
    parser.add_argument("--audit-only", action="store_true", help="Apenas audita o XML existente e exibe resumo")
    parser.add_argument("--package", action="store_true", help="Compila o PDF LaTeX e empacota o .zip de entrega")
    parser.add_argument("--force-skeleton", action="store_true", help="Sobrescreve main.tex, introduction.tex e body.tex")
    args = parser.parse_args()

    num_int = int(re.sub(r"\D", "", args.cenario))
    num_str = f"{num_int:02d}"

    repo_root = Path(__file__).resolve().parents[4]
    cenario_dir = repo_root / f"cenario_{num_str}"
    pt_dir = cenario_dir / "packet_tracer"
    rel_dir = cenario_dir / "relatorio"
    pics_dir = rel_dir / "pics"
    sec_dir = rel_dir / "sections"
    tab_dir = sec_dir / "tabelas"
    tpl_dir = rel_dir / "template"
    analise_dir = cenario_dir / "analise"
    entregas_dir = cenario_dir / "entregas"

    xml_target = pt_dir / f"cenario_{num_str}_equipe_08_Lab_SD.xml"
    pkt_target = pt_dir / f"cenario_{num_str}_equipe_08_Lab_SD.pkt"

    if args.audit_only:
        if not xml_target.exists():
            print(f"[!] Arquivo XML não encontrado: {xml_target}")
            sys.exit(1)
        data = parse_packet_tracer_xml(xml_target)
        print(f"=== AUDITORIA DO CENÁRIO {num_str} (PT v{data['version']}) ===")
        print(f"Dispositivos totais : {len(data['devices'])}")
        print(f"Enlaces (cabos)     : {len(data['links'])}")
        print(f"Interfaces com IP   : {len(data['router_ifaces'])}")
        print(f"Portas de Switch    : {len(data['switch_ports'])}")
        print(f"Sub-redes IPv4      : {len(data['subnets'])} -> {data['subnets']}")
        print(f"Protocolos ativos   : {data['protocols']}")
        print(f"Roteadores na RIB   : {list(data['rib'].keys())}")
        sys.exit(0)

    if args.package and (rel_dir / "main.tex").exists() and not args.force_skeleton:
        ok = compile_and_package(cenario_dir, num_str)
        sys.exit(0 if ok else 1)

    for d in (pt_dir, pics_dir, tab_dir, tpl_dir, analise_dir, entregas_dir):
        d.mkdir(parents=True, exist_ok=True)

    c1_rel = repo_root / "cenario_01" / "relatorio"
    if (c1_rel / "pics" / "Logo_UFPA.png").exists():
        shutil.copy2(c1_rel / "pics" / "Logo_UFPA.png", pics_dir / "Logo_UFPA.png")
    if (c1_rel / "template" / "sbc.bst").exists():
        shutil.copy2(c1_rel / "template" / "sbc.bst", tpl_dir / "sbc.bst")
    for sfile in ("references.tex", "references.bib", "conclusion.tex", "appendix.tex"):
        src_s = c1_rel / "sections" / sfile
        dst_s = sec_dir / sfile
        if src_s.exists() and not dst_s.exists():
            shutil.copy2(src_s, dst_s)

    archive_paths = [Path(args.archive)] if args.archive else []
    if not archive_paths:
        archives_dir = repo_root / "archives"
        if archives_dir.exists():
            archive_paths = sorted(
                [
                    p
                    for p in archives_dir.iterdir()
                    if p.is_file() and (f"cenario_{num_str}" in p.name.lower() or f"cenario{num_int}" in p.name.lower())
                ]
            )

    known_table_files = {"ifaces.tex", "switchports.tex", "pcs.tex", "rib.tex", "configs.tex", "tabelas_geradas.tex", "vlans.tex"}
    for archive_path in archive_paths:
        if not archive_path.exists():
            continue
        print(f"[*] Processando arquivo de entrada: {archive_path}")
        if archive_path.suffix.lower() == ".pkt":
            shutil.copy2(archive_path, pkt_target)
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                if archive_path.name.endswith((".tar.xz", ".tar.gz", ".tgz", ".tar")):
                    with tarfile.open(archive_path, "r:*") as tf:
                        tf.extractall(tmp_path)
                elif archive_path.suffix.lower() == ".zip":
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extractall(tmp_path)
                for f in tmp_path.rglob("*"):
                    if not f.is_file():
                        continue
                    ext = f.suffix.lower()
                    if ext == ".pkt":
                        shutil.copy2(f, pkt_target)
                    elif ext == ".xml" and not pkt_target.exists():
                        shutil.copy2(f, xml_target)
                    elif ext in (".png", ".jpg", ".jpeg") and f.name != "Logo_UFPA.png":
                        shutil.copy2(f, pics_dir / f.name)
                        if not (pics_dir / "cenario_real.png").exists():
                            shutil.copy2(f, pics_dir / "cenario_real.png")
                    elif ext in (".md", ".html"):
                        shutil.copy2(f, analise_dir / f.name)
                    elif f.name in known_table_files:
                        dst_t = tab_dir / f.name
                        shutil.copy2(f, dst_t)
                        normalize_extracted_table_tex(dst_t)

    if not pkt_target.exists():
        existing_pkts = [p for p in pt_dir.glob("*.pkt") if p.name != "original.pkt"]
        if existing_pkts:
            existing_pkts[0].rename(pkt_target)

    if pkt_target.exists():
        decrypt_tool = repo_root / "tools" / "decrypt_pkt_9-0-0.py"
        print(f"[*] Decodificando {pkt_target.name} via {decrypt_tool.name}...")
        subprocess.run(["python3", str(decrypt_tool), str(pkt_target)], check=True)

    if xml_target.exists():
        parsed_data = parse_packet_tracer_xml(xml_target)
        print(
            f"[+] XML auditado: {len(parsed_data['devices'])} dispositivos, "
            f"{len(parsed_data['links'])} enlaces, {len(parsed_data['switch_ports'])} portas de switch, "
            f"protocolos={parsed_data['protocols']}"
        )
        write_latex_tables(parsed_data, tab_dir)
        write_analysis_md_and_html(parsed_data, analise_dir, num_int)
        if not (pics_dir / "cenario_real.png").exists():
            ok_img = render_topology_diagram(parsed_data, pics_dir / "cenario_real.png")
            if ok_img:
                print("[+] Diagrama visual gerado automaticamente em relatorio/pics/cenario_real.png.")
        ensure_latex_files_and_readme(parsed_data, cenario_dir, num_int, force_regen=args.force_skeleton)
    else:
        print(f"[!] AVISO: Nenhum arquivo .pkt ou .xml encontrado para o Cenário {num_str}.")
        print("    Montando estrutura LaTeX e README.md a partir dos artefatos do pacote em archives/...")
        parsed_data = fallback_parsed_data_from_archive(tab_dir, analise_dir)
        ensure_latex_files_and_readme(parsed_data, cenario_dir, num_int, force_regen=args.force_skeleton)

    if args.package:
        compile_and_package(cenario_dir, num_str)


if __name__ == "__main__":
    main()
