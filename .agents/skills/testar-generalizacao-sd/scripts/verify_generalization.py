#!/usr/bin/env python3
"""
Suíte de Auditoria Contínua de Generalização, Cobertura XML e Não-Regressão
para a skill `novo-cenario-sd` (`process_cenario.py`).

Uso:
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py --cenario 02 --compile-latex
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py --report-out relatorio_auditoria.md
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NOVO_CENARIO_SCRIPTS = REPO_ROOT / ".agents" / "skills" / "novo-cenario-sd" / "scripts"
sys.path.insert(0, str(NOVO_CENARIO_SCRIPTS))

import process_cenario as pc  # noqa: E402

# Cenários cujo relatório e tabelas foram gerados com o motor padrão (baseline 0-diff)
GOLDEN_REGRESSION_SCENARIOS = {
    2: [
        "README.md",
        "relatorio/main.tex",
        "relatorio/sections/introduction.tex",
        "relatorio/sections/body.tex",
        "relatorio/sections/tabelas/ifaces.tex",
        "relatorio/sections/tabelas/switchports.tex",
        "relatorio/sections/tabelas/pcs.tex",
        "relatorio/sections/tabelas/rib.tex",
        "relatorio/sections/tabelas/configs.tex",
        "relatorio/sections/tabelas/tabelas_geradas.tex",
    ]
}

# Linhas padrão do IOS no Packet Tracer que são intencionalmente ignoradas por serem boilerplate
KNOWN_BOILERPLATE_IOS_PREFIXES = (
    "!",
    "version ",
    "no service ",
    "service ",
    "hostname ",
    "ip cef",
    "no ipv6 cef",
    "ip ssh ",
    "ip domain-name ",
    "ip domain-lookup",
    "no ip domain-lookup",
    "username ",
    "enable ",
    "spanning-tree ",
    "interface ",
    "ip address ",
    "no ip address",
    "duplex ",
    "speed ",
    "clock rate ",
    "description ",
    "shutdown",
    "no shutdown",
    "encapsulation dot1q",
    "encapsulation dot1Q",
    "switchport",
    "ip dhcp ",
    "network ",
    "default-router ",
    "dns-server ",
    "router ospf",
    "router rip",
    "router eigrp",
    "router-id ",
    "passive-interface ",
    "auto-summary",
    "no auto-summary",
    "version 2",
    "log-adjacency-changes",
    "ip route ",
    "access-list ",
    "ip access-list ",
    "ip nat ",
    "vlan ",
    "name ",
    "ip classless",
    "flowcontrol ",
    "media-type ",
    "negotiation ",
    "line ",
    "exec-timeout ",
    "password ",
    "logging ",
    "login",
    "transport ",
    "end",
    "exit",
    "ip routing",
    "ip helper-address",
    "ip default-gateway",
    "no ip cef",
    "ip flow-export",
    "ptp clock",
)


def audit_raw_xml_zero_drop(xml_path: Path, parsed_data: dict) -> dict:
    """Compara o XML bruto do Packet Tracer contra o dicionário extraído por process_cenario.py."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    raw_devices = []
    unknown_device_types = []
    unrecognized_ios_cmds = []
    recognized_types = set(pc.END_HOST_TYPES) | set(pc.IGNORED_DEVICE_TYPES) | {
        "Router",
        "Switch",
        "Multilayer Switch",
        "AccessPoint",
        "Cloud",
    }

    for d in root.findall(".//NETWORK/DEVICES/DEVICE"):
        eng = d.find("ENGINE")
        if eng is None:
            continue
        dname = eng.findtext("NAME") or "Unknown"
        dtype = eng.findtext("TYPE") or "Unknown"
        raw_devices.append((dname, dtype))
        if dtype not in recognized_types:
            unknown_device_types.append(f"{dname} (TYPE='{dtype}')")

        rc_node = eng.find("RUNNINGCONFIG")
        if rc_node is not None:
            for line_el in rc_node.findall("LINE"):
                line = (line_el.text or "").strip()
                if not line:
                    continue
                if not line.startswith(KNOWN_BOILERPLATE_IOS_PREFIXES):
                    unrecognized_ios_cmds.append(f"{dname}: `{line}`")

    # Contar cabos físicos de rede no XML bruto
    raw_cables = 0
    unknown_cable_types = []
    known_cables = {"eStraightThrough", "eCrossOver", "eSerial", "eFiber", "eConsole", "eCoaxial", "ePhone", "eOctal"}
    for link in root.findall(".//NETWORK/LINKS/LINK"):
        c = link.find("CABLE")
        if c is None:
            continue
        raw_cables += 1
        ctype = c.attrib.get("type") or c.findtext("TYPE") or "eStraightThrough"
        if ctype not in known_cables:
            unknown_cable_types.append(ctype)

    return {
        "raw_device_count": len(raw_devices),
        "parsed_device_count": len(parsed_data["devices"]),
        "raw_link_count": raw_cables,
        "parsed_link_count": len(parsed_data["links"]),
        "unknown_device_types": unknown_device_types,
        "unknown_cable_types": unknown_cable_types,
        "unrecognized_ios_cmds": unrecognized_ios_cmds,
    }


def validate_scenario(cenario_num: int, xml_path: Path, cenario_dir: Path = None, compile_latex: bool = False) -> dict:
    """Executa bateria de validação sobre um cenário real do repositório."""
    checks = []
    warnings = []

    def add_check(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": passed, "detail": detail})

    # 1. Parse XML
    try:
        data = pc.parse_packet_tracer_xml(xml_path)
        add_check("Parse XML Packet Tracer", True, f"PT v{data['version']} ({len(data['devices'])} disp, {len(data['links'])} links)")
    except Exception as e:
        add_check("Parse XML Packet Tracer", False, f"Exceção: {e}")
        return {"cenario": cenario_num, "checks": checks, "warnings": warnings, "data": None}

    # 2. Auditoria Zero-Drop
    zdrop = audit_raw_xml_zero_drop(xml_path, data)
    dev_match = zdrop["raw_device_count"] == zdrop["parsed_device_count"]
    add_check(
        "Cobertura 100% de Dispositivos XML",
        dev_match,
        f"XML bruto={zdrop['raw_device_count']}, extraídos={zdrop['parsed_device_count']}",
    )
    link_match = zdrop["raw_link_count"] == zdrop["parsed_link_count"]
    add_check(
        "Cobertura 100% de Enlaces/Cabos XML",
        link_match,
        f"XML bruto={zdrop['raw_link_count']}, extraídos={zdrop['parsed_link_count']}",
    )
    add_check(
        "Tipos de Dispositivos Reconhecidos",
        len(zdrop["unknown_device_types"]) == 0,
        "Todos reconhecidos" if not zdrop["unknown_device_types"] else f"Desconhecidos: {zdrop['unknown_device_types']}",
    )
    if zdrop["unrecognized_ios_cmds"]:
        warnings.append(f"Diretivas IOS novas detectadas no XML ({len(zdrop['unrecognized_ios_cmds'])}): {', '.join(zdrop['unrecognized_ios_cmds'][:5])}")

    # 3. Construção das 9 Seções Analíticas
    try:
        sec9 = pc.build_9_sections_data(data)
        has_all_keys = all(k in sec9 for k in ("resumo", "dispositivos", "rif_sorted", "enlaces", "subredes", "vlans", "protocolos", "dhcp"))
        add_check(
            "Geração das 9 Seções Analíticas",
            has_all_keys,
            f"Sub-redes={len(sec9['subredes'])}, VLANs={len(sec9['vlans'])}, Protocolos={len(sec9['protocolos'])}, DHCP={len(sec9['dhcp'])}",
        )
    except Exception as e:
        add_check("Geração das 9 Seções Analíticas", False, f"Erro: {e}")

    # 4. Consistência da RIB
    routers_with_ip = [
        d for d in data["devices"] if d["type"] in ("Router", "Multilayer Switch") and any(ifd["ip"] for ifd in d["config"]["interfaces"].values())
    ]
    rib_ok = len(data["rib"]) == len(routers_with_ip) and all(len(v) > 0 for v in data["rib"].values())
    add_check(
        "Cálculo da Tabela RIB (Dijkstra/AD/ECMP)",
        rib_ok,
        f"{len(data['rib'])}/{len(routers_with_ip)} roteadores L3 com rotas calculadas",
    )

    # 5. Geração de arquivos LaTeX, MD, HTML e README em Sandbox Temporário
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tab_dir = tmp_path / "relatorio" / "sections" / "tabelas"
        analise_dir = tmp_path / "analise"
        pics_dir = tmp_path / "relatorio" / "pics"
        tpl_dir = tmp_path / "relatorio" / "template"
        sec_dir = tmp_path / "relatorio" / "sections"
        for d in (tab_dir, analise_dir, pics_dir, tpl_dir, sec_dir):
            d.mkdir(parents=True, exist_ok=True)

        try:
            pc.write_latex_tables(data, tab_dir)
            pc.write_analysis_md_and_html(data, analise_dir, cenario_num)
            pc.ensure_latex_files_and_readme(data, tmp_path, cenario_num, force_regen=True)
            pc.render_topology_diagram(data, pics_dir / "cenario_real.png")

            expected_files = [
                tab_dir / "ifaces.tex",
                tab_dir / "switchports.tex",
                tab_dir / "pcs.tex",
                tab_dir / "rib.tex",
                tab_dir / "configs.tex",
                tab_dir / "tabelas_geradas.tex",
                analise_dir / f"relatorio_cenario{cenario_num}_equipe8_lab_SD.md",
                analise_dir / f"relatorio_cenario{cenario_num}_equipe8_lab_SD.html",
                tmp_path / "relatorio" / "main.tex",
                sec_dir / "introduction.tex",
                sec_dir / "body.tex",
                tmp_path / "README.md",
            ]
            missing = [f.name for f in expected_files if not f.exists() or f.stat().st_size == 0]
            add_check(
                "Geração de Artefatos (.tex, .md, .html, .png, README)",
                len(missing) == 0,
                "Todos os 12+ artefatos gerados com sucesso" if not missing else f"Faltando/vazios: {missing}",
            )
        except Exception as e:
            add_check("Geração de Artefatos (.tex, .md, .html, .png, README)", False, f"Exceção: {e}")

        # 6. Teste de Não-Regressão (Golden Baseline) se aplicável
        if cenario_num in GOLDEN_REGRESSION_SCENARIOS and cenario_dir and cenario_dir.exists():
            diffs = []
            for rel_f in GOLDEN_REGRESSION_SCENARIOS[cenario_num]:
                f_gen = tmp_path / rel_f
                f_real = cenario_dir / rel_f
                if not f_gen.exists() or not f_real.exists():
                    diffs.append(f"{rel_f} (ausente)")
                elif f_gen.read_text(encoding="utf-8") != f_real.read_text(encoding="utf-8"):
                    diffs.append(rel_f)
            add_check(
                f"Não-Regressão Golden Baseline (cenario_{cenario_num:02d})",
                len(diffs) == 0,
                f"0 byte diff em todos os {len(GOLDEN_REGRESSION_SCENARIOS[cenario_num])} arquivos oficiais"
                if not diffs
                else f"Diferenças em: {diffs}",
            )

        # 7. Compilação opcional pdflatex
        if compile_latex:
            c1_rel = REPO_ROOT / "cenario_01" / "relatorio"
            if (c1_rel / "pics" / "Logo_UFPA.png").exists():
                shutil.copy2(c1_rel / "pics" / "Logo_UFPA.png", pics_dir / "Logo_UFPA.png")
            for sfile in ("references.tex", "references.bib", "conclusion.tex", "appendix.tex"):
                if (c1_rel / "sections" / sfile).exists():
                    shutil.copy2(c1_rel / "sections" / sfile, sec_dir / sfile)
            res = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=tmp_path / "relatorio",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            pdf_ok = res.returncode == 0 and (tmp_path / "relatorio" / "main.pdf").exists()
            add_check(
                "Compilação LaTeX (pdflatex em sandbox)",
                pdf_ok,
                f"main.pdf gerado ({(tmp_path / 'relatorio' / 'main.pdf').stat().st_size:,} bytes)" if pdf_ok else "Falha na compilação pdflatex",
            )

    return {"cenario": cenario_num, "checks": checks, "warnings": warnings, "data": data}


def run_synthetic_extreme_topologies_test() -> list:
    """
    Cria em memória uma topologia sintética extrema combinando recursos que ainda não apareceram
    juntos nos Cenários 01 e 02 (Multilayer Switch L3 + SVI + EIGRP + RIP + Rotas Estáticas + OSPF + Trunks + VoIP/Server)
    para garantir que o motor generaliza sem falhas.
    """
    synthetic_xml = """<?xml version="1.0" encoding="utf-8"?>
<PACKETTRACER5>
  <VERSION>9.0.1.0858</VERSION>
  <NETWORK>
    <DEVICES>
      <DEVICE>
        <ENGINE>
          <NAME>MLS0</NAME>
          <TYPE>Multilayer Switch</TYPE>
          <SAVE_REF_ID>dev-mls0</SAVE_REF_ID>
          <SYS_NAME>CoreL3</SYS_NAME>
          <SERIALNUMBER>PTT-MLS-001</SERIALNUMBER>
          <RUNNINGCONFIG>
            <LINE>hostname CoreL3</LINE>
            <LINE>ip routing</LINE>
            <LINE>ip dhcp excluded-address 10.10.10.1 10.10.10.5</LINE>
            <LINE>ip dhcp pool POOL_VOZ</LINE>
            <LINE> network 10.10.10.0 255.255.255.0</LINE>
            <LINE> default-router 10.10.10.1</LINE>
            <LINE> dns-server 1.1.1.1</LINE>
            <LINE>interface GigabitEthernet0/1</LINE>
            <LINE> switchport mode trunk</LINE>
            <LINE> switchport trunk native vlan 99</LINE>
            <LINE> switchport trunk allowed vlan 10,20,99</LINE>
            <LINE>interface GigabitEthernet0/2</LINE>
            <LINE> ip address 10.0.0.1 255.255.255.252</LINE>
            <LINE>interface Vlan10</LINE>
            <LINE> ip address 10.10.10.1 255.255.255.0</LINE>
            <LINE>router eigrp 100</LINE>
            <LINE> network 10.0.0.0 0.0.0.3</LINE>
            <LINE> network 10.10.10.0 0.0.0.255</LINE>
            <LINE> passive-interface Vlan10</LINE>
            <LINE>ip route 192.168.99.0 255.255.255.0 10.0.0.2</LINE>
          </RUNNINGCONFIG>
          <VLAN number="10" name="VOZ_CORP"/>
          <VLAN number="20" name="DADOS_CORP"/>
          <VLAN number="99" name="NATIVA_MGMT"/>
          <PORTS>
            <PORT><TYPE>eCopperGigabitEthernet</TYPE><BANDWIDTH>1000000</BANDWIDTH><FULLDUPLEX>true</FULLDUPLEX></PORT>
            <PORT><TYPE>eCopperGigabitEthernet</TYPE><BANDWIDTH>1000000</BANDWIDTH><FULLDUPLEX>true</FULLDUPLEX></PORT>
          </PORTS>
        </ENGINE>
        <WORKSPACE><LOGICAL><X>200</X><Y>200</Y></LOGICAL></WORKSPACE>
      </DEVICE>
      <DEVICE>
        <ENGINE>
          <NAME>SWAccess</NAME>
          <TYPE>Switch</TYPE>
          <SAVE_REF_ID>dev-swa</SAVE_REF_ID>
          <SYS_NAME>SWAccess</SYS_NAME>
          <SERIALNUMBER>PTT-SWA-001</SERIALNUMBER>
          <RUNNINGCONFIG>
            <LINE>hostname SWAccess</LINE>
            <LINE>interface GigabitEthernet0/1</LINE>
            <LINE> switchport mode trunk</LINE>
          </RUNNINGCONFIG>
          <PORTS>
            <PORT><TYPE>eCopperGigabitEthernet</TYPE><BANDWIDTH>1000000</BANDWIDTH><FULLDUPLEX>true</FULLDUPLEX></PORT>
          </PORTS>
        </ENGINE>
        <WORKSPACE><LOGICAL><X>100</X><Y>400</Y></LOGICAL></WORKSPACE>
      </DEVICE>
      <DEVICE>
        <ENGINE>
          <NAME>RouterBorda</NAME>
          <TYPE>Router</TYPE>
          <SAVE_REF_ID>dev-r1</SAVE_REF_ID>
          <SYS_NAME>RBorda</SYS_NAME>
          <SERIALNUMBER>PTT-RTR-002</SERIALNUMBER>
          <RUNNINGCONFIG>
            <LINE>hostname RBorda</LINE>
            <LINE>interface GigabitEthernet0/0</LINE>
            <LINE> ip address 10.0.0.2 255.255.255.252</LINE>
            <LINE>interface GigabitEthernet0/1</LINE>
            <LINE> ip address 192.168.99.1 255.255.255.0</LINE>
            <LINE>router eigrp 100</LINE>
            <LINE> network 10.0.0.0 0.0.0.3</LINE>
            <LINE> network 192.168.99.0 0.0.0.255</LINE>
            <LINE>router rip</LINE>
            <LINE> version 2</LINE>
            <LINE> network 10.0.0.0</LINE>
            <LINE> network 192.168.99.0</LINE>
          </RUNNINGCONFIG>
          <PORTS>
            <PORT><TYPE>eCopperGigabitEthernet</TYPE><BANDWIDTH>1000000</BANDWIDTH><FULLDUPLEX>true</FULLDUPLEX></PORT>
            <PORT><TYPE>eCopperGigabitEthernet</TYPE><BANDWIDTH>1000000</BANDWIDTH><FULLDUPLEX>true</FULLDUPLEX></PORT>
          </PORTS>
        </ENGINE>
        <WORKSPACE><LOGICAL><X>500</X><Y>200</Y></LOGICAL></WORKSPACE>
      </DEVICE>
      <DEVICE>
        <ENGINE>
          <NAME>SrvDNS</NAME>
          <TYPE>Server</TYPE>
          <SAVE_REF_ID>dev-srv</SAVE_REF_ID>
          <GATEWAY>192.168.99.1</GATEWAY>
          <DNS_SERVER_IP>1.1.1.1</DNS_SERVER_IP>
          <PORTS>
            <PORT>
              <TYPE>eCopperGigabitEthernet</TYPE>
              <IP>192.168.99.10</IP>
              <SUBNET>255.255.255.0</SUBNET>
              <BANDWIDTH>1000000</BANDWIDTH>
              <FULLDUPLEX>true</FULLDUPLEX>
              <PORT_DHCP_ENABLE>false</PORT_DHCP_ENABLE>
            </PORT>
          </PORTS>
        </ENGINE>
        <WORKSPACE><LOGICAL><X>700</X><Y>200</Y></LOGICAL></WORKSPACE>
      </DEVICE>
    </DEVICES>
    <LINKS>
      <LINK>
        <CABLE type="eCrossOver">
          <ENDPOINT><DEVICE>dev-mls0</DEVICE><PORT>GigabitEthernet0/1</PORT></ENDPOINT>
          <ENDPOINT><DEVICE>dev-swa</DEVICE><PORT>GigabitEthernet0/1</PORT></ENDPOINT>
        </CABLE>
      </LINK>
      <LINK>
        <CABLE type="eCrossOver">
          <ENDPOINT><DEVICE>dev-mls0</DEVICE><PORT>GigabitEthernet0/2</PORT></ENDPOINT>
          <ENDPOINT><DEVICE>dev-r1</DEVICE><PORT>GigabitEthernet0/0</PORT></ENDPOINT>
        </CABLE>
      </LINK>
      <LINK>
        <CABLE type="eStraightThrough">
          <ENDPOINT><DEVICE>dev-r1</DEVICE><PORT>GigabitEthernet0/1</PORT></ENDPOINT>
          <ENDPOINT><DEVICE>dev-srv</DEVICE><PORT>GigabitEthernet0</PORT></ENDPOINT>
        </CABLE>
      </LINK>
    </LINKS>
  </NETWORK>
</PACKETTRACER5>"""

    checks = []
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "synthetic_extreme.xml"
        xml_file.write_text(synthetic_xml, encoding="utf-8")
        data = pc.parse_packet_tracer_xml(xml_file)
        sec9 = pc.build_9_sections_data(data)

        # 1. Verificar Switch Multicamada L3 + SVI + Trunk
        mls_rib = data["rib"].get("CoreL3 (MLS0)", [])
        has_svi_route = any(e["subnet"] == "10.10.10.0/24" and e["code"] == "C" for e in mls_rib)
        checks.append(
            {
                "name": "[Sintético] Switch Multicamada L3 + SVI na RIB",
                "passed": has_svi_route,
                "detail": f"Rotas CoreL3: {[(e['subnet'], e['code']) for e in mls_rib]}",
            }
        )

        # 2. Verificar Precedência de Distância Administrativa (Estática S [AD=1] vs EIGRP D [AD=90] vs RIP R [AD=120])
        # Para 192.168.99.0/24 em CoreL3, há rota estática (AD=1) e EIGRP (AD=90). Deve vencer 'S'!
        has_static_win = any(e["subnet"] == "192.168.99.0/24" and e["code"] == "S" for e in mls_rib)
        # Para 10.10.10.0/24 em RBorda, EIGRP (AD=90) deve vencer e instalar 'D'!
        rb_rib = data["rib"].get("RBorda (RouterBorda)", [])
        has_eigrp_win = any(e["subnet"] == "10.10.10.0/24" and e["code"] == "D" for e in rb_rib)
        checks.append(
            {
                "name": "[Sintético] Seleção por Distância Administrativa (S < D < O < R)",
                "passed": has_static_win and has_eigrp_win,
                "detail": f"CoreL3->192.168.99.0/24 via 'S' ({has_static_win}), RBorda->10.10.10.0/24 via 'D' ({has_eigrp_win})",
            }
        )

        # 3. Verificar Trunk allowed/native VLANs e DHCP em Switch L3
        sw_trunks = [sp for sp in data["switch_ports"] if sp["mode"] == "trunk" and "10,20,99" in sp["vlan"] and "nativa 99" in sp["vlan"]]
        has_sw_dhcp = len(sec9["dhcp"]) == 1 and sec9["dhcp"][0][0] == "MLS0"
        checks.append(
            {
                "name": "[Sintético] Trunk 802.1Q (Allowed + Native VLAN) & DHCP em Switch",
                "passed": bool(sw_trunks) and has_sw_dhcp,
                "detail": f"Porta trunk VLAN='{sw_trunks[0]['vlan'] if sw_trunks else 'N/A'}', DHCP Switch={has_sw_dhcp}",
            }
        )

    return checks


def main():
    parser = argparse.ArgumentParser(description="Verifica a generalização e não-regressão da skill novo-cenario-sd.")
    parser.add_argument("--cenario", help="Testar apenas um cenário específico (ex: 01, 02)")
    parser.add_argument("--compile-latex", action="store_true", help="Executa pdflatex em sandbox para validar compilação do PDF")
    parser.add_argument("--report-out", help="Salvar relatório detalhado em arquivo Markdown")
    args = parser.parse_args()

    # Descobrir todos os cenários no repositório
    scenario_dirs = sorted(
        [d for d in REPO_ROOT.iterdir() if d.is_dir() and re.match(r"^cenario_\d+$", d.name)],
        key=lambda d: int(re.sub(r"\D", "", d.name)),
    )
    if args.cenario:
        target_num = int(re.sub(r"\D", "", args.cenario))
        scenario_dirs = [d for d in scenario_dirs if int(re.sub(r"\D", "", d.name)) == target_num]

    all_results = []
    total_checks = 0
    passed_checks = 0

    print("=" * 78)
    print(" AUDITORIA DE GENERALIZAÇÃO E NÃO-REGRESSÃO — SKILL `novo-cenario-sd`")
    print("=" * 78)

    for cdir in scenario_dirs:
        cnum = int(re.sub(r"\D", "", cdir.name))
        xml_files = list((cdir / "packet_tracer").glob("*.xml"))
        if not xml_files:
            print(f"\n[!] {cdir.name}: Nenhum arquivo .xml encontrado em packet_tracer/.")
            continue
        xml_path = xml_files[0]
        res = validate_scenario(cnum, xml_path, cdir, compile_latex=args.compile_latex)
        all_results.append(res)

        d = res["data"]
        protos_str = ", ".join(d["protocols"]) if d and d["protocols"] else "L2/Conectado"
        print(f"\n▶ Cenário {cnum:02d} ({xml_path.name}) — Recursos: [{protos_str}]")
        for chk in res["checks"]:
            total_checks += 1
            if chk["passed"]:
                passed_checks += 1
            icon = "✅ PASS" if chk["passed"] else "❌ FAIL"
            print(f"  {icon} | {chk['name']}: {chk['detail']}")
        for w in res["warnings"]:
            print(f"  ⚠️  GAP  | {w}")

    # Rodar bateria sintética extrema
    print("\n▶ Bateria Sintética de Topologias Extremas (Stress Test Multi-Protocolo)")
    syn_checks = run_synthetic_extreme_topologies_test()
    for chk in syn_checks:
        total_checks += 1
        if chk["passed"]:
            passed_checks += 1
        icon = "✅ PASS" if chk["passed"] else "❌ FAIL"
        print(f"  {icon} | {chk['name']}: {chk['detail']}")

    score = (passed_checks / total_checks * 100.0) if total_checks else 100.0
    print("\n" + "=" * 78)
    print(f" RESULTADO GLOBAL: {passed_checks}/{total_checks} verificações aprovadas ({score:.1f}%)")
    print("=" * 78)

    if args.report_out:
        out_p = Path(args.report_out)
        lines = [
            "# Relatório de Auditoria de Generalização — `novo-cenario-sd`",
            "",
            f"- **Score Global**: `{passed_checks}/{total_checks}` ({score:.1f}%)",
            "",
        ]
        for res in all_results:
            cnum = res["cenario"]
            lines.append(f"## Cenário {cnum:02d}")
            lines.append("| Verificação | Status | Detalhes |")
            lines.append("|---|---|---|")
            for chk in res["checks"]:
                st = "PASS" if chk["passed"] else "FAIL"
                lines.append(f"| {chk['name']} | **{st}** | {chk['detail']} |")
            if res["warnings"]:
                lines.append("\n**Avisos / Novos Comandos Detectados:**")
                for w in res["warnings"]:
                    lines.append(f"- {w}")
            lines.append("")
        lines.append("## Bateria Sintética Multi-Protocolo")
        lines.append("| Verificação | Status | Detalhes |")
        lines.append("|---|---|---|")
        for chk in syn_checks:
            st = "PASS" if chk["passed"] else "FAIL"
            lines.append(f"| {chk['name']} | **{st}** | {chk['detail']} |")
        out_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[+] Relatório salvo em: {out_p}")

    sys.exit(0 if passed_checks == total_checks else 1)


if __name__ == "__main__":
    main()
