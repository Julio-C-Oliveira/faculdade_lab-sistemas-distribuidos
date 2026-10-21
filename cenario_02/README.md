# Cenário 02 — Topologia Distribuída, Roteamento OSPF e RIB

## 🎯 Objetivo
Análise e auditoria completa de infraestrutura de rede distribuída com núcleo WAN em malha completa (*full-mesh* com OSPF área 0 entre os roteadores de núcleo R0–R3), roteadores de borda (R4–R7) atendendo quatro redes locais (LANs), cálculo de métricas de custos e tabela esperada de roteamento (RIB).

---

## ✉️ Modelo de E-mail para Envio da Atividade

- **Título (Assunto):** `Cenário 02 - equipe 08 - Laboratório de Sistemas Distribuidos`
- **Arquivo a anexar (Ficheiro):** `cenario_02_equipe_08_Lab_SD.zip` (em `entregas/`)

```text
Assunto: Cenário 02 - equipe 08 - Laboratório de Sistemas Distribuidos
Anexo: cenario_02_equipe_08_Lab_SD.zip

Bom dia professor, segue em anexo a segunda atividade cenario_02_equipe_08_Lab_SD.zip

Discentes: 
- Júlio Costa Oliveira
- Luiz Gabriel Santos Moreira
```

---

## 📊 Resumo da Topologia
- **Roteadores**: 8 (4 de núcleo R0–R3 em malha completa, 4 de borda R4–R7)
- **Switches de Acesso**: 4 (Switch0 a Switch3)
- **Estações de Trabalho**: 9 PCs
- **Enlaces**: 23 (10 seriais WAN + 13 Ethernet LAN)
- **Sub-redes**: 14 (4 LANs `/24` + 10 enlaces seriais `/16`)
- **Protocolo de Roteamento**: OSPF Processo 1, Área única 0

---

## 📂 Estrutura de Arquivos

- **`packet_tracer/`**:
  - Diretório reservado para os arquivos `cenario_02_equipe_08_Lab_SD.pkt` e `cenario_02_equipe_08_Lab_SD.xml`.
- **`relatorio/`**:
  - `main.tex`: Documento principal em LaTeX com capa padrão da UFPA (2º Relatório) e dados dos discentes.
  - `pics/`: Brasão `Logo_UFPA.png` e diagramas da rede (`cenario_ideal.png`, `cenario_real.png`).
  - `sections/`: Seções modulares (`introduction.tex`, `body.tex`, `references.tex`, `references.bib`, etc.).
  - `sections/tabelas/`: Módulos de tabelas (`ifaces.tex`, `switchports.tex`, `pcs.tex`, `rib.tex`, etc.).
  - `template/sbc.bst`: Arquivo de estilo bibliográfico da SBC.
- **`analise/`**:
  - `relatorio_cenario2_equipe8_lab_SD.md`: Documentação técnica gerada a partir dos dados do Packet Tracer.
  - `relatorio_cenario2_equipe8_lab_SD.html`: Versão visual em HTML dos dados e tabelas.
- **`entregas/`**:
  - `cenario_02_equipe_08_Lab_SD.pdf`: Relatório final compilado.
  - `cenario_02_equipe_08_Lab_SD.zip`: Pacote oficial de submissão (PDF + PKT).
