# Relatório de rede — cenario_03_equipe_08_Lab_SD

Origem: `cenario_03_equipe_08_Lab_SD.xml` · Packet Tracer 9.0.1.0858 · gerado em 11/11/2026 14:28

### Resumo

| Item | Quantidade |
|---|---|
| Versão do Packet Tracer | 9.0.1.0858 |
| Roteador(s) | 1 |
| Switch(s) | 2 |
| PC(s) | 10 |
| Enlaces (cabos) | 14 |
| Sub-redes IPv4 distintas | 2 |
| Interfaces com IP | 4 |

### Dispositivos

| Nome | Tipo | Modelo | Hostname (config) | Nº de série | Interfaces físicas | Gateway padrão | DNS |
|---|---|---|---|---|---|---|---|
| Router0 | Roteador | 1941 | Router_TI_CBCC_2026 | FTX1524VHFC- | 2 | — | — |
| Switch_01 | Switch | 2960-24TT | Switch01 | CAT1010HH1P- | 26 | — | — |
| Switch_02 | Switch | 2960-24TT | Switch02 | CAT10108KSQ- | 26 | — | — |
| Laptop0 | Laptop | Laptop-PT | — | PTT0810Y0O3 | 1 | — | — |
| Laptop1 | Laptop | Laptop-PT | PC | PTT08103F3F | 1 | — | — |
| Laptop2 | Laptop | Laptop-PT | PC | PTT08103MRC | 1 | — | — |
| Laptop3 | Laptop | Laptop-PT | — | PTT08103DDW | 1 | 172.16.255.254 | 192.168.0.1 |
| Light Weight Access Point0 | LightWeightAccessPoint | LAP-PT | AP00d0.d370.6d01 | PTT0810VUT7 | 0 | — | 192.168.0.1 |
| Light Weight Access Point1 | LightWeightAccessPoint | LAP-PT | AP0001.6351.2301 | PTT081025Q9 | 0 | — | 192.168.0.1 |
| PC0 | PC | PC-PT | PC | PTT08109F9Y | 1 | 192.168.0.254 | 192.168.0.1 |
| PC1 | PC | PC-PT | PC | PTT08106400 | 1 | 192.168.0.254 | 192.168.0.1 |
| PC2 | PC | PC-PT | — | PTT0810I795 | 1 | 172.16.255.254 | 192.168.0.1 |
| PC3 | PC | PC-PT | PC | PTT0810QKE4 | 1 | 172.16.255.254 | 192.168.0.1 |
| Power Distribution Device0 | Power Distribution Device | 2Power | — | PTT08107F7N | 0 | — | — |
| Printer0 | Impressora | Printer-PT | — | PTT0810U17D | 1 | 192.168.0.254 | 192.168.0.1 |
| Server0 | Servidor | Server-PT | PC | PTT0810VI50 | 1 | 192.168.0.254 | 192.168.0.1 |
| Smartphone0 | Pda | SMARTPHONE-PT | PC | PTT08106IDB | 0 | 192.168.0.254 | 192.168.0.1 |
| Tablet PC0 | TabletPC | TabletPC-PT | PC | PTT0810ESD3 | 0 | 172.16.255.254 | 192.168.0.1 |
| Wireless LAN Controller0 | WirelessLanController | WLC-PT | WLC | PTT081085S6- | 0 | — | 192.168.0.1 |
| Wireless LAN Controller1 | WirelessLanController | WLC-PT | WLC | PTT0810YF60- | 0 | — | — |

### Interfaces de roteadores e SVIs

| Dispositivo | Hostname | Interface | IP | Máscara | Prefixo | Banda | Descrição | Situação | Conectado a |
|---|---|---|---|---|---|---|---|---|---|
| Router0 | Router_TI_CBCC_2026 | GigabitEthernet0/0 | 192.168.0.254 | 255.255.255.0 | /24 | 100 Mb/s | — | conectada | Switch_01 FastEthernet0/1 |
| Router0 | Router_TI_CBCC_2026 | GigabitEthernet0/1 | 172.16.255.254 | 255.255.0.0 | /16 | 100 Mb/s | — | conectada | Switch_02 FastEthernet0/1 |
| Switch_01 | Switch01 | Vlan1 | 192.168.0.200 | 255.255.255.0 | /24 | 100 Mb/s | — | sem cabo | — |
| Switch_02 | Switch02 | Vlan1 | 172.16.255.200 | 255.255.0.0 | /16 | 100 Mb/s | — | sem cabo | — |

### Portas de switch

_Modo/VLAN vêm da running-config; porta sem 'switchport' explícito é access na VLAN 1._

| Switch | Porta | Banda | Duplex | Modo | VLAN(s) | Situação | Conectado a |
|---|---|---|---|---|---|---|---|
| Switch_01 | FastEthernet0/1 | 100 Mb/s | full | access | 1 | conectada | Router0 GigabitEthernet0/0 |
| Switch_01 | FastEthernet0/2 | 100 Mb/s | full | access | 1 | conectada | Server0 FastEthernet0 |
| Switch_01 | FastEthernet0/3 | 100 Mb/s | full | access | 1 | conectada | PC0 FastEthernet0 |
| Switch_01 | FastEthernet0/4 | 100 Mb/s | full | access | 1 | conectada | PC1 FastEthernet0 |
| Switch_01 | FastEthernet0/5 | 100 Mb/s | full | access | 1 | conectada | Light Weight Access Point0 GigabitEthernet0 |
| Switch_01 | FastEthernet0/6 | 100 Mb/s | full | access | 1 | conectada | Wireless LAN Controller0 GigabitEthernet0 |
| Switch_01 | FastEthernet0/7 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/8 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/9 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/10 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/11 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/12 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/13 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/14 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/15 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/16 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/17 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/18 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/19 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/20 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/21 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/22 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/23 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | FastEthernet0/24 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_01 | GigabitEthernet0/1 | 1 Gb/s | half | access | 1 | sem cabo | — |
| Switch_01 | GigabitEthernet0/2 | 1 Gb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/1 | 100 Mb/s | full | access | 1 | conectada | Router0 GigabitEthernet0/1 |
| Switch_02 | FastEthernet0/2 | 100 Mb/s | full | access | 1 | conectada | PC2 FastEthernet0 |
| Switch_02 | FastEthernet0/3 | 100 Mb/s | full | access | 1 | conectada | PC3 FastEthernet0 |
| Switch_02 | FastEthernet0/4 | 100 Mb/s | full | access | 1 | conectada | Light Weight Access Point1 GigabitEthernet0 |
| Switch_02 | FastEthernet0/5 | 100 Mb/s | full | access | 1 | conectada | Wireless LAN Controller1 GigabitEthernet0 |
| Switch_02 | FastEthernet0/6 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/7 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/8 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/9 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/10 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/11 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/12 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/13 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/14 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/15 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/16 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/17 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/18 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/19 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/20 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/21 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/22 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/23 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | FastEthernet0/24 | 100 Mb/s | half | access | 1 | sem cabo | — |
| Switch_02 | GigabitEthernet0/1 | 1 Gb/s | half | access | 1 | sem cabo | — |
| Switch_02 | GigabitEthernet0/2 | 1 Gb/s | half | access | 1 | sem cabo | — |

### Hosts

_IP vazio com endereçamento DHCP: a concessão não é salva no .pkt._

| Dispositivo | Tipo | Interface | Endereçamento | Gateway | DNS | Rede | Conectado a |
|---|---|---|---|---|---|---|---|
| Laptop0 | Laptop | FastEthernet0 | DHCP | — | — | — | Switch_01 Console |
| Laptop1 | Laptop | FastEthernet0 | DHCP | — | — | — | Switch_02 Console |
| Laptop2 | Laptop | FastEthernet0 | DHCP | — | — | — | Router0 Console |
| Laptop3 | Laptop | Wireless0 | DHCP | 172.16.255.254 | 192.168.0.1 | 172.16.0.0/16 (inferida) | — |
| PC0 | PC | FastEthernet0 | DHCP | 192.168.0.254 | 192.168.0.1 | 192.168.0.0/24 (inferida) | Switch_01 FastEthernet0/3 |
| PC1 | PC | FastEthernet0 | DHCP | 192.168.0.254 | 192.168.0.1 | 192.168.0.0/24 (inferida) | Switch_01 FastEthernet0/4 |
| PC2 | PC | FastEthernet0 | DHCP | 172.16.255.254 | 192.168.0.1 | 172.16.0.0/16 (inferida) | Switch_02 FastEthernet0/2 |
| PC3 | PC | FastEthernet0 | DHCP | 172.16.255.254 | 192.168.0.1 | 172.16.0.0/16 (inferida) | Switch_02 FastEthernet0/3 |
| Printer0 | Impressora | Wireless0 | DHCP | 192.168.0.254 | 192.168.0.1 | 192.168.0.0/24 (inferida) | — |
| Server0 | Servidor | FastEthernet0 | 192.168.0.1/24 | 192.168.0.254 | 192.168.0.1 | 192.168.0.0/24 | Switch_01 FastEthernet0/2 |

### Enlaces

| # | Dispositivo A | Porta A | Dispositivo B | Porta B | Cabo |
|---|---|---|---|---|---|
| 1 | Laptop2 | FastEthernet0 | Router0 | Console | eRollOver |
| 2 | Switch_01 | Console | Laptop0 | FastEthernet0 | eRollOver |
| 3 | Switch_01 | FastEthernet0/1 | Router0 | GigabitEthernet0/0 | Direto |
| 4 | Router0 | GigabitEthernet0/1 | Switch_02 | FastEthernet0/1 | Direto |
| 5 | Server0 | FastEthernet0 | Switch_01 | FastEthernet0/2 | Direto |
| 6 | PC0 | FastEthernet0 | Switch_01 | FastEthernet0/3 | Direto |
| 7 | PC1 | FastEthernet0 | Switch_01 | FastEthernet0/4 | Direto |
| 8 | Switch_02 | Console | Laptop1 | FastEthernet0 | eRollOver |
| 9 | Switch_02 | FastEthernet0/4 | Light Weight Access Point1 | GigabitEthernet0 | Direto |
| 10 | Switch_02 | FastEthernet0/5 | Wireless LAN Controller1 | GigabitEthernet0 | Cruzado |
| 11 | Light Weight Access Point0 | GigabitEthernet0 | Switch_01 | FastEthernet0/5 | Direto |
| 12 | Wireless LAN Controller0 | GigabitEthernet0 | Switch_01 | FastEthernet0/6 | Cruzado |
| 13 | PC2 | FastEthernet0 | Switch_02 | FastEthernet0/2 | Direto |
| 14 | PC3 | FastEthernet0 | Switch_02 | FastEthernet0/3 | Direto |

### Sub-redes

| Rede | Máscara | Faixa de hosts | Interfaces (dispositivo interface – IP) |
|---|---|---|---|
| 172.16.0.0/16 | 255.255.0.0 | 172.16.0.1 – 172.16.255.254 | Router0 Gi0/1 – 172.16.255.254; Switch_02 Vlan1 – 172.16.255.200 |
| 192.168.0.0/24 | 255.255.255.0 | 192.168.0.1 – 192.168.0.254 | Router0 Gi0/0 – 192.168.0.254; Switch_01 Vlan1 – 192.168.0.200 |

### VLANs

_Portas em shutdown e trunks não entram na lista de portas access._

| Switch | VLAN | Nome | Portas access |
|---|---|---|---|
| Switch_01 | 1 | default | Fa0/1, Fa0/2, Fa0/3, Fa0/4, Fa0/5, Fa0/6, Fa0/7, Fa0/8, Fa0/9, Fa0/10, Fa0/11, Fa0/12, Fa0/13, Fa0/14, Fa0/15, Fa0/16, Fa0/17, Fa0/18, Fa0/19, Fa0/20, Fa0/21, Fa0/22, Fa0/23, Fa0/24, Gi0/1, Gi0/2 |
| Switch_02 | 1 | default | Fa0/1, Fa0/2, Fa0/3, Fa0/4, Fa0/5, Fa0/6, Fa0/7, Fa0/8, Fa0/9, Fa0/10, Fa0/11, Fa0/12, Fa0/13, Fa0/14, Fa0/15, Fa0/16, Fa0/17, Fa0/18, Fa0/19, Fa0/20, Fa0/21, Fa0/22, Fa0/23, Fa0/24, Gi0/1, Gi0/2 |

### Pools DHCP (roteadores)

| Dispositivo | Pool | Rede / máscara | Gateway | DNS | Endereços excluídos |
|---|---|---|---|---|---|
| Router0 | REDE192 | 192.168.0.0 / 255.255.255.0 | 192.168.0.254 | 192.168.0.1 | 192.168.0.254; 192.168.0.200; 192.168.0.1; 172.16.255.200; 172.16.255.254 |
| Router0 | REDE172 | 172.16.0.0 / 255.255.0.0 | 172.16.255.254 | 192.168.0.1 | 192.168.0.254; 192.168.0.200; 192.168.0.1; 172.16.255.200; 172.16.255.254 |
