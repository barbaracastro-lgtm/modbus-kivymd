"""Interface grafica (KivyMD) do cliente Modbus TCP.

A interface so le os campos, chama os metodos da classe ClienteModbus
e mostra os resultados. Toda a comunicacao, leitura, escrita e conversao
de dados fica em cliente/cliente_modbus.py.
"""
import os
from datetime import datetime

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivymd.app import MDApp

from cliente.cliente_modbus import ClienteModbus

KV = os.path.join(os.path.dirname(__file__), 'modbus_app.kv')

AJUDA = {
    'coil': "Coil: escreva 0 ou 1 (ou lista '1;0;1' / '1,0,1' para várias coils). "
            "Quantidade = nº de coils lidas.",
    'hr': "Holding Register (16 bits): valor em unidade de engenharia, "
          "enviado = valor × Div (lista '10;20' escreve vários). "
          "Quantidade = nº de registradores lidos.",
    'float': "Float32 em 2 registradores (word order big): "
             "enviado = valor × Div. Ex.: 62,37",
    'bits': "Bits do registrador (bit 0 = menos significativo): lê 'Quantidade' "
            "bits a partir do 'Bit inicial'. Escrita: 1, 0 ou lista '1;0;1'.",
}

MAX_LINHAS_LOG = 200


class ModbusApp(MDApp):
    cor_ok = (0.10, 0.55, 0.25, 1)
    cor_erro = (0.75, 0.15, 0.15, 1)

    def build(self):
        self.title = 'Cliente Modbus TCP - KivyMD'
        self.theme_cls.theme_style = 'Light'
        self.theme_cls.primary_palette = 'Teal'
        Window.size = (980, 760)

        self.cliente = None      # instancia de ClienteModbus
        self.tipo = 'hr'         # tipo de dado selecionado
        self.evento = None       # evento do Clock (leitura recorrente)
        self.linhas_log = []
        return Builder.load_file(KV)

    def on_start(self):
        self.mudar_tipo(self.tipo)

    def on_stop(self):
        self.parar_recorrente()
        if self.cliente:
            self.cliente.desconectar()

    # ------------------------------------------------------------ conexao
    def conectar(self):
        ids = self.root.ids
        if self.cliente and self.cliente.conectado:
            self.parar_recorrente()
            self.cliente.desconectar()
            self.cliente = None
            self._status(False, 'Desconectado')
            self.log('Desconectado.')
            return
        try:
            host = ids.campo_ip.text.strip()
            porta = self._inteiro(ids.campo_porta.text, 'Porta')
            if not host:
                raise ValueError('Informe o IP do servidor')
            cliente = ClienteModbus(host, porta)
            cliente.conectar()
        except (ValueError, ConnectionError) as e:
            self._status(False, 'Falha na conexão')
            self.erro(e)
            return
        self.cliente = cliente
        self._status(True, f'Conectado a {host}:{porta}')
        self.log(f'Conectado a {host}:{porta}')

    # ------------------------------------------------------------ tipo
    def mudar_tipo(self, tipo):
        self.tipo = tipo
        if self.root:   # durante a construcao da tela o root ainda nao existe
            self.root.ids.lbl_ajuda.text = AJUDA[tipo]

    # ------------------------------------------------------------ leitura
    def ler(self):
        if self.evento:              # o botao vira "Parar" durante a recorrente
            self.parar_recorrente()
            return
        if not self._checar_conexao():
            return
        if not self.root.ids.chk_recorrente.active:
            self._ler_uma_vez()
            return
        try:
            intervalo = self._real(self.root.ids.campo_intervalo.text, 'Intervalo')
            if intervalo < 0.2:
                raise ValueError('Intervalo mínimo: 0,2 s')
        except ValueError as e:
            self.erro(e)
            return
        if self._ler_uma_vez():
            self.evento = Clock.schedule_interval(self._tick, intervalo)
            self.root.ids.txt_ler.text = 'Parar leitura'
            self.log(f'Leitura recorrente a cada {intervalo:g} s')

    def _tick(self, dt):
        if not self._ler_uma_vez():
            self.parar_recorrente()

    def parar_recorrente(self):
        if self.evento:
            self.evento.cancel()
            self.evento = None
            self.log('Leitura recorrente parada.')
        if self.root:
            self.root.ids.txt_ler.text = 'Ler'

    def _ler_uma_vez(self):
        """Faz uma leitura conforme o tipo. Retorna True se deu certo."""
        ids = self.root.ids
        c = self.cliente
        try:
            end = self._inteiro(ids.campo_endereco.text, 'Endereço')
            if self.tipo == 'coil':
                qtd = self._inteiro(ids.campo_qtd.text, 'Quantidade')
                valores = c.ler_coils(end, qtd)
                resumo = self._lista(valores)
                detalhe = '   '.join(f'coil {end + i}: {v}' for i, v in enumerate(valores))

            elif self.tipo == 'hr':
                qtd = self._inteiro(ids.campo_qtd.text, 'Quantidade')
                div = self._real(ids.campo_div.text, 'Div')
                valores = c.ler_inteiros(end, qtd, div)
                resumo = self._lista(valores)
                detalhe = '   '.join(f'HR {end + i}: {v:g}' for i, v in enumerate(valores))
                detalhe += f'   (Div = {div:g})'

            elif self.tipo == 'float':
                div = self._real(ids.campo_div.text, 'Div')
                valor = c.ler_float(end, div)
                resumo = f'{valor:.4f}'
                detalhe = f'float32 em {end}-{end + 1}, Div = {div:g}'

            else:  # bits
                bit = self._inteiro(ids.campo_bit.text, 'Bit inicial')
                qtd = self._inteiro(ids.campo_qtd.text, 'Quantidade')
                bits = c.ler_bits(end, bit, qtd)
                reg = c.ler_registrador(end)
                resumo = self._lista(bits)
                detalhe = (f'Registrador {end} = {reg} = {reg:016b}b\n'
                           + '   '.join(f'bit {bit + i}: {b}' for i, b in enumerate(bits)))
        except (ValueError, RuntimeError, ConnectionError) as e:
            self.erro(e)
            return False

        ids.lbl_resultado.text = resumo
        ids.lbl_detalhe.text = detalhe
        self.log(f'Leitura [{self.tipo}] {end}: {resumo}')
        return True

    # ------------------------------------------------------------ escrita
    def escrever(self):
        if not self._checar_conexao():
            return
        ids = self.root.ids
        c = self.cliente
        try:
            end = self._inteiro(ids.campo_endereco.text, 'Endereço')
            texto = ids.campo_valor.text

            if self.tipo == 'coil':
                valores = [self._inteiro(v, 'Valor') for v in self._separar(texto.replace(',', ' '))]
                if len(valores) == 1:
                    c.escrever_coil(end, valores[0])
                else:
                    c.escrever_coils(end, valores)
                msg = f'coil {end}: {self._lista(valores)}'

            elif self.tipo == 'hr':
                div = self._real(ids.campo_div.text, 'Div')
                valores = [self._real(v, 'Valor') for v in self._separar(texto)]
                if len(valores) == 1:
                    c.escrever_inteiro(end, valores[0], div)
                else:
                    c.escrever_inteiros(end, valores, div)
                msg = f'HR {end}: {self._lista(valores)} (Div = {div:g})'

            elif self.tipo == 'float':
                div = self._real(ids.campo_div.text, 'Div')
                valor = self._real(texto, 'Valor')
                c.escrever_float(end, valor, div)
                msg = f'float {end}: {valor:g} (Div = {div:g})'

            else:  # bits
                bit = self._inteiro(ids.campo_bit.text, 'Bit inicial')
                valores = [self._inteiro(v, 'Valor') for v in self._separar(texto.replace(',', ' '))]
                reg = c.escrever_bits(end, bit, valores)
                msg = f'bits {bit}..{bit + len(valores) - 1} de {end} -> {reg:016b}b'
        except (ValueError, RuntimeError, ConnectionError) as e:
            self.erro(e)
            return

        self.log(f'Escrita {msg}')
        if not self.evento:       # confirma lendo de volta
            self._ler_uma_vez()

    # ------------------------------------------------------------ auxiliares de tela
    def _checar_conexao(self):
        if self.cliente is None:
            self.erro('Conecte-se ao servidor primeiro')
            return False
        return True

    def _status(self, ok, texto):
        lbl = self.root.ids.lbl_status
        lbl.text = texto
        lbl.text_color = self.cor_ok if ok else self.cor_erro
        self.root.ids.txt_conectar.text = 'Desconectar' if ok else 'Conectar'

    def erro(self, e):
        self.root.ids.lbl_resultado.text = 'Erro'
        self.root.ids.lbl_detalhe.text = str(e)
        self.log(f'ERRO: {e}')

    def log(self, texto):
        hora = datetime.now().strftime('%H:%M:%S')
        self.linhas_log.insert(0, f'[{hora}] {texto}')
        del self.linhas_log[MAX_LINHAS_LOG:]
        self.root.ids.lbl_log.text = '\n'.join(self.linhas_log)

    # ------------------------------------------------------------ leitura dos campos de texto
    @staticmethod
    def _separar(texto):
        partes = texto.replace(';', ' ').split()
        if not partes:
            raise ValueError('Informe o valor a escrever')
        return partes

    @staticmethod
    def _inteiro(texto, nome):
        try:
            return int(texto.strip())
        except ValueError:
            raise ValueError(f'{nome} inválido: "{texto}"') from None

    @staticmethod
    def _real(texto, nome):
        try:
            return float(texto.strip().replace(',', '.'))
        except ValueError:
            raise ValueError(f'{nome} inválido: "{texto}"') from None

    @staticmethod
    def _lista(valores):
        txt = [f'{v:g}' if isinstance(v, float) else str(v) for v in valores]
        return txt[0] if len(txt) == 1 else '[' + ', '.join(txt) + ']'


def main():
    ModbusApp().run()


if __name__ == '__main__':
    main()
