"""Geracao do codigo intermediario de tres enderecos da MPL.

Cada expressao e decomposta em instrucoes simples. Os valores intermediarios
ficam em temporarios (t0, t1, ...), e cada instrucao de calculo contem no
maximo um operador.
"""
import json


class Instrucao:
    def __init__(self, op, linha=1, **args):
        self.op = op
        self.linha = linha or 1
        self.args = args


class FuncaoIR:
    def __init__(self, nome, tipo_retorno):
        self.nome = nome
        self.tipo_retorno = tipo_retorno
        self.parametros = []
        self.locais = {}
        self.instrucoes = []


class ProgramaIR:
    def __init__(self):
        self.funcoes = []


def gerar(arvore, tabela):
    """Devolve um ProgramaIR produzido a partir da AST ja validada."""
    return GeradorIR(arvore, tabela).executar()


class GeradorIR:
    def __init__(self, arvore, tabela):
        self.arvore = arvore
        self.tabela = tabela
        self.programa = ProgramaIR()
        self.funcao = None
        self.slots = {}
        self.proximo_slot = 0
        self.proximo_temp = 0
        self.proximo_rotulo = 0

    def executar(self):
        for no in self.arvore.filhos:
            self.gerar_funcao(no)
        return self.programa

    def emitir(self, op, linha=1, **args):
        self.funcao.instrucoes.append(Instrucao(op, linha, **args))

    def novo_temp(self):
        nome = f't{self.proximo_temp}'
        self.proximo_temp += 1
        return nome

    def novo_rotulo(self):
        nome = f'L{self.proximo_rotulo}'
        self.proximo_rotulo += 1
        return nome

    def slot(self, simbolo):
        chave = id(simbolo)
        if chave not in self.slots:
            prefixo = 'p' if simbolo.categoria == 'parametro' else 'v'
            nome = f'{prefixo}{self.proximo_slot}_{simbolo.nome}'
            self.proximo_slot += 1
            self.slots[chave] = nome
            self.funcao.locais[nome] = simbolo.tipo
        return self.slots[chave]

    def gerar_funcao(self, no):
        self.funcao = FuncaoIR(no.extra['nome'], no.extra['tipo'])
        self.programa.funcoes.append(self.funcao)
        self.slots = {}
        self.proximo_slot = 0
        self.proximo_temp = 0
        self.proximo_rotulo = 0

        for parametro in no.filhos[0].filhos:
            simbolo = parametro.extra['simbolo']
            nome_slot = self.slot(simbolo)
            self.funcao.parametros.append((nome_slot, simbolo.tipo, simbolo.nome))

        self.gerar_bloco(no.filhos[1])
        self.emitir('retorne', no.linha, valor=None)

    def gerar_bloco(self, no):
        for comando in no.filhos:
            self.gerar_comando(comando)

    def gerar_comando(self, no):
        classe = no.rotulo.split(' ', 1)[0]

        if classe == 'declaracao':
            simbolo = no.extra['simbolo']
            destino = self.slot(simbolo)
            if no.filhos:
                valor = self.gerar_expressao(no.filhos[0])
                valor = self.converter(valor, no.filhos[0].extra['tipo_semantico'],
                                       simbolo.tipo, no.linha)
                self.emitir('armazena', no.linha, slot=destino, valor=valor,
                            nome=simbolo.nome)
            else:
                self.emitir('padrao', no.linha, slot=destino, tipo=simbolo.tipo,
                            nome=simbolo.nome)
            return

        if classe == 'atribuicao':
            simbolo = no.extra['simbolo']
            valor = self.gerar_expressao(no.filhos[0])
            valor = self.converter(valor, no.filhos[0].extra['tipo_semantico'],
                                   simbolo.tipo, no.linha)
            self.emitir('armazena', no.linha, slot=self.slot(simbolo), valor=valor,
                        nome=simbolo.nome)
            return

        if classe == 'escreva':
            valor = self.gerar_expressao(no.filhos[0])
            self.emitir('escreva', no.linha, valor=valor,
                        tipo=no.filhos[0].extra['tipo_semantico'])
            return

        if classe == 'retorne':
            valor = None
            if no.filhos:
                expr = no.filhos[0]
                valor = self.gerar_expressao(expr)
                valor = self.converter(valor, expr.extra['tipo_semantico'],
                                       no.extra['tipo_semantico'], no.linha)
            self.emitir('retorne', no.linha, valor=valor)
            return

        if classe == 'chamada':
            self.gerar_chamada(no, guardar=False)
            return

        if classe == 'bloco':
            self.gerar_bloco(no)
            return

        if classe == 'se':
            condicao = self.gerar_expressao(no.filhos[0])
            rotulo_senao = self.novo_rotulo()
            rotulo_fim = self.novo_rotulo() if len(no.filhos) == 3 else rotulo_senao
            self.emitir('desvia_falso', no.linha, valor=condicao,
                        rotulo=rotulo_senao)
            self.gerar_bloco(no.filhos[1])
            if len(no.filhos) == 3:
                self.emitir('desvia', no.linha, rotulo=rotulo_fim)
                self.emitir('rotulo', no.linha, nome=rotulo_senao)
                self.gerar_bloco(no.filhos[2])
            self.emitir('rotulo', no.linha, nome=rotulo_fim)
            return

        if classe == 'enquanto':
            rotulo_inicio = self.novo_rotulo()
            rotulo_fim = self.novo_rotulo()
            self.emitir('rotulo', no.linha, nome=rotulo_inicio)
            condicao = self.gerar_expressao(no.filhos[0])
            self.emitir('desvia_falso', no.linha, valor=condicao,
                        rotulo=rotulo_fim)
            self.gerar_bloco(no.filhos[1])
            self.emitir('desvia', no.linha, rotulo=rotulo_inicio)
            self.emitir('rotulo', no.linha, nome=rotulo_fim)
            return

        raise ValueError(f'comando IR desconhecido: {no.rotulo}')

    def gerar_expressao(self, no):
        classe = no.rotulo.split(' ', 1)[0]

        if classe == 'literal':
            destino = self.novo_temp()
            tipo = no.extra['tipo']
            valor = no.extra['valor']
            if tipo == 'texto':
                valor = json.loads(valor)
            elif tipo == 'real':
                valor = str(valor)
            self.emitir('constante', no.linha, destino=destino, tipo=tipo,
                        valor=valor)
            return destino

        if classe == 'variavel':
            destino = self.novo_temp()
            simbolo = no.extra['simbolo']
            self.emitir('carrega', no.linha, destino=destino,
                        slot=self.slot(simbolo), nome=simbolo.nome)
            return destino

        if classe == 'chamada':
            return self.gerar_chamada(no, guardar=True)

        if classe == 'unario':
            operando = self.gerar_expressao(no.filhos[0])
            destino = self.novo_temp()
            self.emitir('unario', no.linha, destino=destino,
                        operador=no.extra['operador'], operando=operando)
            return destino

        if classe == 'binario':
            esquerda_no, direita_no = no.filhos
            esquerda = self.gerar_expressao(esquerda_no)
            direita = self.gerar_expressao(direita_no)
            op = no.extra['operador']
            tipo_e = esquerda_no.extra['tipo_semantico']
            tipo_d = direita_no.extra['tipo_semantico']
            if tipo_e in ('inteiro', 'real') and tipo_d in ('inteiro', 'real'):
                if 'real' in (tipo_e, tipo_d):
                    esquerda = self.converter(esquerda, tipo_e, 'real', no.linha)
                    direita = self.converter(direita, tipo_d, 'real', no.linha)

            destino = self.novo_temp()
            self.emitir('binario', no.linha, destino=destino, operador=op,
                        esquerda=esquerda, direita=direita,
                        tipo=no.extra['tipo_semantico'])
            return destino

        raise ValueError(f'expressao IR desconhecida: {no.rotulo}')

    def gerar_chamada(self, no, guardar):
        simbolo = no.extra['simbolo']
        argumentos = []
        for argumento, tipo_parametro in zip(no.filhos, simbolo.parametros):
            valor = self.gerar_expressao(argumento)
            valor = self.converter(valor, argumento.extra['tipo_semantico'],
                                   tipo_parametro, argumento.linha)
            argumentos.append(valor)
        destino = self.novo_temp() if guardar else None
        self.emitir('chama', no.linha, destino=destino, nome=simbolo.nome,
                    argumentos=argumentos, tipo=simbolo.tipo)
        return destino

    def converter(self, valor, origem, destino, linha):
        if origem == destino:
            return valor
        if origem == 'inteiro' and destino == 'real':
            convertido = self.novo_temp()
            self.emitir('converte_real', linha, destino=convertido, valor=valor)
            return convertido
        return valor


def _valor_texto(valor, tipo=None):
    if tipo == 'texto':
        return json.dumps(valor, ensure_ascii=False)
    if tipo == 'logico':
        return 'verdadeiro' if valor else 'falso'
    return str(valor)


def despejar(codigo):
    """Devolve uma representacao humana do codigo de tres enderecos."""
    linhas = []
    for funcao in codigo.funcoes:
        parametros = ', '.join(
            f'{nome} {tipo}' for _, tipo, nome in funcao.parametros)
        linhas.append(f'funcao {funcao.nome} {funcao.tipo_retorno} ({parametros})')
        for inst in funcao.instrucoes:
            a = inst.args
            if inst.op == 'rotulo':
                linhas.append(f'{a["nome"]}:')
            elif inst.op == 'constante':
                linhas.append(f'  {a["destino"]} = {_valor_texto(a["valor"], a["tipo"])}')
            elif inst.op == 'carrega':
                linhas.append(f'  {a["destino"]} = {a["nome"]}@{a["slot"]}')
            elif inst.op == 'padrao':
                linhas.append(f'  {a["nome"]}@{a["slot"]} = padrao {a["tipo"]}')
            elif inst.op == 'armazena':
                linhas.append(f'  {a["nome"]}@{a["slot"]} = {a["valor"]}')
            elif inst.op == 'unario':
                linhas.append(f'  {a["destino"]} = {a["operador"]} {a["operando"]}')
            elif inst.op == 'binario':
                linhas.append(f'  {a["destino"]} = {a["esquerda"]} {a["operador"]} {a["direita"]}')
            elif inst.op == 'converte_real':
                linhas.append(f'  {a["destino"]} = real {a["valor"]}')
            elif inst.op == 'chama':
                chamada = f'chama {a["nome"]}'
                if a['argumentos']:
                    chamada += ' ' + ', '.join(a['argumentos'])
                if a['destino'] is None:
                    linhas.append(f'  {chamada}')
                else:
                    linhas.append(f'  {a["destino"]} = {chamada}')
            elif inst.op == 'escreva':
                linhas.append(f'  escreva {a["valor"]}')
            elif inst.op == 'desvia_falso':
                linhas.append(f'  seFalso {a["valor"]} desvie {a["rotulo"]}')
            elif inst.op == 'desvia':
                linhas.append(f'  desvie {a["rotulo"]}')
            elif inst.op == 'retorne':
                sufixo = '' if a['valor'] is None else f' {a["valor"]}'
                linhas.append(f'  retorne{sufixo}')
        linhas.append('fim')
    return linhas
