from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

HOST = '127.0.0.1'
PORT = 502
WORD_ORDER = 'big'  # palavra alta primeiro, igual ao servidor


class ClienteModbus:
    """Comunicacao Modbus TCP: conexao, leitura, escrita e conversoes.

    Reutilizada da atividade anterior e estendida com coils e
    leitura/escrita de multiplos bits de um registrador.
    """

    def __init__(self, host=HOST, port=PORT, device_id=1,
                 word_order=WORD_ORDER, timeout=1):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.word_order = word_order
        self.client = ModbusTcpClient(host, port=port, timeout=timeout)

    # ---------- conexao ----------
    def conectar(self):
        if not self.client.connect():
            raise ConnectionError(f"Nao foi possivel conectar em {self.host}:{self.port}")

    def desconectar(self):
        self.client.close()

    @property
    def conectado(self):
        return self.client.connected

    # ---------- coils (bobinas) ----------
    def ler_coils(self, endereco, quantidade=1):
        """Lista de 0/1 com o estado das coils a partir de 'endereco'."""
        try:
            r = self.client.read_coils(
                endereco, count=quantidade, device_id=self.device_id)
        except ModbusException as e:
            raise RuntimeError(f"Falha de comunicacao ao ler coil {endereco}: {e}")
        if r.isError():
            raise RuntimeError(f"Erro ao ler coil {endereco}: {r}")
        # r.bits vem completado ate multiplo de 8: corta no tamanho pedido
        return [int(b) for b in r.bits[:quantidade]]

    def ler_coil(self, endereco):
        return self.ler_coils(endereco, 1)[0]

    def escrever_coil(self, endereco, valor):
        if valor not in (0, 1):
            raise ValueError("Valor da coil deve ser 0 ou 1")
        try:
            r = self.client.write_coil(
                endereco, bool(valor), device_id=self.device_id)
        except ModbusException as e:
            raise RuntimeError(f"Falha de comunicacao ao escrever coil {endereco}: {e}")
        if r.isError():
            raise RuntimeError(f"Erro ao escrever coil {endereco}: {r}")

    def escrever_coils(self, endereco, valores):
        if any(v not in (0, 1) for v in valores):
            raise ValueError("Valores das coils devem ser 0 ou 1")
        try:
            r = self.client.write_coils(
                endereco, [bool(v) for v in valores], device_id=self.device_id)
        except ModbusException as e:
            raise RuntimeError(f"Falha de comunicacao ao escrever coils {endereco}: {e}")
        if r.isError():
            raise RuntimeError(f"Erro ao escrever coils {endereco}: {r}")

    # ---------- registradores brutos ----------
    def ler_registradores(self, endereco, quantidade=1):
        try:
            r = self.client.read_holding_registers(
                endereco, count=quantidade, device_id=self.device_id)
        except ModbusException as e:
            raise RuntimeError(f"Falha de comunicacao ao ler {endereco}: {e}")
        if r.isError():
            raise RuntimeError(f"Erro ao ler {endereco}: {r}")
        return list(r.registers)

    def escrever_registradores(self, endereco, valores):
        if any(not 0 <= v <= 65535 for v in valores):
            raise ValueError("Valor fora do intervalo de 16 bits (0 a 65535)")
        try:
            r = self.client.write_registers(
                endereco, valores, device_id=self.device_id)
        except ModbusException as e:
            raise RuntimeError(f"Falha de comunicacao ao escrever {endereco}: {e}")
        if r.isError():
            raise RuntimeError(f"Erro ao escrever {endereco}: {r}")

    def ler_registrador(self, endereco):
        return self.ler_registradores(endereco, 1)[0]

    def escrever_registrador(self, endereco, valor):
        if not 0 <= valor <= 65535:
            raise ValueError("Valor fora do intervalo de 16 bits (0 a 65535)")
        self.escrever_registradores(endereco, [valor])

    # ---------- inteiro com escala ----------
    def ler_inteiro(self, endereco, div=1):
        """Retorna valor de engenharia = valor recebido / Div."""
        return self.ler_registrador(endereco) / div

    def escrever_inteiro(self, endereco, valor_eng, div=1):
        """Envia valor de engenharia * Div, arredondado."""
        self.escrever_registrador(endereco, int(round(valor_eng * div)))

    def ler_inteiros(self, endereco, quantidade=1, div=1):
        """Varios registradores consecutivos, cada um dividido por Div."""
        return [v / div for v in self.ler_registradores(endereco, quantidade)]

    def escrever_inteiros(self, endereco, valores_eng, div=1):
        """Varios valores de engenharia em registradores consecutivos."""
        self.escrever_registradores(
            endereco, [int(round(v * div)) for v in valores_eng])

    # ---------- float32 em 2 registradores ----------
    def ler_float(self, endereco, div=1):
        """Decodifica float32 primeiro, depois aplica a escala."""
        regs = self.ler_registradores(endereco, 2)
        valor = self.client.convert_from_registers(
            regs, ModbusTcpClient.DATATYPE.FLOAT32, word_order=self.word_order)
        return valor / div

    def escrever_float(self, endereco, valor_eng, div=1):
        """Aplica a escala primeiro, depois converte para registradores."""
        regs = self.client.convert_to_registers(
            valor_eng * div, ModbusTcpClient.DATATYPE.FLOAT32,
            word_order=self.word_order)
        self.escrever_registradores(endereco, regs)

    # ---------- bits de um holding register ----------
    def ler_bits(self, endereco, bit_inicial=0, quantidade=16):
        """Bits de um registrador: indice 0 = menos significativo.

        Sem argumentos extras retorna os 16 bits; com bit_inicial e
        quantidade retorna so a faixa pedida.
        """
        self._validar_faixa(bit_inicial, quantidade)
        valor = self.ler_registrador(endereco)
        return [(valor >> i) & 1 for i in range(bit_inicial, bit_inicial + quantidade)]

    def escrever_bit(self, endereco, bit, valor_bit):
        return self.escrever_bits(endereco, bit, [valor_bit])

    def escrever_bits(self, endereco, bit_inicial, valores):
        """Altera varios bits consecutivos a partir de bit_inicial,
        preservando os demais (leitura -> mascara -> escrita).
        valores[0] vai para bit_inicial, valores[1] para bit_inicial+1...
        """
        self._validar_faixa(bit_inicial, len(valores))
        if any(v not in (0, 1) for v in valores):
            raise ValueError("Valor do bit deve ser 0 ou 1")
        reg = self.ler_registrador(endereco)
        for i, v in enumerate(valores):
            bit = bit_inicial + i
            if v == 1:
                reg |= (1 << bit)
            else:
                reg &= ~(1 << bit)
        self.escrever_registrador(endereco, reg)
        return reg

    @staticmethod
    def _validar_faixa(bit_inicial, quantidade):
        if not 0 <= bit_inicial <= 15:
            raise ValueError("Bit deve ser entre 0 e 15")
        if quantidade < 1 or bit_inicial + quantidade > 16:
            raise ValueError("Faixa de bits deve ficar entre 0 e 15")


# Mapa: (tag, endereco, tipo, Div, unidade)
MAPA = [
    ('temp_r',    700, 'FP', 10,   'C'),
    ('temp_s',    702, 'FP', 10,   'C'),
    ('temp_t',    704, 'FP', 10,   'C'),
    ('temp_carc', 706, 'FP', 10,   'C'),
    ('pressao',   710, 'FP', 1,    'bar'),
    ('vazao',     712, 'FP', 1,    'm3/h'),
    ('freq',      830, '4X', 100,  'Hz'),
    ('corrente',  840, '4X', 10,   'A'),
    ('tensao',    847, '4X', 10,   'V'),
    ('fp',        868, '4X', 1000, ''),
]


def ler_mapa(c):
    for tag, end, tipo, div, un in MAPA:
        v = c.ler_float(end, div) if tipo == 'FP' else c.ler_inteiro(end, div)
        print(f"  {tag:10s} (end {end:4d}) = {v:10.3f} {un}")


if __name__ == '__main__':
    # Demonstracao rapida por chamadas diretas (nao roda ao importar)
    c = ClienteModbus()
    c.conectar()
    print(f"Conectado em {c.host}:{c.port}")
    try:
        print("\n=== Mapa ===")
        ler_mapa(c)

        print("\n=== Coils 0-3 ===")
        c.escrever_coils(0, [1, 0, 1, 1])
        print(f"  coils: {c.ler_coils(0, 4)}")

        print("\n=== Float (1302) ===")
        c.escrever_float(1302, 62.37)
        print(f"  lido = {c.ler_float(1302):.4f}")

        print("\n=== Multiplos bits (1328) ===")
        c.escrever_registrador(1328, 0b0000000000100101)
        print(f"  antes:  {c.ler_registrador(1328):016b}")
        c.escrever_bits(1328, 8, [1, 1, 0, 1])  # bits 8..11
        print(f"  depois: {c.ler_registrador(1328):016b}")
        print(f"  bits 8..11: {c.ler_bits(1328, 8, 4)}")
    finally:
        c.desconectar()
        print("\nDesconectado.")
