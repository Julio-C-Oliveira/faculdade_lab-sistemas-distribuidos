# Cenário 02 — Topologia Distribuída, Roteamento OSPF e RIB

## 🎯 Objetivo
Análise e auditoria completa da topologia de rede distribuída com backbone em malha completa (full-mesh OSPF área 0 entre roteadores de núcleo R0–R3), roteadores de borda (R4–R7) atendendo quatro LANs distintas, switches e estações de trabalho.

---

## 📊 Resumo da Topologia
- **Roteadores**: 8 (4 de núcleo R0–R3, 4 de borda R4–R7)
- **Switches**: 4
- **Estações**: 9 PCs
- **Enlaces**: 23 (10 seriais WAN + 13 Ethernet LAN)
- **Sub-redes**: 14 (4 LANs `/24` + 10 enlaces `/16`)
- **Protocolo de Roteamento**: OSPF Processo 1, Área única 0

---

## 📂 Arquivos Disponíveis

- **`relatorio_cenario2_equipe8.tex`**: Fonte principal LaTeX do relatório técnico com análises de camada física, enlace, roteamento e auditoria de configurações.
- **`relatorio_cenario2_equipe8.pdf`**: Relatório compilado.
- **`relatorio_cenario2_equipe8_lab_SD.md` / `.html`**: Relatório em formato Markdown e HTML gerado automaticamente a partir do XML.
- **`cenario_ideal.png` / `cenario_real.png`**: Diagramas da topologia lógica e física.
- **`*.tex`**: Tabelas de interface (`ifaces.tex`), portas de switch (`switchports.tex`), PCs (`pcs.tex`), tabela de roteamento RIB (`rib.tex`), configurações (`configs.tex`) e consolidadas (`tabelas_geradas.tex`).
- **`packet_tracer/`**: Diretório reservado para os arquivos `.pkt` e `.xml` da topologia deste cenário.
