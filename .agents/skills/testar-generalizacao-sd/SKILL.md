---
name: testar-generalizacao-sd
description: >-
  Audita, testa e valida continuamente a capacidade de generalização, cobertura de recursos
  do Packet Tracer (XML) e não-regressão da skill novo-cenario-sd através de todos os cenários
  existentes no repositório (cenario_01, cenario_02, cenario_03...) e de baterias sintéticas
  de topologias extremas (OSPF, EIGRP, RIP, Rotas Estáticas, VLANs, Trunks, SVI/L3 Switch, NAT, ACL).
  Ative esta skill sempre que o usuário pedir para verificar/testar a generalização da skill
  novo-cenario-sd, validar um novo cenário adicionado ou aprimorar o motor process_cenario.py.
---

# Skill: Auditoria Contínua de Generalização (`testar-generalizacao-sd`)

Esta skill atua como uma **suíte de testes automatizada, auditor de cobertura XML e guia de evolução contínua** para a skill [`novo-cenario-sd`](../novo-cenario-sd/SKILL.md) e seu motor [`process_cenario.py`](../novo-cenario-sd/scripts/process_cenario.py).

À medida que novos cenários (`cenario_03`, `cenario_04`, etc.) são adicionados ao repositório com topologias, dispositivos e protocolos inéditos, esta skill verifica automaticamente:
1. **Cobertura Zero-Drop do XML bruto**: se algum `<DEVICE>`, `<TYPE>`, `<CABLE>`, `<VLAN>` ou diretiva de `RUNNINGCONFIG` do Packet Tracer foi ignorado ou mal classificado pelo parser.
2. **Invariantes Estruturais e Compilação LaTeX**: se todas as tabelas (`.tex`), análises de 9 seções (`.md` e `.html`), RIB (`rib.tex`) e relatórios compilam em `pdflatex` sem linhas órfãs ou erros.
3. **Não-Regressão Multi-Cenário (*Golden Regression*)**: se melhorias feitas para um cenário novo quebraram a saída exata de cenários anteriores já homologados (como o `cenario_02`).
4. **Simulação em Topologias Sintéticas Extremas**: testa o cálculo de RIB e a extração contra topologias sintéticas (L3 Multilayer Switch + SVI, EIGRP, RIP, Rotas Estáticas, NAT/ACL, Wireless/VoIP/Server).

---

## 1. Como Executar a Verificação Completa

Sempre que o usuário pedir para testar a generalização da skill ou validar o motor após um novo cenário, execute o script [`verify_generalization.py`](./scripts/verify_generalization.py):

```bash
python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py
```

Opções adicionais da CLI:
- Testar apenas um cenário específico:
  ```bash
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py --cenario 02
  ```
- Incluir teste real de compilação `pdflatex` em diretório temporário isolado (sem sujar o repositório):
  ```bash
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py --compile-latex
  ```
- Salvar um relatório detalhado de evolução/auditoria em Markdown:
  ```bash
  python3 .agents/skills/testar-generalizacao-sd/scripts/verify_generalization.py --report-out relatorio_generalizacao.md
  ```

---

## 2. O Que o Motor `verify_generalization.py` Verifica Automaticamente

### Etapa A — Auditoria *Zero-Drop* contra o XML Bruto (Todos os `cenario_XX` e `archives/`)
Para cada arquivo `.xml` (ou `.pkt` decodificado temporariamente) encontrado no repositório:
1. **Tipos de Dispositivos (`<TYPE>`)**: compara o conjunto de `<TYPE>` existentes no XML bruto com as constantes `END_HOST_TYPES`, `Router`, `Switch`, `Multilayer Switch` de `process_cenario.py`. Se surgir um tipo novo no Packet Tracer (ex: `Firewall`, `IoT`, `Hub`, `Repeater`, `Meraki`), emite um alerta **`[GAP DE DISPOSITIVO]`** indicando a linha exata a expandir.
2. **Modelos (`CUSTOM_VARS -> PT_MODEL`)**: verifica se algum dispositivo retornou modelo genérico por falha de decodificação Base64.
3. **Contagem de Enlaces (`<LINK>`)**: confirma que 100% dos cabos físicos de rede foram mapeados e nenhum tipo de cabo (`<CABLE><TYPE>`) ficou sem tradução.
4. **Diretivas IOS (`<RUNNINGCONFIG>`)**: varre todas as linhas de configuração IOS de todos os roteadores e switches procurando comandos de protocolos ainda não extraídos pelo parser (ex: `router bgp`, `ipv6 route`, `standby` HSRP, `channel-group` EtherChannel, `ip nat`, `access-list`, `switchport voice vlan`), reportando **`[GAP DE COMANDO IOS]`** quando encontrar diretivas novas.

### Etapa B — Validação de Consistência das 9 Seções e RIB
Para cada cenário analisado:
1. Verifica se `build_9_sections_data()` gera todas as seções esperadas sem exceções e sem células `None` ou `KeyError`.
2. Verifica se todos os roteadores (e switches L3 com roteamento) possuem entradas calculadas na **RIB (`compute_expected_rib`)** e se todas as sub-redes diretamente conectadas (`C`) estão presentes.
3. Verifica se as tabelas LaTeX geradas em sandbox (`ifaces.tex`, `switchports.tex`, `pcs.tex`, `rib.tex`, `configs.tex`, `tabelas_geradas.tex` e `vlans.tex` quando aplicável) possuem delimitadores `\begin{tabular}` / `\end{tabular}` balanceados e caracteres especiais devidamente escapados.

### Etapa C — Teste de Não-Regressão (*Golden Baseline*)
Compara byte a byte (`0 diff`) a saída gerada em memória/sandbox pelo `process_cenario.py` contra os arquivos oficiais dos cenários homologados com o motor (ex: `cenario_02`), garantindo que o suporte a novos protocolos nunca altere o comportamento dos cenários anteriores.

### Etapa D — Bateria de Topologias Sintéticas Extremas (*Stress Test*)
Cria em memória um XML sintético contendo recursos avançados combinados que podem aparecer nos próximos laboratórios:
- **Switch Multicamada (L3 `3560-24PS`)** com SVIs (`interface Vlan10`, `interface Vlan20`), `ip routing` e Trunks 802.1Q;
- **Múltiplos Protocolos de Roteamento Simultâneos**: OSPF + EIGRP + RIP + Rotas Estáticas (`ip route`) verificando o desempate correto por **Distância Administrativa** (`C=0 < S=1 < D=90 < O=110 < R=120`) e **ECMP**;
- **Dispositivos Diversos**: `Server`, `Printer`, `IpPhone`, `WirelessEndDevice`, `Laptop`.

---

## 3. Fluxo de Aprimoramento Contínuo (Ciclo de Evolução)

Sempre que `verify_generalization.py` apontar um **`[AVISO / GAP]`** ou uma falha em um novo `cenario_XX`:

1. **Inspecione o Diagnóstico**: Veja na saída do script qual tag XML (`<TYPE>`, `<PORT>`, `<VLAN>`) ou comando do `RUNNINGCONFIG` não foi reconhecido.
2. **Aprimore o `process_cenario.py`**:
   - Novos dispositivos finais $\rightarrow$ adicione em `END_HOST_TYPES` e no dicionário `type_pt` de `build_9_sections_data()`.
   - Novo comando IOS $\rightarrow$ adicione a captura em `parse_running_config()` e inclua na seção correspondente.
   - Novo protocolo de roteamento $\rightarrow$ adicione o cálculo de distância administrativa e métrica em `compute_expected_rib()`.
3. **Re-execute `verify_generalization.py`**:
   - Confirme que o score de generalização voltou a **100% (PASS)** e que o teste de **Não-Regressão (`cenario_02`)** continua com `0 diff`.
