"""
Entrega 3 — analise semantica.

Tabela de simbolos, escopos aninhados e verificacao de tipos.

Tres coisas que costumam ser esquecidas e valem nota:
  - o corpo de uma funcao abre DOIS escopos (o dos parametros e o do bloco);
  - uma funcao pode ser chamada antes de aparecer no arquivo, entao a
    primeira passada so coleta assinaturas;
  - funcao com retorno declarado precisa garantir o retorno em TODOS os
    caminhos.

Leiam antes: LINGUAGEM.md secoes 3 a 5, e CONTRATOS.md secao 4.
"""
from mplc.erros import ErroMPL


TIPOS_NUMERICOS = {'inteiro', 'real'}


class Simbolo:
    """Uma funcao, um parametro ou uma variavel declarada na MPL."""

    def __init__(self, nome, categoria, tipo, linha, no=None, parametros=None):
        self.nome = nome
        self.categoria = categoria
        self.tipo = tipo
        self.linha = linha
        self.no = no
        self.parametros = list(parametros or [])
        self.escopo = None


class Escopo:
    """Um dicionario de simbolos ligado ao escopo que o contem."""

    def __init__(self, numero, descricao, pai=None):
        self.numero = numero
        self.descricao = descricao
        self.pai = pai
        self.simbolos = {}

    def adicionar(self, simbolo):
        self.simbolos[simbolo.nome] = simbolo
        simbolo.escopo = self


class TabelaSimbolos:
    """Arvore de escopos, mantida tambem em ordem de abertura para o despejo."""

    def __init__(self):
        self.global_ = Escopo(0, 'global')
        self.escopos = [self.global_]

    def novo_escopo(self, descricao, pai):
        escopo = Escopo(len(self.escopos), descricao, pai)
        self.escopos.append(escopo)
        return escopo

    def procurar_variavel(self, nome, escopo):
        atual = escopo
        while atual is not None and atual is not self.global_:
            simbolo = atual.simbolos.get(nome)
            if simbolo is not None and simbolo.categoria in ('parametro', 'variavel'):
                return simbolo
            atual = atual.pai
        return None

    def procurar_funcao(self, nome):
        simbolo = self.global_.simbolos.get(nome)
        if simbolo is not None and simbolo.categoria == 'funcao':
            return simbolo
        return None


def analisar(arvore):
    """Percorre a arvore, monta a tabela e confere os tipos. Devolve a tabela."""
    return AnalisadorSemantico(arvore).executar()


class AnalisadorSemantico:
    def __init__(self, arvore):
        self.arvore = arvore
        self.tabela = TabelaSimbolos()
        self.funcao_atual = None

    def executar(self):
        # Primeira passada: todas as assinaturas ficam disponiveis antes de
        # qualquer corpo ser analisado, permitindo recursao direta e mutua.
        self.coletar_assinaturas()
        self.validar_principal()

        # Segunda passada: cria escopos, registra variaveis e confere tipos.
        for funcao in self.arvore.filhos:
            self.analisar_funcao(funcao)

        self.arvore.extra['tabela'] = self.tabela
        return self.tabela

    def erro(self, no, mensagem):
        raise ErroMPL('semantico', no.linha or 1, no.coluna or 1, mensagem)

    def coletar_assinaturas(self):
        global_ = self.tabela.global_
        for no in self.arvore.filhos:
            nome = no.extra['nome']
            if nome in global_.simbolos:
                self.erro(no, f'funcao {nome!r} declarada mais de uma vez')
            parametros = [p.extra['tipo'] for p in no.filhos[0].filhos]
            simbolo = Simbolo(nome, 'funcao', no.extra['tipo'], no.linha,
                              no=no, parametros=parametros)
            global_.adicionar(simbolo)
            no.extra['simbolo'] = simbolo

    def validar_principal(self):
        principal = self.tabela.procurar_funcao('principal')
        if principal is None:
            self.erro(self.arvore, 'falta a funcao principal')
        if principal.tipo != 'vazio':
            self.erro(principal.no, 'a funcao principal deve retornar vazio')
        if principal.parametros:
            self.erro(principal.no, 'a funcao principal nao pode ter parametros')

    def analisar_funcao(self, no):
        simbolo_funcao = no.extra['simbolo']
        self.funcao_atual = simbolo_funcao

        escopo_funcao = self.tabela.novo_escopo(
            f'funcao {simbolo_funcao.nome}', self.tabela.global_)
        no.extra['escopo_funcao'] = escopo_funcao

        for parametro in no.filhos[0].filhos:
            nome = parametro.extra['nome']
            if nome in escopo_funcao.simbolos:
                self.erro(parametro, f'parametro {nome!r} declarado mais de uma vez')
            simbolo = Simbolo(nome, 'parametro', parametro.extra['tipo'],
                              parametro.linha, no=parametro)
            escopo_funcao.adicionar(simbolo)
            parametro.extra['simbolo'] = simbolo
            parametro.extra['escopo'] = escopo_funcao

        corpo = no.filhos[1]
        self.analisar_bloco(corpo, escopo_funcao)

        if simbolo_funcao.tipo != 'vazio' and not self.garante_retorno(corpo):
            self.erro(no, f'a funcao {simbolo_funcao.nome!r} pode terminar sem retorne')

        self.funcao_atual = None

    def analisar_bloco(self, no, pai):
        escopo = self.tabela.novo_escopo('bloco', pai)
        no.extra['escopo'] = escopo
        for comando in no.filhos:
            self.analisar_comando(comando, escopo)
        return escopo

    def analisar_comando(self, no, escopo):
        classe = no.rotulo.split(' ', 1)[0]
        no.extra['escopo_uso'] = escopo

        if classe == 'declaracao':
            self.analisar_declaracao(no, escopo)
            return
        if classe == 'atribuicao':
            self.analisar_atribuicao(no, escopo)
            return
        if classe == 'se':
            tipo = self.tipo_expressao(no.filhos[0], escopo)
            if tipo != 'logico':
                self.erro(no.filhos[0], 'a condicao de se deve ser logica')
            self.analisar_bloco(no.filhos[1], escopo)
            if len(no.filhos) == 3:
                self.analisar_bloco(no.filhos[2], escopo)
            return
        if classe == 'enquanto':
            tipo = self.tipo_expressao(no.filhos[0], escopo)
            if tipo != 'logico':
                self.erro(no.filhos[0], 'a condicao de enquanto deve ser logica')
            self.analisar_bloco(no.filhos[1], escopo)
            return
        if classe == 'escreva':
            tipo = self.tipo_expressao(no.filhos[0], escopo)
            if tipo == 'vazio':
                self.erro(no, 'escreva nao aceita uma expressao vazia')
            return
        if classe == 'retorne':
            self.analisar_retorno(no, escopo)
            return
        if classe == 'chamada':
            self.validar_chamada(no, escopo, em_expressao=False)
            return
        if classe == 'bloco':
            self.analisar_bloco(no, escopo)
            return

        self.erro(no, f'comando desconhecido: {no.rotulo}')

    def analisar_declaracao(self, no, escopo):
        nome = no.extra['nome']
        if nome in escopo.simbolos:
            self.erro(no, f'{nome!r} ja foi declarado neste escopo')

        # A inicializacao e analisada antes de o novo nome entrar no escopo.
        # Assim, num bloco interno, "inteiro x = x + 1" pode ler o x externo.
        if no.filhos:
            tipo_valor = self.tipo_expressao(no.filhos[0], escopo)
            if not self.compativel(no.extra['tipo'], tipo_valor):
                self.erro(no, f'nao e possivel atribuir {tipo_valor} a {no.extra["tipo"]}')

        simbolo = Simbolo(nome, 'variavel', no.extra['tipo'], no.linha, no=no)
        escopo.adicionar(simbolo)
        no.extra['simbolo'] = simbolo
        no.extra['escopo'] = escopo

    def analisar_atribuicao(self, no, escopo):
        simbolo = self.tabela.procurar_variavel(no.extra['nome'], escopo)
        if simbolo is None:
            self.erro(no, f'variavel {no.extra["nome"]!r} nao declarada')
        tipo_valor = self.tipo_expressao(no.filhos[0], escopo)
        if not self.compativel(simbolo.tipo, tipo_valor):
            self.erro(no, f'nao e possivel atribuir {tipo_valor} a {simbolo.tipo}')
        no.extra['simbolo'] = simbolo
        no.extra['tipo_semantico'] = simbolo.tipo

    def analisar_retorno(self, no, escopo):
        esperado = self.funcao_atual.tipo
        if esperado == 'vazio':
            if no.filhos:
                self.erro(no, 'funcao vazia nao pode retornar valor')
            no.extra['tipo_semantico'] = 'vazio'
            return

        if not no.filhos:
            self.erro(no, f'a funcao deve retornar {esperado}')
        recebido = self.tipo_expressao(no.filhos[0], escopo)
        if not self.compativel(esperado, recebido):
            self.erro(no, f'retorno {recebido} incompativel com {esperado}')
        no.extra['tipo_semantico'] = esperado

    def tipo_expressao(self, no, escopo):
        classe = no.rotulo.split(' ', 1)[0]
        no.extra['escopo_uso'] = escopo

        if classe == 'literal':
            tipo = no.extra['tipo']
        elif classe == 'variavel':
            simbolo = self.tabela.procurar_variavel(no.extra['nome'], escopo)
            if simbolo is None:
                self.erro(no, f'variavel {no.extra["nome"]!r} nao declarada')
            no.extra['simbolo'] = simbolo
            tipo = simbolo.tipo
        elif classe == 'chamada':
            tipo = self.validar_chamada(no, escopo, em_expressao=True)
        elif classe == 'unario':
            tipo = self.tipo_unario(no, escopo)
        elif classe == 'binario':
            tipo = self.tipo_binario(no, escopo)
        else:
            self.erro(no, f'expressao desconhecida: {no.rotulo}')

        no.extra['tipo_semantico'] = tipo
        return tipo

    def validar_chamada(self, no, escopo, em_expressao):
        simbolo = self.tabela.procurar_funcao(no.extra['nome'])
        if simbolo is None:
            self.erro(no, f'funcao {no.extra["nome"]!r} nao declarada')
        if len(no.filhos) != len(simbolo.parametros):
            self.erro(no, f'a funcao espera {len(simbolo.parametros)} argumento(s)')

        for argumento, tipo_parametro in zip(no.filhos, simbolo.parametros):
            tipo_argumento = self.tipo_expressao(argumento, escopo)
            if not self.compativel(tipo_parametro, tipo_argumento):
                self.erro(argumento,
                          f'argumento {tipo_argumento} incompativel com {tipo_parametro}')

        if em_expressao and simbolo.tipo == 'vazio':
            self.erro(no, 'funcao vazia nao pode ser usada em expressao')
        no.extra['simbolo'] = simbolo
        no.extra['tipo_semantico'] = simbolo.tipo
        return simbolo.tipo

    def tipo_unario(self, no, escopo):
        operador = no.extra['operador']
        operando = self.tipo_expressao(no.filhos[0], escopo)
        if operador == 'nao':
            if operando != 'logico':
                self.erro(no, 'o operador nao exige um valor logico')
            return 'logico'
        if operador == '-':
            if operando not in TIPOS_NUMERICOS:
                self.erro(no, 'o menos unario exige um numero')
            return operando
        self.erro(no, f'operador unario desconhecido: {operador}')

    def tipo_binario(self, no, escopo):
        operador = no.extra['operador']
        esquerda = self.tipo_expressao(no.filhos[0], escopo)
        direita = self.tipo_expressao(no.filhos[1], escopo)

        if operador == '+' and esquerda == direita == 'texto':
            return 'texto'

        if operador in ('+', '-', '*', '/'):
            if esquerda not in TIPOS_NUMERICOS or direita not in TIPOS_NUMERICOS:
                self.erro(no, f'o operador {operador} exige numeros')
            return 'real' if 'real' in (esquerda, direita) else 'inteiro'

        if operador == '%':
            if esquerda != 'inteiro' or direita != 'inteiro':
                self.erro(no, 'o operador % exige dois inteiros')
            return 'inteiro'

        if operador in ('==', '!='):
            tipos_iguais = esquerda == direita
            numeros_compativeis = {esquerda, direita} <= TIPOS_NUMERICOS
            if not tipos_iguais and not numeros_compativeis:
                self.erro(no, f'nao e possivel comparar {esquerda} com {direita}')
            return 'logico'

        if operador in ('<', '<=', '>', '>='):
            if esquerda not in TIPOS_NUMERICOS or direita not in TIPOS_NUMERICOS:
                self.erro(no, f'o operador {operador} exige numeros')
            return 'logico'

        if operador in ('e', 'ou'):
            if esquerda != 'logico' or direita != 'logico':
                self.erro(no, f'o operador {operador} exige valores logicos')
            return 'logico'

        self.erro(no, f'operador binario desconhecido: {operador}')

    @staticmethod
    def compativel(destino, origem):
        return destino == origem or (destino == 'real' and origem == 'inteiro')

    def garante_retorno(self, bloco):
        """Retorna True quando algum comando garante a saida deste bloco."""
        for comando in bloco.filhos:
            classe = comando.rotulo.split(' ', 1)[0]
            if classe == 'retorne':
                return True
            if classe == 'bloco' and self.garante_retorno(comando):
                return True
            if classe == 'se' and len(comando.filhos) == 3:
                if (self.garante_retorno(comando.filhos[1]) and
                        self.garante_retorno(comando.filhos[2])):
                    return True
            # Um enquanto nunca garante retorno: a condicao pode ser falsa.
        return False


def despejar(tabela):
    """Devolve as linhas do --tabela, no formato da secao 4 do contrato."""
    linhas = []
    for escopo in tabela.escopos:
        if escopo.pai is None:
            linhas.append(f'escopo {escopo.numero} global')
        else:
            linhas.append(
                f'escopo {escopo.numero} {escopo.descricao} pai {escopo.pai.numero}')

        for simbolo in escopo.simbolos.values():
            if simbolo.categoria == 'funcao':
                parametros = ','.join(simbolo.parametros)
                tipo = f'{simbolo.tipo}({parametros})'
            else:
                tipo = simbolo.tipo
            linhas.append(
                f'  {simbolo.nome}|{simbolo.categoria}|{tipo}|{simbolo.linha}')
    return linhas
