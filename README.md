# Trabalhos de Laboratório — Sistemas Distribuídos e Redes
**Universidade Federal do Pará (UFPA)**  
**Instituto de Ciências Exatas e Naturais (ICEN)**  
**Curso de Ciência da Computação**  
**Equipe 08**: Luiz Gabriel Santos Moreira & Christian de Jesus da Costa Marinho

---

## 📁 Estrutura do Repositório

O repositório é organizado de forma modular para isolar os diferentes cenários práticos e ferramentas de apoio:

```
trabalho_lab_sd/
├── README.md                      # Este arquivo (visão geral do repositório)
├── .gitignore                     # Regras para ignorar temporários de LaTeX e SO
├── archives/                      # Cópias de segurança de arquivos brutos compactados
│   └── cenario_02.tar.xz
├── cenario_01/                    # Cenário 01: Segmentação por VLANs e DHCP Distribuído
│   ├── README.md                  # Descrição específica do Cenário 01
│   ├── packet_tracer/             # Arquivos de topologia (.pkt, .xml)
│   ├── relatorio/                 # Fontes LaTeX (.tex) e relatórios em PDF
│   └── entregas/                  # Arquivos e pacotes finais entregues (.zip, .pdf)
├── cenario_02/                    # Cenário 02: Topologia Distribuída, Roteamento OSPF e RIB
│   ├── README.md                  # Descrição específica do Cenário 02
│   ├── packet_tracer/             # Diretório reservado para topologias .pkt/.xml do Cenário 02
│   ├── relatorio_cenario2_*.{tex,pdf,md,html} # Relatórios em múltiplos formatos
│   ├── cenario_ideal.png / cenario_real.png    # Diagramas lógicos da rede
│   └── *.tex                      # Tabelas auxiliares modulares (RIB, configs, portas, etc.)
└── tools/                         # Scripts e utilitários
    └── decrypt_pkt_9-0-0.py       # Decompilador de arquivos .pkt do Packet Tracer 9.x
```

---

## 🛠️ Ferramentas

### Decompilador Packet Tracer (`tools/decrypt_pkt_9-0-0.py`)
Converte contêineres criptografados `.pkt` do Cisco Packet Tracer 9.x em arquivos XML legíveis para auditoria e automação:

```bash
python3 tools/decrypt_pkt_9-0-0.py caminho/para/arquivo.pkt
```
O XML correspondente será gerado no mesmo diretório do arquivo `.pkt`.

---

## 📖 Cenários

- [Cenário 01 — Documentação](cenario_01/README.md)
- [Cenário 02 — Documentação](cenario_02/README.md)
