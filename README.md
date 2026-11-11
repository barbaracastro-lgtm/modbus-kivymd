# Cliente Modbus TCP com interface gráfica (KivyMD)

Aplicação gráfica em Python/KivyMD para **ler e escrever dados em um servidor Modbus TCP**:
coils, holding registers, valores float32 e bits (individuais ou múltiplos) de um registrador,
com leitura única ou recorrente (via `kivy.clock.Clock`).

Disciplina: ENE118 – Informática Industrial (UFJF)

Barbara Castro – matrícula 202169030B – barbara.castro@estudante.ufjf.br – GitHub: [barbaracastro-lgtm](https://github.com/barbaracastro-lgtm)

## Estrutura

```
main.py                     # ponto de entrada da interface gráfica
interface/
    app.py                  # interface (KivyMD): só lê os campos e chama a classe Modbus
    modbus_app.kv           # layout da tela (linguagem KV)
cliente/
    cliente_modbus.py       # classe ClienteModbus: conexão, leitura, escrita e conversões
servidor/
    servidor_modbus.py      # servidor Modbus TCP de teste (emulação de bancada de bombeamento)
requirements.txt
.gitignore
```

### Separação de responsabilidades

- `cliente/cliente_modbus.py` (classe `ClienteModbus`, reutilizada da atividade anterior):
  contém **apenas** comunicação, leitura, escrita e conversão de dados (float32, escala `Div`, bits).
  Foi estendida com `ler_coils`, `escrever_coil(s)`, `ler_inteiros`, `escrever_inteiros`,
  `ler_bits(endereco, bit_inicial, quantidade)` e `escrever_bits(endereco, bit_inicial, valores)`.
- `interface/app.py`: apenas lê os campos da tela, chama os métodos da classe e mostra o resultado.
  Não acessa o pymodbus diretamente.

## Instalação (Windows)

Requer Python 3.10 a 3.14 (Kivy ainda não tem versão para 3.15). Na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(Linux/macOS: `source .venv/bin/activate`.)

## Execução (a partir da raiz)

Terminal 1 – servidor de teste:

```powershell
python -m servidor.servidor_modbus
```

Por padrão escuta em `127.0.0.1:502`. Para outro IP/porta:
`python -m servidor.servidor_modbus --host 0.0.0.0 --port 5020`.

Terminal 2 – interface gráfica:

```powershell
python main.py
```

Demonstração da classe sem interface (opcional): `python -m cliente.cliente_modbus`.

### Testando com servidor externo

Qualquer servidor Modbus TCP funciona (CLP real, ModRSsim2, Modbus Slave, etc.).
Basta digitar o IP e a porta dele na tela e usar os endereços do mapa desse equipamento.
O `device_id` (unit id) padrão é 1.

## Como usar a interface

1. Digite **IP** e **Porta** e clique em **Conectar** (o botão vira **Desconectar**).
2. Escolha o tipo de dado (checkbox): **Coil**, **Holding Register**, **Float** ou **Bits do registrador**.
3. Preencha **Endereço** (endereço direto, sem prefixo 4xxxx) e os demais campos conforme o tipo:

| Tipo | Leitura | Escrita (campo *Valor*) | Campos usados |
|---|---|---|---|
| Coil | `Quantidade` coils a partir do endereço | `1` ou `0`; lista `1;0;1` escreve várias | Endereço, Quantidade |
| Holding Register | `Quantidade` registradores, cada um ÷ Div | valor de engenharia (enviado = valor × Div, arredondado); lista `10;20` escreve vários | Endereço, Div, Quantidade |
| Float | float32 em 2 registradores, ÷ Div | valor de engenharia, ex.: `62,37` | Endereço, Div |
| Bits | `Quantidade` bits a partir do `Bit inicial` | `1`, `0` ou lista `1;0;1` (aplicada a partir do Bit inicial, preservando os outros bits) | Endereço, Bit inicial, Quantidade |

4. **Ler**: leitura única. Com **Leitura recorrente** marcada, lê a cada *Intervalo (s)*
   usando `Clock.schedule_interval`; o botão vira **Parar leitura** (desmarcar a checkbox também para).
5. **Escrever**: envia o valor e lê de volta para confirmar.

Erros de conexão, respostas de erro do servidor e entradas inválidas aparecem na área de resultado e no histórico.

## Mapa do servidor de teste

Ordem de palavras dos floats: **big** (palavra alta primeiro), igual no cliente e no servidor.
Conversão: leitura → valor de engenharia = valor recebido / Div; escrita → valor enviado = valor de engenharia × Div.

| Tag | Descrição | Tipo | Endereço | Regs | Bit | Div | Mult. (1/Div) | Unidade |
|---|---|---|---|---|---|---|---|---|
| temp_r | Temperatura R | FP | 700 | 2 | – | 10 | 0,1 | °C |
| temp_s | Temperatura S | FP | 702 | 2 | – | 10 | 0,1 | °C |
| temp_t | Temperatura T | FP | 704 | 2 | – | 10 | 0,1 | °C |
| temp_carc | Temperatura carcaça | FP | 706 | 2 | – | 10 | 0,1 | °C |
| pressao | Pressão | FP | 710 | 2 | – | 1 | 1 | bar |
| vazao | Vazão | FP | 712 | 2 | – | 1 | 1 | m³/h |
| freq | Frequência | 4X | 830 | 1 | – | 100 | 0,01 | Hz |
| corrente | Corrente R | 4X | 840 | 1 | – | 10 | 0,1 | A |
| tensao | Tensão R-S | 4X | 847 | 1 | – | 10 | 0,1 | V |
| fp | Fator de potência | 4X | 868 | 1 | – | 1000 | 0,001 | – |
| sp_pid | Setpoint de vazão (escrito pelo cliente) | FP | 1302 | 2 | – | 1 | 1 | m³/h |
| habilita | Habilita motor (escrito pelo cliente) | 4X/bit | 1328 | 1 | 6 | 1 | 1 | – |
| liga_motor | Liga motor (escrito pelo cliente) | Coil | 0 | – | – | – | – | – |
| alarme_temp | Temp. carcaça > 75 °C (escrito pelo servidor) | Coil | 10 | – | – | – | – | – |

**Simulação:** a cada 2 s as medições variam aleatoriamente dentro de limites pequenos.
Quando o bit 6 de 1328 **ou** a coil 0 está em 1, a vazão (712) se aproxima gradualmente do setpoint (1302);
caso contrário, permanece constante. O servidor só lê 1302, 1328 e a coil 0 — nunca sobrescreve comandos do cliente.

## Roteiro rápido de teste

| O que testar | Tipo | Endereço | Outros campos | Ação |
|---|---|---|---|---|
| Inteiro com escala | Holding Register | 830 | Div = 100 | Ler → ~60 Hz |
| Float | Float | 1302 | Div = 1, Valor = 62,37 | Escrever |
| Ligar o motor (bit) | Bits | 1328 | Bit inicial = 6, Valor = 1 | Escrever |
| Ligar o motor (coil) | Coil | 0 | Valor = 1 | Escrever |
| Ver a vazão subir | Float | 712 | Div = 1, Leitura recorrente | Ler |
| Vários bits | Bits | 1328 | Bit inicial = 8, Quantidade = 4, Valor = 1;1;0;1 | Escrever |
