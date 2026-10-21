---
name: novo-cenario-sd
description: >-
  Coordena e automatiza a criação, extração, auditoria XML, geração de relatório LaTeX
  e empacotamento de entrega de novos cenários (ex: Cenário 03, Cenário 04) da disciplina
  Laboratório de Sistemas Distribuídos (UFPA - Equipe 08) a partir de arquivos adicionados
  na pasta archives/. Ative esta skill sempre que o usuário adicionar um arquivo em archives/
  ou pedir para estruturar/criar um novo cenário no repositório.
---

# Skill: Criação e Padronização de Novo Cenário (`novo-cenario-sd`)

Esta skill coordena todo o fluxo de trabalho para estruturar um novo cenário (`cenario_XX`) no repositório `trabalho_lab_sd`, garantindo **simetria com o Cenário 01 e Cenário 02**, **fidelidade de 100% ao arquivo `.pkt`/`.xml`**, **padrão de nomenclatura oficial** e **modelo de e-mail pronto**.

---

## 1. Identificação Fixa e Padrões Obrigatórios

- **Instituição**: Universidade Federal do Pará (UFPA) / ICEN / Faculdade de Ciências da Computação
- **Disciplina**: Laboratório de Sistemas Distribuídos
- **Equipe 08**:
  - **Júlio Costa Oliveira** — Matrícula: `202104940025`
  - **Luiz Gabriel Santos Moreira** — Matrícula: `202304940001`
- **Nomenclatura Oficial (`XX` com 2 dígitos, ex: `03`, `04`)**:
  - Pasta do cenário: `cenario_XX/`
  - Topologia Packet Tracer: `cenario_XX/packet_tracer/cenario_XX_equipe_08_Lab_SD.pkt`
  - XML Decodificado: `cenario_XX/packet_tracer/cenario_XX_equipe_08_Lab_SD.xml`
  - Relatório PDF: `cenario_XX/entregas/cenario_XX_equipe_08_Lab_SD.pdf`
  - Pacote Final de Entrega: `cenario_XX/entregas/cenario_XX_equipe_08_Lab_SD.zip` (contendo **exclusivamente** o `.pdf` e o `.pkt` na raiz do zip, usando `zip -j`)

---

## 2. Passo a Passo de Execução

### Passo 1: Executar o Motor de Extração, Auditoria e Bootstrap (`process_cenario.py`)

Sempre comece executando o script [process_cenario.py](./scripts/process_cenario.py) passando o número do cenário e (opcionalmente) o caminho do arquivo em `archives/`:

```bash
python3 .agents/skills/novo-cenario-sd/scripts/process_cenario.py --cenario XX
```

O script realiza automaticamente:
1. **Descoberta de todos os arquivos em `archives/`**: Localiza pacotes (`.tar.xz`, `.zip`, `.tar.gz`) e/ou arquivos `.pkt` referentes ao cenário `XX` (modo híbrido: extrai tanto artefatos pré-gerados do pacote quanto o `.pkt`).
2. **Criação da árvore simétrica**:
   - `cenario_XX/packet_tracer/`
   - `cenario_XX/relatorio/{pics,sections/tabelas,template}/`
   - `cenario_XX/analise/`
   - `cenario_XX/entregas/`
3. **Cópia de assets oficiais**: Copia `Logo_UFPA.png`, `sbc.bst` e arquivos base (`references.tex`, `references.bib`, `conclusion.tex`, `appendix.tex`) de `cenario_01/relatorio/`.
4. **Padronização e Decodificação do `.pkt`**:
   - Copia/renomeia o `.pkt` para `cenario_XX/packet_tracer/cenario_XX_equipe_08_Lab_SD.pkt`.
   - Invoca `tools/decrypt_pkt_9-0-0.py` gerando `cenario_XX_equipe_08_Lab_SD.xml`.
   - **Se nenhum `.pkt` for encontrado**: monta toda a estrutura (`main.tex`, `introduction.tex`, `body.tex`, `sections/tabelas/`, `README.md`) a partir dos arquivos disponíveis no pacote e avisa que falta apenas o `.pkt` para fechar o `.zip` final.
5. **Extração e Auditoria tendo o `.xml` como Fonte da Verdade Absoluta**:
   - Extrai todos os dispositivos, modelos reais decodificados de `CUSTOM_VARS`, números de série, enlaces (`LINKS`), interfaces com IP, portas físicas de switch (mapeamento posicional 1-para-1 entre `RUNNINGCONFIG` e `<PORT>`), PCs e `RUNNINGCONFIG`.
   - Detecta dinamicamente os protocolos ativos: **VLANs/802.1Q, OSPF, RIP, EIGRP, Rotas Estáticas, Pools DHCP, Passive Interfaces, ACLs e NAT**.
   - Calcula automaticamente a **RIB esperada** por menor caminho (Dijkstra com ECMP) sobre a topologia real.
   - Gera/sobrescreve as tabelas LaTeX encapsuladas em `cenario_XX/relatorio/sections/tabelas/` (`ifaces.tex`, `switchports.tex`, `pcs.tex`, `rib.tex`, `configs.tex`, `tabelas_geradas.tex`).
   - Gera os relatórios analíticos completos de **9 seções** em `cenario_XX/analise/relatorio_cenarioXX_equipe8_lab_SD.md` e `.html` (estilizado com CSS `.rpt`).
6. **Diagrama Visual da Topologia (`pics/cenario_real.png`)**:
   - Se o pacote em `archives/` trouxer imagens (`.png`/`.jpg`), copia para `cenario_XX/relatorio/pics/`.
   - Se não houver nenhuma imagem, renderiza automaticamente `cenario_real.png` a partir das coordenadas lógicas $(x, y)$ e links do `.xml`.
7. **Relatório LaTeX Inteligente e `README.md`**:
   - Gera `cenario_XX/relatorio/main.tex` com capa padrão UFPA (`XXº Relatório`), `introduction.tex` e `body.tex` (com detecção automática de topologias Núcleo WAN vs. Roteadores de Borda, cálculo de métricas OSPF e DHCP) e `cenario_XX/README.md` com o modelo de e-mail pronto.

---

### Passo 2: Redigir/Refinar `sections/introduction.tex` e `sections/body.tex`

Após rodar `process_cenario.py`, leia o resumo impresso pelo script (e `cenario_XX/analise/relatorio_cenarioXX_equipe8_lab_SD.md`) e refine os arquivos:
- `cenario_XX/relatorio/sections/introduction.tex`:
  - Contextualize o objetivo específico do cenário com base nos protocolos detectados no XML.
- `cenario_XX/relatorio/sections/body.tex`:
  - Descreva a arquitetura física e lógica (quantidade exata de roteadores, switches, PCs e enlaces do XML).
  - Inclua a figura da topologia (`pics/cenario_real.png`).
  - Inclua e comente as tabelas geradas em `sections/tabelas/` (`ifaces.tex`, `switchports.tex`, `pcs.tex`, `vlans.tex` se houver VLANs).
  - Dedique seções específicas aos protocolos ativos detectados no XML (ex: cálculo de métricas e tabela `rib.tex`, escopos DHCP, segmentação VLAN/Trunk, ACLs ou NAT) e finalize com `\input{sections/tabelas/configs.tex}`.
  - **Regra Crítica**: Jamais mencione protocolos que não estejam presentes no `.xml` real.

---

### Passo 3: Compilar o PDF, Empacotar o `.zip` e Validar

Execute o mesmo script com a flag `--package` para compilar o LaTeX em duas passadas (`pdflatex`), limpar arquivos auxiliares (`.aux`, `.log`, `.out`) e gerar o pacote `.zip`:

```bash
python3 .agents/skills/novo-cenario-sd/scripts/process_cenario.py --cenario XX --package
```

Verifique na saída do comando:
1. O PDF `cenario_XX/entregas/cenario_XX_equipe_08_Lab_SD.pdf` foi gerado sem erros de LaTeX.
2. O arquivo `cenario_XX/entregas/cenario_XX_equipe_08_Lab_SD.zip` contém exatamente:
   - `cenario_XX_equipe_08_Lab_SD.pdf`
   - `cenario_XX_equipe_08_Lab_SD.pkt`
   *(Caso o `.pkt` ainda não tenha sido fornecido pelo usuário, pause aqui e peça para o usuário adicionar o `.pkt` em `cenario_XX/packet_tracer/` antes de rodar `--package` e fazer o commit).*

---

### Passo 4: Atualizar `README.md` Raiz e Fazer Commit no Git

1. Verifique se `cenario_XX/README.md` contém o modelo de e-mail no formato obrigatório:
   - **Título (Assunto):** `Cenário XX - equipe 08 - Laboratório de Sistemas Distribuidos`
   - **Arquivo a anexar (Ficheiro):** `cenario_XX_equipe_08_Lab_SD.zip` (em `entregas/`)
   ```text
   Assunto: Cenário XX - equipe 08 - Laboratório de Sistemas Distribuidos
   Anexo: cenario_XX_equipe_08_Lab_SD.zip

   Bom dia professor, segue em anexo a <ordinal> atividade cenario_XX_equipe_08_Lab_SD.zip

   Discentes: 
   - Júlio Costa Oliveira
   - Luiz Gabriel Santos Moreira
   ```
2. Atualize o `README.md` na raiz do repositório adicionando `cenario_XX/` na árvore de diretórios e na lista de links de documentação por cenário.
3. Execute `git add -A` e `git commit -m "feat(cenario_XX): estrutura cenario XX completo com relatorio LaTeX, auditoria XML e pacote de entrega"` na branch `main`.
