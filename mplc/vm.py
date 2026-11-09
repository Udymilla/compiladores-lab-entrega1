"""Maquina virtual de pilha para o bytecode textual MPLB."""
import json
from decimal import Decimal, DivisionByZero, InvalidOperation

from mplc.erros import ErroMPL


LIMITE_CHAMADAS = 1000


class Funcao:
    def __init__(self, cabecalho):
        self.nome = cabecalho['name']
        self.tipo_retorno = cabecalho['return']
        self.parametros = cabecalho['params']
        self.tipos_locais = cabecalho['locals']
        self.codigo = []
        self.rotulos = {}


class Quadro:
    """Registro de ativacao de uma chamada."""
    def __init__(self, funcao, argumentos):
        self.funcao = funcao
        self.ip = 0
        self.locais = {}
        self.temporarios = {}
        self.pilha = []
        for (slot, _tipo, _nome), valor in zip(funcao.parametros, argumentos):
            self.locais[slot] = valor


def erro(linha, mensagem):
    raise ErroMPL('execucao', linha or 1, 1, mensagem)


def ler_programa(texto):
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != 'MPLB 1':
        erro(1, 'arquivo MPLB invalido')
    funcoes = {}
    atual = None
    try:
        for numero, linha in enumerate(linhas[1:], 2):
            if not linha.strip():
                continue
            if linha.startswith('FUNCTION '):
                if atual is not None:
                    erro(numero, 'FUNCTION antes de END')
                atual = Funcao(json.loads(linha[len('FUNCTION '):]))
                if atual.nome in funcoes:
                    erro(numero, 'funcao duplicada no MPLB')
                funcoes[atual.nome] = atual
            elif linha == 'END':
                if atual is None:
                    erro(numero, 'END sem FUNCTION')
                atual = None
            else:
                if atual is None:
                    erro(numero, 'instrucao fora de funcao')
                inst = json.loads(linha)
                if inst.get('op') == 'LABEL':
                    atual.rotulos[inst['name']] = len(atual.codigo)
                atual.codigo.append(inst)
    except ErroMPL:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        erro(1, f'arquivo MPLB invalido: {exc}')
    if atual is not None:
        erro(1, 'faltou END no arquivo MPLB')
    return funcoes


def executar(texto_mplb, saida):
    """Executa o bytecode e escreve os valores de PRINT em ``saida``."""
    funcoes = ler_programa(texto_mplb)
    if 'principal' not in funcoes:
        erro(1, 'funcao principal ausente')

    chamadas = [Quadro(funcoes['principal'], [])]
    while chamadas:
        quadro = chamadas[-1]
        if quadro.ip >= len(quadro.funcao.codigo):
            chamadas.pop()
            continue

        inst = quadro.funcao.codigo[quadro.ip]
        quadro.ip += 1
        op = inst.get('op')
        linha = inst.get('line', 1)

        try:
            if op == 'LABEL':
                continue
            if op == 'PUSH_CONST':
                quadro.pilha.append(valor_constante(inst['value'], inst['type']))
            elif op == 'PUSH_DEFAULT':
                quadro.pilha.append(valor_padrao(inst['type']))
            elif op == 'LOAD_LOCAL':
                quadro.pilha.append(quadro.locais[inst['name']])
            elif op == 'STORE_LOCAL':
                quadro.locais[inst['name']] = quadro.pilha.pop()
            elif op == 'LOAD_TEMP':
                quadro.pilha.append(quadro.temporarios[inst['name']])
            elif op == 'STORE_TEMP':
                quadro.temporarios[inst['name']] = quadro.pilha.pop()
            elif op == 'TO_REAL':
                quadro.pilha.append(Decimal(quadro.pilha.pop()))
            elif op == 'UNARY':
                valor = quadro.pilha.pop()
                quadro.pilha.append(aplicar_unario(inst['operator'], valor))
            elif op == 'BINARY':
                direita = quadro.pilha.pop()
                esquerda = quadro.pilha.pop()
                quadro.pilha.append(
                    aplicar_binario(inst['operator'], esquerda, direita,
                                    inst.get('type'), linha))
            elif op == 'PRINT':
                valor = quadro.pilha.pop()
                saida.write(formatar(valor, inst['type']) + '\n')
            elif op == 'POP':
                quadro.pilha.pop()
            elif op == 'JUMP':
                quadro.ip = alvo_rotulo(quadro.funcao, inst['target'], linha)
            elif op == 'JUMP_FALSE':
                condicao = quadro.pilha.pop()
                if not condicao:
                    quadro.ip = alvo_rotulo(quadro.funcao, inst['target'], linha)
            elif op == 'CALL':
                nome = inst['name']
                if nome not in funcoes:
                    erro(linha, f'funcao {nome!r} ausente no MPLB')
                argc = inst['argc']
                argumentos = [quadro.pilha.pop() for _ in range(argc)][::-1]
                if len(chamadas) >= LIMITE_CHAMADAS:
                    erro(linha, 'estouro de pilha')
                chamadas.append(Quadro(funcoes[nome], argumentos))
            elif op == 'RETURN':
                tem_valor = inst.get('has_value')
                valor = quadro.pilha.pop() if tem_valor else None
                chamadas.pop()
                if chamadas and tem_valor:
                    chamadas[-1].pilha.append(valor)
            else:
                erro(linha, f'instrucao desconhecida: {op}')
        except ErroMPL:
            raise
        except (KeyError, IndexError, TypeError, InvalidOperation) as exc:
            erro(linha, f'bytecode invalido: {exc}')


def valor_constante(valor, tipo):
    if tipo == 'real':
        return Decimal(str(valor))
    if tipo == 'inteiro':
        return int(valor)
    if tipo == 'logico':
        return bool(valor)
    if tipo == 'texto':
        return str(valor)
    return valor


def valor_padrao(tipo):
    return {
        'inteiro': 0,
        'real': Decimal('0'),
        'logico': False,
        'texto': '',
    }[tipo]


def aplicar_unario(operador, valor):
    if operador == '-':
        return -valor
    if operador == 'nao':
        return not valor
    raise ValueError(f'operador unario {operador!r}')


def divisao_inteira(a, b):
    quociente = abs(a) // abs(b)
    return -quociente if (a < 0) != (b < 0) else quociente


def aplicar_binario(operador, esquerda, direita, tipo, linha):
    if operador in ('/', '%') and direita == 0:
        erro(linha, 'divisao por zero' if operador == '/' else 'resto por zero')
    if operador == '+':
        return esquerda + direita
    if operador == '-':
        return esquerda - direita
    if operador == '*':
        return esquerda * direita
    if operador == '/':
        if tipo == 'inteiro':
            return divisao_inteira(esquerda, direita)
        try:
            return esquerda / direita
        except DivisionByZero:
            erro(linha, 'divisao por zero')
    if operador == '%':
        quociente = divisao_inteira(esquerda, direita)
        return esquerda - quociente * direita
    if operador == '==':
        return esquerda == direita
    if operador == '!=':
        return esquerda != direita
    if operador == '<':
        return esquerda < direita
    if operador == '<=':
        return esquerda <= direita
    if operador == '>':
        return esquerda > direita
    if operador == '>=':
        return esquerda >= direita
    if operador == 'e':
        return esquerda and direita
    if operador == 'ou':
        return esquerda or direita
    raise ValueError(f'operador binario {operador!r}')


def alvo_rotulo(funcao, nome, linha):
    if nome not in funcao.rotulos:
        erro(linha, f'rotulo {nome!r} inexistente')
    return funcao.rotulos[nome]


def formatar(valor, tipo):
    if tipo == 'real':
        return format(valor, '.6f')
    if tipo == 'logico':
        return 'verdadeiro' if valor else 'falso'
    return str(valor)
