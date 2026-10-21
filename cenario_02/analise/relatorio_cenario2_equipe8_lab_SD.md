# Relatório de rede — cenario2_equipe8_lab_SD

Origem: `cenario2_equipe8_lab_SD.xml` · Packet Tracer 9.0.1.0858 · gerado em 14/10/2026 18:44

### Resumo

| Item | Quantidade |
|---|---|
| Versão do Packet Tracer | 9.0.1.0858 |
| Roteador(s) | 8 |
| Switch(s) | 4 |
| PC(s) | 9 |
| Enlaces (cabos) | 23 |
| Sub-redes IPv4 distintas | 14 |
| Interfaces com IP | 24 |

### Dispositivos

| Nome | Tipo | Modelo | Hostname (config) | Nº de série | Interfaces físicas | Gateway padrão | DNS |
|---|---|---|---|---|---|---|---|
| Router0 | Roteador | Router-PT-Empty | R0 | PTT0810HNIR- | 4 | — | — |
| Router1 | Roteador | Router-PT-Empty | R1 | PTT081005M3- | 4 | — | — |
| Router2 | Roteador | Router-PT-Empty | R2 | PTT0810F5B8- | 4 | — | — |
| Router3 | Roteador | Router-PT-Empty | R3 | PTT081027DO- | 4 | — | — |
| Router4 | Roteador | Router-PT-Empty | R4 | PTT0810FAF6- | 2 | — | — |
| Router5 | Roteador | Router-PT-Empty | R5 | PTT08108RO6- | 2 | — | — |
| Router6 | Roteador | Router-PT-Empty | R6 | PTT0810MO36- | 2 | — | — |
| Router7 | Roteador | Router-PT-Empty | R7 | PTT0810B80V- | 2 | — | — |
| Switch0 | Switch | Switch-PT-Empty | Switch | PTT08104TFM- | 4 | — | — |
| Switch1 | Switch | Switch-PT-Empty | Switch | PTT0810PZK1- | 4 | — | — |
| Switch2 | Switch | Switch-PT-Empty | Switch | PTT08105MP4- | 4 | — | — |
| Switch3 | Switch | Switch-PT-Empty | Switch | PTT081018V6- | 4 | — | — |
| PC0 | PC | PC-PT | PC | PTT08108RDE | 1 | 200.168.10.254 | 8.8.8.8 |
| PC1 | PC | PC-PT | PC | PTT0810M2TB | 1 | 200.168.10.254 | 8.8.8.8 |
| PC2 | PC | PC-PT | PC | PTT0810O0G0 | 1 | 200.168.40.254 | 8.8.8.8 |
| PC3 | PC | PC-PT | PC | PTT08101EIH | 1 | 200.168.40.254 | 8.8.8.8 |
| PC4 | PC | PC-PT | PC | PTT0810B3MA | 1 | 200.168.30.254 | 8.8.8.8 |
| PC5 | PC | PC-PT | PC | PTT0810N4J4 | 1 | 200.168.30.254 | 8.8.8.8 |
| PC6 | PC | PC-PT | PC | PTT0810G929 | 1 | 200.168.20.254 | 8.8.8.8 |
| PC7 | PC | PC-PT | PC | PTT0810VYC9 | 1 | 200.168.20.254 | 8.8.8.8 |
| PC8 | PC | PC-PT | — | PTT0810G54E | 1 | 200.168.10.254 | 8.8.8.8 |

### Interfaces de roteadores e SVIs

| Dispositivo | Hostname | Interface | IP | Máscara | Prefixo | Banda | Descrição | Situação | Conectado a |
|---|---|---|---|---|---|---|---|---|---|
| Router0 | R0 | Serial6/0 | 172.30.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router1 Serial6/0 |
| Router0 | R0 | Serial7/0 | 172.20.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router4 Serial0/0 |
| Router0 | R0 | Serial8/0 | 172.100.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router2 Serial9/0 |
| Router0 | R0 | Serial9/0 | 172.90.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router3 Serial9/0 |
| Router1 | R1 | Serial6/0 | 172.30.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router0 Serial6/0 |
| Router1 | R1 | Serial7/0 | 172.50.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router2 Serial7/0 |
| Router1 | R1 | Serial8/0 | 172.110.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router3 Serial7/0 |
| Router1 | R1 | Serial9/0 | 172.40.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router5 Serial0/0 |
| Router2 | R2 | Serial6/0 | 172.60.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router6 Serial0/0 |
| Router2 | R2 | Serial7/0 | 172.50.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router1 Serial7/0 |
| Router2 | R2 | Serial8/0 | 172.70.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router3 Serial8/0 |
| Router2 | R2 | Serial9/0 | 172.100.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router0 Serial8/0 |
| Router3 | R3 | Serial6/0 | 172.80.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router7 Serial0/0 |
| Router3 | R3 | Serial7/0 | 172.110.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router1 Serial8/0 |
| Router3 | R3 | Serial8/0 | 172.70.0.2 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router2 Serial8/0 |
| Router3 | R3 | Serial9/0 | 172.90.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router0 Serial9/0 |
| Router4 | R4 | GigabitEthernet9/0 | 200.168.10.254 | 255.255.255.0 | /24 | 1 Gb/s | LAN-SiteA | conectada | Switch0 GigabitEthernet0/1 |
| Router4 | R4 | Serial0/0 | 172.20.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router0 Serial7/0 |
| Router5 | R5 | GigabitEthernet9/0 | 200.168.20.254 | 255.255.255.0 | /24 | 1 Gb/s | LAN-SiteC | conectada | Switch1 GigabitEthernet9/1 |
| Router5 | R5 | Serial0/0 | 172.40.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router1 Serial9/0 |
| Router6 | R6 | GigabitEthernet9/0 | 200.168.30.254 | 255.255.255.0 | /24 | 1 Gb/s | LAN-SiteD | conectada | Switch2 GigabitEthernet9/1 |
| Router6 | R6 | Serial0/0 | 172.60.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router2 Serial6/0 |
| Router7 | R7 | GigabitEthernet9/0 | 200.168.40.254 | 255.255.255.0 | /24 | 1 Gb/s | LAN-SiteB | conectada | Switch3 GigabitEthernet9/1 |
| Router7 | R7 | Serial0/0 | 172.80.0.1 | 255.255.0.0 | /16 | 1544 kb/s | — | conectada | Router3 Serial6/0 |

### Portas de switch

_Modo/VLAN vêm da running-config; porta sem 'switchport' explícito é access na VLAN 1._

| Switch | Porta | Banda | Duplex | Modo | VLAN(s) | Situação | Conectado a |
|---|---|---|---|---|---|---|---|
| Switch0 | GigabitEthernet0/1 | 1 Gb/s | full | access | 1 | conectada | Router4 GigabitEthernet9/0 |
| Switch0 | GigabitEthernet7/1 | 100 Mb/s | full | access | 1 | conectada | PC8 FastEthernet0 |
| Switch0 | GigabitEthernet8/1 | 100 Mb/s | full | access | 1 | conectada | PC1 FastEthernet0 |
| Switch0 | GigabitEthernet9/1 | 100 Mb/s | full | access | 1 | conectada | PC0 FastEthernet0 |
| Switch1 | GigabitEthernet0/1 | 100 Mb/s | full | access | 1 | conectada | PC7 FastEthernet0 |
| Switch1 | GigabitEthernet7/1 | 100 Mb/s | full | access | 1 | conectada | PC6 FastEthernet0 |
| Switch1 | GigabitEthernet8/1 | 1 Gb/s | half | access | 1 | sem cabo | — |
| Switch1 | GigabitEthernet9/1 | 1 Gb/s | full | access | 1 | conectada | Router5 GigabitEthernet9/0 |
| Switch2 | GigabitEthernet0/1 | 100 Mb/s | full | access | 1 | conectada | PC5 FastEthernet0 |
| Switch2 | GigabitEthernet7/1 | 100 Mb/s | full | access | 1 | conectada | PC4 FastEthernet0 |
| Switch2 | GigabitEthernet8/1 | 1 Gb/s | half | access | 1 | sem cabo | — |
| Switch2 | GigabitEthernet9/1 | 1 Gb/s | full | access | 1 | conectada | Router6 GigabitEthernet9/0 |
| Switch3 | GigabitEthernet0/1 | 100 Mb/s | full | access | 1 | sem cabo | — |
| Switch3 | GigabitEthernet7/1 | 100 Mb/s | full | access | 1 | conectada | PC3 FastEthernet0 |
| Switch3 | GigabitEthernet8/1 | 100 Mb/s | full | access | 1 | conectada | PC2 FastEthernet0 |
| Switch3 | GigabitEthernet9/1 | 1 Gb/s | full | access | 1 | conectada | Router7 GigabitEthernet9/0 |

### Hosts

_IP vazio com endereçamento DHCP: a concessão não é salva no .pkt._

| Dispositivo | Tipo | Interface | Endereçamento | Gateway | DNS | Rede | Conectado a |
|---|---|---|---|---|---|---|---|
| PC0 | PC | FastEthernet0 | DHCP | 200.168.10.254 | 8.8.8.8 | 200.168.10.0/24 (inferida) | Switch0 GigabitEthernet9/1 |
| PC1 | PC | FastEthernet0 | DHCP | 200.168.10.254 | 8.8.8.8 | 200.168.10.0/24 (inferida) | Switch0 GigabitEthernet8/1 |
| PC2 | PC | FastEthernet0 | DHCP | 200.168.40.254 | 8.8.8.8 | 200.168.40.0/24 (inferida) | Switch3 GigabitEthernet8/1 |
| PC3 | PC | FastEthernet0 | DHCP | 200.168.40.254 | 8.8.8.8 | 200.168.40.0/24 (inferida) | Switch3 GigabitEthernet7/1 |
| PC4 | PC | FastEthernet0 | DHCP | 200.168.30.254 | 8.8.8.8 | 200.168.30.0/24 (inferida) | Switch2 GigabitEthernet7/1 |
| PC5 | PC | FastEthernet0 | DHCP | 200.168.30.254 | 8.8.8.8 | 200.168.30.0/24 (inferida) | Switch2 GigabitEthernet0/1 |
| PC6 | PC | FastEthernet0 | DHCP | 200.168.20.254 | 8.8.8.8 | 200.168.20.0/24 (inferida) | Switch1 GigabitEthernet7/1 |
| PC7 | PC | FastEthernet0 | DHCP | 200.168.20.254 | 8.8.8.8 | 200.168.20.0/24 (inferida) | Switch1 GigabitEthernet0/1 |
| PC8 | PC | FastEthernet0 | DHCP | 200.168.10.254 | 8.8.8.8 | 200.168.10.0/24 (inferida) | Switch0 GigabitEthernet7/1 |

### Enlaces

| # | Dispositivo A | Porta A | Dispositivo B | Porta B | Cabo |
|---|---|---|---|---|---|
| 1 | PC3 | FastEthernet0 | Switch3 | GigabitEthernet7/1 | Direto |
| 2 | PC8 | FastEthernet0 | Switch0 | GigabitEthernet7/1 | Direto |
| 3 | Router0 | Serial6/0 | Router1 | Serial6/0 | Serial |
| 4 | Router0 | Serial7/0 | Router4 | Serial0/0 | Serial |
| 5 | Router0 | Serial8/0 | Router2 | Serial9/0 | Serial |
| 6 | Router1 | Serial7/0 | Router2 | Serial7/0 | Serial |
| 7 | Router1 | Serial9/0 | Router5 | Serial0/0 | Serial |
| 8 | Router2 | Serial6/0 | Router6 | Serial0/0 | Serial |
| 9 | Router2 | Serial8/0 | Router3 | Serial8/0 | Serial |
| 10 | Router3 | Serial7/0 | Router1 | Serial8/0 | Serial |
| 11 | Router3 | Serial9/0 | Router0 | Serial9/0 | Serial |
| 12 | Router5 | GigabitEthernet9/0 | Switch1 | GigabitEthernet9/1 | Direto |
| 13 | Router6 | GigabitEthernet9/0 | Switch2 | GigabitEthernet9/1 | Direto |
| 14 | Router7 | Serial0/0 | Router3 | Serial6/0 | Serial |
| 15 | Switch0 | GigabitEthernet0/1 | Router4 | GigabitEthernet9/0 | Direto |
| 16 | Switch0 | GigabitEthernet8/1 | PC1 | FastEthernet0 | Direto |
| 17 | Switch0 | GigabitEthernet9/1 | PC0 | FastEthernet0 | Direto |
| 18 | Switch1 | GigabitEthernet0/1 | PC7 | FastEthernet0 | Direto |
| 19 | Switch1 | GigabitEthernet7/1 | PC6 | FastEthernet0 | Direto |
| 20 | Switch2 | GigabitEthernet0/1 | PC5 | FastEthernet0 | Direto |
| 21 | Switch2 | GigabitEthernet7/1 | PC4 | FastEthernet0 | Direto |
| 22 | Switch3 | GigabitEthernet8/1 | PC2 | FastEthernet0 | Direto |
| 23 | Switch3 | GigabitEthernet9/1 | Router7 | GigabitEthernet9/0 | Direto |

### Sub-redes

| Rede | Máscara | Faixa de hosts | Interfaces (dispositivo interface – IP) |
|---|---|---|---|
| 172.20.0.0/16 | 255.255.0.0 | 172.20.0.1 – 172.20.255.254 | Router0 Se7/0 – 172.20.0.2; Router4 Se0/0 – 172.20.0.1 |
| 172.30.0.0/16 | 255.255.0.0 | 172.30.0.1 – 172.30.255.254 | Router0 Se6/0 – 172.30.0.1; Router1 Se6/0 – 172.30.0.2 |
| 172.40.0.0/16 | 255.255.0.0 | 172.40.0.1 – 172.40.255.254 | Router1 Se9/0 – 172.40.0.2; Router5 Se0/0 – 172.40.0.1 |
| 172.50.0.0/16 | 255.255.0.0 | 172.50.0.1 – 172.50.255.254 | Router1 Se7/0 – 172.50.0.1; Router2 Se7/0 – 172.50.0.2 |
| 172.60.0.0/16 | 255.255.0.0 | 172.60.0.1 – 172.60.255.254 | Router2 Se6/0 – 172.60.0.2; Router6 Se0/0 – 172.60.0.1 |
| 172.70.0.0/16 | 255.255.0.0 | 172.70.0.1 – 172.70.255.254 | Router2 Se8/0 – 172.70.0.1; Router3 Se8/0 – 172.70.0.2 |
| 172.80.0.0/16 | 255.255.0.0 | 172.80.0.1 – 172.80.255.254 | Router3 Se6/0 – 172.80.0.2; Router7 Se0/0 – 172.80.0.1 |
| 172.90.0.0/16 | 255.255.0.0 | 172.90.0.1 – 172.90.255.254 | Router0 Se9/0 – 172.90.0.2; Router3 Se9/0 – 172.90.0.1 |
| 172.100.0.0/16 | 255.255.0.0 | 172.100.0.1 – 172.100.255.254 | Router0 Se8/0 – 172.100.0.1; Router2 Se9/0 – 172.100.0.2 |
| 172.110.0.0/16 | 255.255.0.0 | 172.110.0.1 – 172.110.255.254 | Router1 Se8/0 – 172.110.0.1; Router3 Se7/0 – 172.110.0.2 |
| 200.168.10.0/24 | 255.255.255.0 | 200.168.10.1 – 200.168.10.254 | Router4 Gi9/0 – 200.168.10.254 |
| 200.168.20.0/24 | 255.255.255.0 | 200.168.20.1 – 200.168.20.254 | Router5 Gi9/0 – 200.168.20.254 |
| 200.168.30.0/24 | 255.255.255.0 | 200.168.30.1 – 200.168.30.254 | Router6 Gi9/0 – 200.168.30.254 |
| 200.168.40.0/24 | 255.255.255.0 | 200.168.40.1 – 200.168.40.254 | Router7 Gi9/0 – 200.168.40.254 |

### VLANs

_Portas em shutdown e trunks não entram na lista de portas access._

| Switch | VLAN | Nome | Portas access |
|---|---|---|---|
| Switch0 | 1 | default | Gi0/1, Gi7/1, Gi8/1, Gi9/1 |
| Switch1 | 1 | default | Gi0/1, Gi7/1, Gi8/1, Gi9/1 |
| Switch2 | 1 | default | Gi0/1, Gi7/1, Gi8/1, Gi9/1 |
| Switch3 | 1 | default | Gi0/1, Gi7/1, Gi8/1, Gi9/1 |

### Protocolos de roteamento

| Dispositivo | Protocolo | Router-ID | Redes anunciadas | Interfaces passivas |
|---|---|---|---|---|
| Router0 | ospf 1 | 1.1.1.1 | 172.0.0.0/8 (área 0) | — |
| Router0 | rip | — | 172.20.0.0; 172.30.0.0; 172.90.0.0; 172.100.0.0 | — |
| Router1 | ospf 1 | 2.2.2.2 | 172.0.0.0/8 (área 0) | — |
| Router1 | rip | — | 172.30.0.0; 172.40.0.0; 172.50.0.0; 172.110.0.0 | — |
| Router2 | ospf 1 | 3.3.3.3 | 172.0.0.0/8 (área 0) | — |
| Router2 | rip | — | 172.50.0.0; 172.60.0.0; 172.70.0.0; 172.100.0.0 | — |
| Router3 | ospf 1 | 4.4.4.4 | 172.0.0.0/8 (área 0) | — |
| Router3 | rip | — | 172.70.0.0; 172.80.0.0; 172.90.0.0; 172.110.0.0 | — |
| Router4 | ospf 1 | 5.5.5.5 | 172.0.0.0/8 (área 0); 200.168.10.0/24 (área 0) | Gi9/0 |
| Router4 | rip | — | 172.20.0.0; 200.168.10.0 | — |
| Router5 | ospf 1 | 6.6.6.6 | 172.0.0.0/8 (área 0); 200.168.20.0/24 (área 0) | Gi9/0 |
| Router5 | rip | — | 172.40.0.0; 200.168.20.0 | — |
| Router6 | ospf 1 | 7.7.7.7 | 172.0.0.0/8 (área 0); 200.168.30.0/24 (área 0) | Gi9/0 |
| Router6 | rip | — | 172.60.0.0; 200.168.30.0 | — |
| Router7 | ospf 1 | 8.8.8.8 | 172.0.0.0/8 (área 0); 200.168.40.0/24 (área 0) | Gi9/0 |
| Router7 | rip | — | 170.80.0.0; 200.168.40.0 | — |

### Pools DHCP (roteadores)

| Dispositivo | Pool | Rede / máscara | Gateway | DNS | Endereços excluídos |
|---|---|---|---|---|---|
| Router4 | REDE_LOCAL_10 | 200.168.10.0 / 255.255.255.0 | 200.168.10.254 | 8.8.8.8 | 200.168.10.1; 200.168.10.2; 200.168.10.3; 200.168.10.254; 200.168.10.1 – 200.168.10.3 |
| Router5 | REDE_LOCAL_20 | 200.168.20.0 / 255.255.255.0 | 200.168.20.254 | 8.8.8.8 | 200.168.20.254 |
| Router6 | REDE_LOCAL_30 | 200.168.30.0 / 255.255.255.0 | 200.168.30.254 | 8.8.8.8 | 200.168.30.254 |
| Router7 | REDE_LOCAL_40 | 200.168.40.0 / 255.255.255.0 | 200.168.40.254 | 8.8.8.8 | 200.168.40.254 |

### Verificações

| # | Observação |
|---|---|
| 1 | Router7: router rip anuncia '170.80.0.0', que não contém nenhuma interface do equipamento. |
