# Laboratório de Sistemas Distribuídos — Práticas e Relatórios
**Universidade Federal do Pará (UFPA)**  
**Instituto de Ciências Exatas e Naturais (ICEN)**  
**Faculdade de Ciências da Computação**  
**Equipe 08**: Júlio Costa Oliveira & Luiz Gabriel Santos Moreira

---

## 🏷️ Padrão Oficial de Nomenclatura

Para manter consistência e conformidade com as submissões acadêmicas, todos os arquivos de cada cenário $XX \in \{01, 02\}$ seguem o padrão:

- **Pacote Compactado de Entrega**: `cenario_XX_equipe_08_Lab_SD.zip`
- **Relatório em PDF**: `cenario_XX_equipe_08_Lab_SD.pdf`
- **Topologia Packet Tracer**: `cenario_XX_equipe_08_Lab_SD.pkt`
- **Topologia Decodificada em XML**: `cenario_XX_equipe_08_Lab_SD.xml`

### ✉️ Formato Padrão de E-mail para Submissão
- **Título (Assunto):** `Cenário XX - equipe 08 - Laboratório de Sistemas Distribuidos`
- **Arquivo a anexar (Ficheiro):** `cenario_XX_equipe_08_Lab_SD.zip` (em `entregas/`)

```text
Assunto: Cenário XX - equipe 08 - Laboratório de Sistemas Distribuidos
Anexo: cenario_XX_equipe_08_Lab_SD.zip

Bom dia professor, segue em anexo a atividade cenario_XX_equipe_08_Lab_SD.zip

Discentes: 
- Júlio Costa Oliveira
- Luiz Gabriel Santos Moreira
```

---

## 📁 Estrutura do Repositório

O repositório adota uma organização simétrica e modular entre os cenários:

```
trabalho_lab_sd/
├── README.md                      # Este arquivo (visão geral, equipe e padrões)
├── .gitignore                     # Filtros para artefatos de build LaTeX, Python e SO
├── archives/                      # Backups de arquivos compactados originais
│   ├── cenario_02.tar.xz
│   └── First_Report_on_Distributed_Systems.zip
├── cenario_01/                    # Cenário 01: Segmentação por VLANs e DHCP Distribuído
│   ├── README.md                  # Contexto, objetivos e modelo de e-mail pronto
│   ├── packet_tracer/             # Topologias (.pkt e .xml)
│   │   ├── original.pkt           # Topologia base fornecida
│   │   ├── cenario_01_equipe_08_Lab_SD.pkt
│   │   └── cenario_01_equipe_08_Lab_SD.xml
│   ├── relatorio/                 # Projeto LaTeX oficial
│   │   ├── main.tex               # Documento principal da equipe (1º Relatório)
│   │   ├── pics/Logo_UFPA.png     # Brasão da UFPA
│   │   ├── sections/              # introduction, body, references, etc.
│   │   └── template/sbc.bst       # Estilo bibliográfico SBC
│   └── entregas/                  # Arquivos prontos para envio
│       ├── cenario_01_equipe_08_Lab_SD.pdf
│       └── cenario_01_equipe_08_Lab_SD.zip
├── cenario_02/                    # Cenário 02: Topologia Distribuída, Roteamento OSPF e RIB
│   ├── README.md                  # Contexto, resumo OSPF e modelo de e-mail pronto
│   ├── packet_tracer/             # Reservado para os arquivos de topologia .pkt e .xml
│   ├── relatorio/                 # Projeto LaTeX oficial (mesmo padrão do Cenário 01)
│   │   ├── main.tex               # Documento principal da equipe (2º Relatório)
│   │   ├── pics/                  # Logo_UFPA.png, cenario_ideal.png, cenario_real.png
│   │   ├── sections/              # introduction, body, references, etc.
│   │   │   └── tabelas/           # ifaces.tex, switchports.tex, pcs.tex, rib.tex, etc.
│   │   └── template/sbc.bst       # Estilo bibliográfico SBC
│   ├── analise/                   # Relatórios auxiliares gerados (.md e .html)
│   └── entregas/                  # Arquivos prontos para envio
│       ├── cenario_02_equipe_08_Lab_SD.pdf
│       └── cenario_02_equipe_08_Lab_SD.zip
└── tools/                         # Utilitários compartilhados
    └── decrypt_pkt_9-0-0.py       # Decompilador de arquivos .pkt do Packet Tracer 9.x
```

---

## 🛠️ Ferramentas

### Decompilador Packet Tracer (`tools/decrypt_pkt_9-0-0.py`)
Utilitário Python para descriptografar arquivos de topologia `.pkt` do Cisco Packet Tracer 9.x:
```bash
python3 tools/decrypt_pkt_9-0-0.py caminho/para/topologia.pkt
```

---

## 📖 Documentação por Cenário

- [Cenário 01 — Detalhes e E-mail de Envio](cenario_01/README.md)
- [Cenário 02 — Detalhes e E-mail de Envio](cenario_02/README.md)
