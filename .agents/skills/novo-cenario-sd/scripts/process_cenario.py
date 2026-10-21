#!/usr/bin/env python3
"""
process_cenario.py — Motor de automação da skill 'novo-cenario-sd'.

Responsável por:
1. Criar a estrutura simétrica de diretórios do cenário (cenario_XX/).
2. Extrair pacotes de archives/ (.tar.xz, .zip, .tar.gz) ou copiar .pkt direto.
3. Padronizar cenario_XX_equipe_08_Lab_SD.pkt e decodificar para .xml.
4. Extrair 100% dos dispositivos, enlaces, IPs, VLANs, DHCP e protocolos do XML.
5. Auditar arquivos pré-existentes contra o XML (fonte da verdade absoluta).
6. Calcular a RIB esperada por menor caminho (Dijkstra com suporte a ECMP).
7. Gerar tabelas LaTeX encapsuladas (ifaces, switchports, pcs, rib, configs, vlans).
8. Renderizar diagrama visual da topologia (cenario_real.png) via PIL caso não haja imagens.
9. Gerar relatórios analíticos (.md e .html), esqueleto LaTeX (main.tex, introduction, body) e README.md com modelo de e-mail.
10. Compilar PDF via pdflatex (2 passadas) e fechar pacote cenario_XX_equipe_08_Lab_SD.zip (--package).
"""

import argparse
import heapq
import html
import ipaddress
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ORDINAIS = {
    1: ("1º", "primeira"),
    2: ("2º", "segunda"),
    3: ("3º", "terceira"),
    4: ("4º", "quarta"),
    5: ("5º", "quinta"),
    6: ("6º", "sexta"),
    7: ("7º", "sétima"),
    8: ("8º", "oitava"),
    9: ("9º", "nona"),
    10: ("10º", "décima"),
}


def mask_to_prefix(mask: str) -> str:
    if not mask or mask == "—":
        return "—"
    try:
        net = ipaddress.IPv4Network(f"0.0.0.0/{mask}", strict=False)
        return f"/{net.prefixlen}"
    except Exception:
        return mask


def ip_to_subnet(ip: str, mask: str) -> str:
    try:
        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
        return str(net)
    except Exception:
        return f"{ip}/{mask}"


def latex_escape(text: str) -> str:
    if not text:
        return "--"
    return (
        text.replace("_", r"\_")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
    )


def parse_running_config(cfg_text: str) -> dict:
    info = {
        "hostname": None,
        "interfaces": {},
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

        # Hostname
        m = re.match(r"^hostname\s+(\S+)", stripped)
        if m:
            info["hostname"] = m.group(1)
            info["essential_lines"].append(line)
            continue

        # Spanning tree
        m = re.match(r"^spanning-tree mode\s+(\S+)", stripped)
        if m:
            info["spanning_tree"] = m.group(1)
            continue

        # DHCP Excluded
        if stripped.startswith("ip dhcp excluded-address"):
            info["dhcp_excluded"].append(stripped)
            info["essential_lines"].append(line)
            continue

        # DHCP Pool
        m = re.match(r"^ip dhcp pool\s+(\S+)", stripped)
        if m:
            current_dhcp = {"name": m.group(1), "network": None, "default_router": None, "dns": None}
            info["dhcp_pools"].append(current_dhcp)
            info["essential_lines"].append(line)
            current_iface = None
            current_router = None
            continue

        if current_dhcp is not None and raw_line.startswith(" "):
            info["essential_lines"].append(line)
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

        # VLAN definition
        m = re.match(r"^vlan\s+(\d+)", stripped)
        if m:
            current_vlan = m.group(1)
            info["vlans"][current_vlan] = f"VLAN{current_vlan}"
            info["essential_lines"].append(line)
            continue
        if current_vlan is not None and raw_line.startswith(" "):
            info["essential_lines"].append(line)
            m_vn = re.match(r"^name\s+(.+)", stripped)
            if m_vn:
                info["vlans"][current_vlan] = m_vn.group(1).strip()
            continue

        # Interface
        m = re.match(r"^interface\s+(\S+)", stripped)
        if m:
            current_iface = m.group(1)
            current_router = None
            info["interfaces"].setdefault(
                current_iface,
                {
                    "ip": None,
                    "mask": None,
                    "clock_rate": None,
                    "description": None,
                    "shutdown": False,
                    "encapsulation": None,
                    "switchport_mode": None,
                    "access_vlan": None,
                },
            )
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
            m_enc = re.match(r"^encapsulation dot1Q\s+(\d+)", stripped, re.I)
            if m_enc:
                ifobj["encapsulation"] = f"dot1Q {m_enc.group(1)}"
            m_swm = re.match(r"^switchport mode\s+(\S+)", stripped)
            if m_swm:
                ifobj["switchport_mode"] = m_swm.group(1)
            m_swa = re.match(r"^switchport access vlan\s+(\d+)", stripped)
            if m_swa:
                ifobj["access_vlan"] = m_swa.group(1)
            if stripped.startswith("ip nat"):
                info["nat"].append(f"{current_iface}: {stripped}")
            continue

        # Routing protocols
        m_ospf = re.match(r"^router ospf\s+(\d+)", stripped)
        if m_ospf:
            current_router = ("ospf", {"process": m_ospf.group(1), "router_id": None, "networks": [], "passives": []})
            info["ospf"].append(current_router[1])
            info["essential_lines"].append(line)
            continue

        if re.match(r"^router rip", stripped):
            current_router = ("rip", {"version": 1, "networks": [], "passives": []})
            info["rip"].append(current_router[1])
            info["essential_lines"].append(line)
            continue

        m_eigrp = re.match(r"^router eigrp\s+(\d+)", stripped)
        if m_eigrp:
            current_router = ("eigrp", {"as": m_eigrp.group(1), "networks": [], "passives": []})
            info["eigrp"].append(current_router[1])
            info["essential_lines"].append(line)
            continue

        if current_router is not None and raw_line.startswith(" "):
            info["essential_lines"].append(line)
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

        # Static route
        m_sr = re.match(r"^ip route\s+([\d\.]+)\s+([\d\.]+)\s+(\S+)", stripped)
        if m_sr:
            info["static_routes"].append((m_sr.group(1), m_sr.group(2), m_sr.group(3)))
            info["essential_lines"].append(line)
            continue

        # ACL / NAT
        if stripped.startswith("access-list") or stripped.startswith("ip access-list"):
            info["acls"].append(stripped)
            info["essential_lines"].append(line)
        elif stripped.startswith("ip nat"):
            info["nat"].append(stripped)
            info["essential_lines"].append(line)

    # Rebuild clean essential lines including only configured interfaces
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
        clean_essential.append(f"vlan {vid}")
        clean_essential.append(f" name {vname}")
    for ifname, ifdata in info["interfaces"].items():
        has_cfg = any(
            ifdata.get(k)
            for k in ("ip", "clock_rate", "description", "encapsulation", "switchport_mode", "access_vlan")
        )
        if has_cfg:
            clean_essential.append(f"interface {ifname}")
            if ifdata["description"]:
                clean_essential.append(f" description {ifdata['description']}")
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
        for net, _, _ in rip["networks"]:
            clean_essential.append(f" network {net}")
    for eigrp in info["eigrp"]:
        clean_essential.append(f"router eigrp {eigrp['as']}")
        for net, wc, _ in eigrp["networks"]:
            clean_essential.append(f" network {net} {wc}".rstrip())
    for dst, msk, nh in info["static_routes"]:
        clean_essential.append(f"ip route {dst} {msk} {nh}")
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
        sys_name = eng.findtext("SYS_NAME") or name
        serial = eng.findtext("SERIALNUMBER") or "—"

        ws_log = d.find("WORKSPACE/LOGICAL")
        x = float(ws_log.findtext("X") or 0.0) if ws_log is not None else 0.0
        y = float(ws_log.findtext("Y") or 0.0) if ws_log is not None else 0.0

        rc_node = eng.find("RUNNINGCONFIG")
        rc_text = ""
        if rc_node is not None:
            rc_lines = [l.text for l in rc_node.findall("LINE") if l.text is not None]
            rc_text = "\n".join(rc_lines)

        parsed_cfg = parse_running_config(rc_text)
        hostname = parsed_cfg["hostname"] or sys_name

        # Ports in XML
        ports = {}
        gw_dev = eng.findtext("DEFAULT_GATEWAY") or "—"
        dns_dev = eng.findtext("DNS_SERVER_IP") or "—"
        for p in eng.findall(".//PORT"):
            pname = p.findtext("NAME")
            if not pname:
                continue
            pip = p.findtext("IP") or p.findtext("IP_ADDRESS") or ""
            pmask = p.findtext("SUBNET") or p.findtext("SUBNET_MASK") or ""
            pbw = p.findtext("BANDWIDTH") or ""
            pclock = p.findtext("CLOCKRATE") or p.findtext("CLOCK_RATE") or ""
            pgw = p.findtext("GATEWAY") or ""
            pdns = p.findtext("DNS_SERVER") or ""
            if pgw and pgw != "0.0.0.0" and gw_dev == "—":
                gw_dev = pgw
            if pdns and pdns != "0.0.0.0" and dns_dev == "—":
                dns_dev = pdns
            ports[pname] = {
                "name": pname,
                "ip": pip if pip != "0.0.0.0" else "",
                "mask": pmask if pmask != "0.0.0.0" else "",
                "bandwidth": pbw,
                "clock_rate": pclock,
            }

        dev_info = {
            "name": name,
            "type": dtype,
            "hostname": hostname,
            "serial": serial,
            "ref_id": ref_id,
            "x": x,
            "y": y,
            "gw": gw_dev,
            "dns": dns_dev,
            "ports": ports,
            "config": parsed_cfg,
        }
        devices.append(dev_info)
        if ref_id:
            id_to_dev[ref_id] = dev_info
        name_to_dev[name] = dev_info

    # Links
    links = []
    port_peer = {}  # (dev_name, port_name) -> (peer_dev_name, peer_port_name, cable_type)
    for l in root.findall(".//NETWORK/LINKS/LINK"):
        cable = l.find("CABLE")
        if cable is None:
            continue
        from_ref = cable.findtext("FROM") or ""
        to_ref = cable.findtext("TO") or ""
        d1 = id_to_dev.get(from_ref, {}).get("name", from_ref)
        d2 = id_to_dev.get(to_ref, {}).get("name", to_ref)
        p_nodes = cable.findall("PORT")
        p1 = p_nodes[0].text if len(p_nodes) > 0 else "?"
        p2 = p_nodes[1].text if len(p_nodes) > 1 else "?"
        ctype = cable.findtext("TYPE") or "Unknown"
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

    # Consolidar interfaces com IP nos roteadores/switches
    router_ifaces = []
    subnets_set = set()
    for d in sorted(devices, key=lambda x: x["name"]):
        if d["type"] not in ("Router", "Switch", "Multilayer Switch"):
            continue
        cfg_ifaces = d["config"]["interfaces"]
        for ifname, ifdata in cfg_ifaces.items():
            ip = ifdata["ip"]
            mask = ifdata["mask"]
            if not ip:
                continue
            subnet = ip_to_subnet(ip, mask)
            subnets_set.add(subnet)
            peer_info = port_peer.get((d["name"], ifname))
            # Para subinterfaces (ex: GigabitEthernet0/0.10), buscar porta física pai
            if not peer_info and "." in ifname:
                parent_port = ifname.split(".")[0]
                peer_info = port_peer.get((d["name"], parent_port))
            peer_str = f"{peer_info[0]} {peer_info[1]}" if peer_info else "—"

            bw_str = "1544 kb/s" if ifname.startswith("Serial") else ("1 Gb/s" if "Gigabit" in ifname else "100 Mb/s")
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
                    "ip": ip,
                    "mask": mask,
                    "prefix": mask_to_prefix(mask),
                    "subnet": subnet,
                    "bw": bw_str,
                    "clock_type": clk_type,
                    "peer": peer_str,
                    "cost_ospf": 64 if ifname.startswith("Serial") else 1,
                }
            )

    # Consolidar portas de Switch
    switch_ports_table = []
    for d in sorted(devices, key=lambda x: x["name"]):
        if "Switch" not in d["type"]:
            continue
        # Descobrir todas as portas físicas Ethernet do switch
        all_pnames = sorted(
            [p for p in d["ports"].keys() if "Ethernet" in p],
            key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)],
        )
        for pname in all_pnames:
            short_p = pname.replace("GigabitEthernet", "Gi").replace("FastEthernet", "Fa")
            peer = port_peer.get((d["name"], pname))
            if peer:
                peer_dev_obj = name_to_dev.get(peer[0], {})
                peer_label = peer_dev_obj.get("hostname") if peer_dev_obj.get("type") == "Router" else peer[0]
                conn_str = f"{peer_label} {peer[1]}"
                bw_str = "100 Mb/s" if "FastEthernet" in pname or "FastEthernet" in peer[1] else "1 Gb/s"
            else:
                conn_str = "livre"
                bw_str = "1 Gb/s" if "Gigabit" in pname else "100 Mb/s"

            cfg_if = d["config"]["interfaces"].get(pname, {})
            mode = cfg_if.get("switchport_mode") or "access"
            vlan = cfg_if.get("access_vlan") or "1"

            switch_ports_table.append(
                {
                    "switch": d["name"],
                    "port": short_p,
                    "full_port": pname,
                    "bw": bw_str,
                    "connected_to": conn_str,
                    "mode": mode,
                    "vlan": vlan,
                }
            )

    # Consolidar PCs
    pcs_table = []
    for d in sorted(devices, key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", x["name"])]):
        if d["type"] != "Pc":
            continue
        peer = port_peer.get((d["name"], "FastEthernet0"))
        if peer:
            short_sp = peer[1].replace("GigabitEthernet", "Gi").replace("FastEthernet", "Fa")
            conn_sw = f"{peer[0]} {short_sp}"
        else:
            conn_sw = "—"
        pcs_table.append(
            {
                "pc": d["name"],
                "connected_to": conn_sw,
                "gw": d["gw"],
                "dns": d["dns"],
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
        if cfg["vlans"] or any(i.get("encapsulation") or i.get("access_vlan") for i in cfg["interfaces"].values()):
            protocols_detected.add("VLAN")
        if cfg["acls"]:
            protocols_detected.add("ACL")
        if cfg["nat"]:
            protocols_detected.add("NAT")

    # Calcular RIB esperada por Dijkstra para os roteadores
    rib_by_router = compute_expected_rib(devices, router_ifaces, sorted(subnets_set))

    return {
        "version": version,
        "devices": devices,
        "links": links,
        "router_ifaces": router_ifaces,
        "switch_ports": switch_ports_table,
        "pcs": pcs_table,
        "subnets": sorted(subnets_set),
        "protocols": sorted(protocols_detected),
        "rib": rib_by_router,
    }


def compute_expected_rib(devices: list, router_ifaces: list, all_subnets: list) -> dict:
    routers = [d for d in devices if d["type"] == "Router"]
    if not routers:
        return {}

    # Mapear sub-rede -> lista de (router_name, hostname, iface, ip, cost)
    subnet_attachments = {}
    router_hostname = {r["name"]: r["hostname"] for r in routers}
    for rif in router_ifaces:
        if rif["dev_name"] not in router_hostname:
            continue
        subnet_attachments.setdefault(rif["subnet"], []).append(rif)

    # Grafo de adjacência entre roteadores: u -> list of (v, out_iface_u, next_hop_ip_v, link_cost)
    adj = {r["name"]: [] for r in routers}
    for sub, rifs in subnet_attachments.items():
        if len(rifs) >= 2:
            for a in rifs:
                for b in rifs:
                    if a["dev_name"] != b["dev_name"]:
                        adj[a["dev_name"]].append((b["dev_name"], a["iface"], b["ip"], a["cost_ospf"]))

    rib_result = {}
    for r in sorted(routers, key=lambda x: x["name"]):
        rname = r["name"]
        # Dijkstra com suporte a múltiplos primeiros saltos de custo mínimo (ECMP)
        dist = {rn: float("inf") for rn in adj}
        first_hops = {rn: set() for rn in adj}  # set of (out_iface, next_hop_ip)
        dist[rname] = 0
        pq = [(0, rname)]

        while pq:
            d_u, u = heapq.heappop(pq)
            if d_u > dist[u]:
                continue
            for v, out_if, nh_ip, w in adj[u]:
                new_cost = d_u + w
                hops_to_v = {(out_if, nh_ip)} if u == rname else first_hops[u]
                if new_cost < dist[v]:
                    dist[v] = new_cost
                    first_hops[v] = set(hops_to_v)
                    heapq.heappush(pq, (new_cost, v))
                elif new_cost == dist[v]:
                    first_hops[v].update(hops_to_v)

        entries = []
        for sub in sorted(all_subnets, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]):
            rifs_on_sub = subnet_attachments.get(sub, [])
            # Verificar se é diretamente conectada a rname
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
            else:
                # Menor custo até qualquer roteador conectado a sub
                best_cost = float("inf")
                best_hops = set()
                for owner in rifs_on_sub:
                    owner_name = owner["dev_name"]
                    if dist.get(owner_name, float("inf")) < float("inf"):
                        total_c = dist[owner_name] + owner["cost_ospf"]
                        if total_c < best_cost:
                            best_cost = total_c
                            best_hops = set(first_hops[owner_name])
                        elif total_c == best_cost:
                            best_hops.update(first_hops[owner_name])
                if best_cost < float("inf"):
                    sorted_hops = sorted(best_hops)
                    out_ifs = ", ".join(dict.fromkeys(h[0] for h in sorted_hops))
                    nh_ips = ", ".join(dict.fromkeys(h[1] for h in sorted_hops))
                    entries.append(
                        {
                            "subnet": sub,
                            "code": "O",
                            "out_ifaces": out_ifs,
                            "metric": str(best_cost),
                            "next_hops": nh_ips,
                        }
                    )
        rib_result[f"{r['hostname']} ({rname})"] = entries

    return rib_result


def render_topology_diagram(parsed_data: dict, output_png: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    # Filtrar dispositivos que têm enlaces ou são roteadores/switches/pcs ativos
    connected_names = set()
    for l in parsed_data["links"]:
        connected_names.add(l["from_dev"])
        connected_names.add(l["to_dev"])

    devs = [d for d in parsed_data["devices"] if d["name"] in connected_names or d["type"] in ("Router", "Switch", "Pc")]
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

    # Desenhar enlaces
    for l in parsed_data["links"]:
        p1 = dev_pos.get(l["from_dev"])
        p2 = dev_pos.get(l["to_dev"])
        if not p1 or not p2:
            continue
        is_serial = "Serial" in l["from_port"] or "Serial" in l["to_port"]
        color = (200, 40, 40) if is_serial else (60, 60, 60)
        draw.line([p1, p2], fill=color, width=3 if is_serial else 2)

    # Desenhar nós
    for d in devs:
        cx, cy = dev_pos[d["name"]]
        dtype = d["type"]
        label = f"{d['hostname']}" if d["hostname"] != d["name"] and dtype == "Router" else d["name"]
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


def write_latex_tables(parsed_data: dict, tabelas_dir: Path) -> list:
    tabelas_dir.mkdir(parents=True, exist_ok=True)
    audit_notes = []

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
    (tabelas_dir / "rib.tex").write_text("\n".join(rib_lines) + "\n", encoding="utf-8")

    # 5. configs.tex
    cfg_lines = []
    for d in sorted(parsed_data["devices"], key=lambda x: x["name"]):
        if d["type"] != "Router" or not d["config"]["essential_lines"]:
            continue
        cfg_lines.append(f"\\subsection*{{{latex_escape(d['name'])}}}")
        cfg_lines.append(r"\begin{lstlisting}")
        cfg_lines.extend(d["config"]["essential_lines"])
        cfg_lines.append(r"\end{lstlisting}")
    (tabelas_dir / "configs.tex").write_text("\n".join(cfg_lines) + "\n", encoding="utf-8")

    return audit_notes


def write_analysis_md_and_html(parsed_data: dict, analise_dir: Path, num_int: int):
    analise_dir.mkdir(parents=True, exist_ok=True)
    routers = [d for d in parsed_data["devices"] if d["type"] == "Router"]
    switches = [d for d in parsed_data["devices"] if "Switch" in d["type"]]
    pcs = [d for d in parsed_data["devices"] if d["type"] == "Pc"]

    md = [
        f"# Relatório de Rede — cenario_{num_int:02d}_equipe_08_Lab_SD",
        "",
        f"Origem: `cenario_{num_int:02d}_equipe_08_Lab_SD.xml` · Packet Tracer {parsed_data['version']}",
        "",
        "### Resumo",
        "",
        "| Item | Quantidade / Detalhe |",
        "|---|---|",
        f"| Versão do Packet Tracer | {parsed_data['version']} |",
        f"| Roteador(es) | {len(routers)} |",
        f"| Switch(es) | {len(switches)} |",
        f"| PC(s) | {len(pcs)} |",
        f"| Enlaces (cabos) | {len(parsed_data['links'])} |",
        f"| Sub-redes IPv4 distintas | {len(parsed_data['subnets'])} |",
        f"| Interfaces com IP | {len(parsed_data['router_ifaces'])} |",
        f"| Protocolos Detectados | {', '.join(parsed_data['protocols']) or 'Nenhum'} |",
        "",
        "### Interfaces de Roteadores",
        "",
        "| Dispositivo | Hostname | Interface | IP | Máscara | Prefixo | Banda | Conectado a |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for rif in parsed_data["router_ifaces"]:
        md.append(
            f"| {rif['dev_name']} | {rif['hostname']} | {rif['iface']} | {rif['ip']} | "
            f"{rif['mask']} | {rif['prefix']} | {rif['bw']} | {rif['peer']} |"
        )

    md_text = "\n".join(md) + "\n"
    md_file = analise_dir / f"relatorio_cenario{num_int}_equipe8_lab_SD.md"
    md_file.write_text(md_text, encoding="utf-8")

    html_file = analise_dir / f"relatorio_cenario{num_int}_equipe8_lab_SD.html"
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Relatório Cenário {num_int:02d} — Equipe 08</title>
<style>body{{font-family:sans-serif;margin:2rem;}} pre{{background:#f4f4f4;padding:1rem;}}</style>
</head>
<body><pre>{html.escape(md_text)}</pre></body></html>
"""
    html_file.write_text(html_content, encoding="utf-8")


def ensure_latex_files_and_readme(parsed_data: dict, cenario_dir: Path, num_int: int, force_regen: bool = False):
    num_str = f"{num_int:02d}"
    ord_simbolo, ord_extenso = ORDINAIS.get(num_int, (f"{num_int}º", f"{num_int}ª"))
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

    routers = [d for d in parsed_data["devices"] if d["type"] == "Router"]
    switches = [d for d in parsed_data["devices"] if "Switch" in d["type"]]
    pcs = [d for d in parsed_data["devices"] if d["type"] == "Pc"]
    protos = ", ".join(parsed_data["protocols"]) if parsed_data["protocols"] else "roteamento e comutação"

    # 2. introduction.tex
    intro_tex = sec_dir / "introduction.tex"
    if not intro_tex.exists() or force_regen:
        intro_tex.write_text(
            rf"""\section{{INTRODUÇÃO}}

Este relatório apresenta a análise e documentação técnica da arquitetura de rede do Cenário {num_str} do Laboratório de Sistemas Distribuídos, implementada e simulada no Cisco Packet Tracer (v{parsed_data['version']}). A topologia exercita conceitos de {protos}, interconectando {len(routers)} roteadores, {len(switches)} switches e {len(pcs)} estações finais através de {len(parsed_data['links'])} enlaces físicos.

\subsection{{Contextualização e Visão Geral da Topologia}}

O experimento avalia a configuração de camadas física, de enlace e de rede, verificando a atribuição de endereçamento IPv4 em {len(parsed_data['subnets'])} sub-redes distintas, o comportamento do encaminhamento de pacotes e a consistência das tabelas de roteamento (RIB) e políticas de serviços configuradas nos ativos de rede.
""",
            encoding="utf-8",
        )

    # 3. body.tex
    body_tex = sec_dir / "body.tex"
    if not body_tex.exists() or force_regen:
        body_tex.write_text(
            rf"""\section{{ARQUITETURA DA INFRAESTRUTURA}}

\subsection{{Topologia Física e Lógica}}

A infraestrutura analisada conta com {len(parsed_data['devices'])} dispositivos totais e {len(parsed_data['links'])} enlaces ativos:
\begin{{itemize}}[leftmargin=2em]
  \item \textbf{{Roteadores:}} {len(routers)} equipamentos responsáveis pelo encaminhamento entre as {len(parsed_data['subnets'])} sub-redes IPv4.
  \item \textbf{{Comutadores de Acesso:}} {len(switches)} switches provendo conectividade de camada 2.
  \item \textbf{{Estações Finais:}} {len(pcs)} computadores distribuídos nas redes locais.
\end{{itemize}}

\begin{{figure}}[H]
    \centering
    \includegraphics[width=0.85\linewidth]{{pics/cenario_real.png}}
    \caption{{Topologia do Cenário {num_str} no Cisco Packet Tracer.}}
    \label{{fig:topologia_real}}
\end{{figure}}

\subsection{{Interfaces e Endereçamento de Roteadores}}

A Tabela~\ref{{tab:ifaces}} detalha as {len(parsed_data['router_ifaces'])} interfaces de roteamento configuradas na topologia.

\begin{{table}}[H]
\centering
\small
\input{{sections/tabelas/ifaces.tex}}
\caption{{Interfaces dos roteadores e enlaces de interconexão.}}
\label{{tab:ifaces}}
\end{{table}}

\subsection{{Portas de Switch e Estações de Trabalho}}

A Tabela~\ref{{tab:switchports}} resume a ocupação de portas nos switches e a Tabela~\ref{{tab:pcs}} lista as estações de trabalho conectadas.

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

\section{{ROTEAMENTO E CONFIGURAÇÕES ATIVAS}}

Protocolos e serviços detectados na auditoria da topologia: \textbf{{{protos}}}.

\subsection{{Base de Informações de Roteamento (RIB)}}

\input{{sections/tabelas/rib.tex}}

\subsection{{Configurações dos Roteadores (Running-Configs)}}

\input{{sections/tabelas/configs.tex}}
""",
            encoding="utf-8",
        )

    # 4. README.md do cenário
    readme_cenario = cenario_dir / "README.md"
    readme_cenario.write_text(
        f"""# Cenário {num_str} — Topologia Distribuída ({protos})

## 🎯 Objetivo
Análise, configuração e auditoria completa da topologia de rede do Cenário {num_str} do Laboratório de Sistemas Distribuídos, composta por {len(routers)} roteadores, {len(switches)} switches, {len(pcs)} PCs e {len(parsed_data['subnets'])} sub-redes IPv4.

---

## ✉️ Modelo de E-mail para Envio da Atividade

- **Título (Assunto):** `Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos`
- **Arquivo a anexar (Ficheiro):** `cenario_{num_str}_equipe_08_Lab_SD.zip` (em `entregas/`)

```text
Assunto: Cenário {num_str} - equipe 08 - Laboratório de Sistemas Distribuidos
Anexo: cenario_{num_str}_equipe_08_Lab_SD.zip

Bom dia professor, segue em anexo a {ord_extenso} atividade cenario_{num_str}_equipe_08_Lab_SD.zip

Discentes: 
- Júlio Costa Oliveira
- Luiz Gabriel Santos Moreira
```

---

## 📊 Resumo da Topologia
- **Roteadores**: {len(routers)}
- **Switches**: {len(switches)}
- **Estações de Trabalho**: {len(pcs)} PCs
- **Enlaces**: {len(parsed_data['links'])}
- **Sub-redes IPv4**: {len(parsed_data['subnets'])}
- **Protocolos Ativos**: {protos}

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

    # Limpar temporários de build
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
        print(f"Sub-redes IPv4      : {len(data['subnets'])} -> {data['subnets']}")
        print(f"Protocolos ativos   : {data['protocols']}")
        print(f"Roteadores na RIB   : {list(data['rib'].keys())}")
        sys.exit(0)

    # Se for apenas --package e o relatório já estiver montado
    if args.package and (rel_dir / "main.tex").exists():
        ok = compile_and_package(cenario_dir, num_str)
        sys.exit(0 if ok else 1)

    # Criar árvore de diretórios
    for d in (pt_dir, pics_dir, tab_dir, tpl_dir, analise_dir, entregas_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Copiar assets base do cenario_01
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

    # Descobrir arquivo em archives/
    archive_path = Path(args.archive) if args.archive else None
    if not archive_path:
        archives_dir = repo_root / "archives"
        candidates = sorted(
            [
                p
                for p in archives_dir.iterdir()
                if p.is_file() and (f"cenario_{num_str}" in p.name.lower() or f"cenario{num_int}" in p.name.lower())
            ]
        )
        if candidates:
            archive_path = candidates[-1]

    if archive_path and archive_path.exists():
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

    # Procurar .pkt já solto em packet_tracer/
    if not pkt_target.exists():
        existing_pkts = [p for p in pt_dir.glob("*.pkt") if p.name != "original.pkt"]
        if existing_pkts:
            existing_pkts[0].rename(pkt_target)

    # Decodificar .pkt -> .xml
    if pkt_target.exists():
        decrypt_tool = repo_root / "tools" / "decrypt_pkt_9-0-0.py"
        print(f"[*] Decodificando {pkt_target.name} via {decrypt_tool.name}...")
        subprocess.run(["python3", str(decrypt_tool), str(pkt_target)], check=True)

    if not xml_target.exists():
        print(f"[!] AVISO: Nenhum arquivo .pkt ou .xml encontrado para o Cenário {num_str}.")
        print(f"    Coloque o arquivo .pkt em {pt_dir}/cenario_{num_str}_equipe_08_Lab_SD.pkt e execute novamente.")
        sys.exit(0)

    # Extrair dados do XML e gerar tudo
    parsed_data = parse_packet_tracer_xml(xml_target)
    print(
        f"[+] XML auditado: {len(parsed_data['devices'])} dispositivos, "
        f"{len(parsed_data['links'])} enlaces, protocolos={parsed_data['protocols']}"
    )

    write_latex_tables(parsed_data, tab_dir)
    write_analysis_md_and_html(parsed_data, analise_dir, num_int)

    # Diagrama de topologia fallback caso nenhuma imagem exista
    if not (pics_dir / "cenario_real.png").exists():
        ok_img = render_topology_diagram(parsed_data, pics_dir / "cenario_real.png")
        if ok_img:
            print(
                "[+] Diagrama visual gerado automaticamente em relatorio/pics/cenario_real.png "
                "(você pode substituí-lo pelo print da tela do Packet Tracer se desejar)."
            )

    ensure_latex_files_and_readme(parsed_data, cenario_dir, num_int, force_regen=args.force_skeleton)

    if args.package:
        compile_and_package(cenario_dir, num_str)


if __name__ == "__main__":
    main()
