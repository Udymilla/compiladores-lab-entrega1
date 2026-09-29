"""
Entrega 2 — analise sintatica.

Transformar a lista de tokens numa arvore.

Sugestao forte: descida recursiva, uma funcao por nivel de precedencia, na
ordem da secao 3.3 da especificacao. E como voces vao enxergar a precedencia
virar formato de arvore.

Gerador de parser (ANTLR, PLY, yacc) esta proibido nesta entrega e na
anterior — o objetivo e entender, e o gerador esconde exatamente a parte
que esta sendo ensinada.

Leiam antes: LINGUAGEM.md secoes 3 a 5, e CONTRATOS.md secao 3.
"""
from decimal import Decimal

from mplc.erros import ErroMPL


class No:
    """Um no da arvore. O rotulo e o que sai no --ast."""

    def __init__(self, rotulo, filhos=None, linha=0, coluna=0, **extra):
        self.rotulo = rotulo      # 'binario +', 'literal inteiro 1', 'bloco', ...
        self.filhos = filhos or []
        self.linha = linha
        self.coluna = coluna
        self.extra = extra        # o que a semantica quiser pendurar depois


def analisar(tokens):
    """Recebe a lista de Token. Devolve a raiz da arvore (um No 'programa')."""
    return Analisador(tokens).programa()


class Analisador:
    """Parser de descida recursiva para a gramatica da MPL."""

    TIPOS = {
        'TIPO_INTEIRO': 'inteiro',
        'TIPO_REAL': 'real',
        'TIPO_LOGICO': 'logico',
        'TIPO_TEXTO': 'texto',
    }
    TIPOS_RETORNO = {**TIPOS, 'TIPO_VAZIO': 'vazio'}

    def __init__(self, tokens):
        self.tokens = tokens
        self.posicao = 0

    def atual(self):
        return self.tokens[self.posicao]

    def anterior(self):
        return self.tokens[self.posicao - 1]

    def verificar(self, *tipos):
        return self.atual().tipo in tipos

    def aceitar(self, *tipos):
        if not self.verificar(*tipos):
            return None
        token = self.atual()
        self.posicao += 1
        return token

    def esperar(self, tipo, descricao=None):
        token = self.aceitar(tipo)
        if token is not None:
            return token
        esperado = descricao or tipo
        encontrado = self.atual().lexema or 'fim do arquivo'
        self.erro(f'esperado {esperado}, encontrado {encontrado!r}')

    def erro(self, mensagem, token=None):
        token = token or self.atual()
        raise ErroMPL('sintatico', token.linha, token.coluna, mensagem)

    def programa(self):
        funcoes = []
        while not self.verificar('FIM_ARQUIVO'):
            funcoes.append(self.funcao())
        fim = self.esperar('FIM_ARQUIVO')
        return No('programa', funcoes, linha=1, coluna=1,
                  fim_linha=fim.linha, fim_coluna=fim.coluna)

    def funcao(self):
        inicio = self.esperar('FUNCAO', "'funcao'")
        tipo = self.tipo_retorno()
        nome = self.esperar('ID', 'nome da funcao')
        self.esperar('ABRE_PAR', "'('")
        parametros = self.parametros()
        self.esperar('FECHA_PAR', "')'")
        corpo = self.bloco()
        return No(f'funcao {nome.lexema} {tipo}', [parametros, corpo],
                  linha=inicio.linha, coluna=inicio.coluna,
                  nome=nome.lexema, tipo=tipo)

    def tipo_retorno(self):
        token = self.atual()
        if token.tipo not in self.TIPOS_RETORNO:
            self.erro('esperado tipo de retorno')
        self.posicao += 1
        return self.TIPOS_RETORNO[token.tipo]

    def tipo(self):
        token = self.atual()
        if token.tipo not in self.TIPOS:
            self.erro('esperado tipo')
        self.posicao += 1
        return self.TIPOS[token.tipo]

    def parametros(self):
        filhos = []
        if not self.verificar('FECHA_PAR'):
            while True:
                token_tipo = self.atual()
                tipo = self.tipo()
                nome = self.esperar('ID', 'nome do parametro')
                filhos.append(No(f'parametro {nome.lexema} {tipo}',
                                  linha=token_tipo.linha,
                                  coluna=token_tipo.coluna,
                                  nome=nome.lexema, tipo=tipo))
                if self.aceitar('VIRGULA') is None:
                    break
        return No('parametros', filhos)

    def bloco(self):
        inicio = self.esperar('ABRE_CHAVE', "'{'")
        comandos = []
        while not self.verificar('FECHA_CHAVE', 'FIM_ARQUIVO'):
            comandos.append(self.comando())
        self.esperar('FECHA_CHAVE', "'}'")
        return No('bloco', comandos, linha=inicio.linha, coluna=inicio.coluna)

    def comando(self):
        if self.verificar(*self.TIPOS):
            return self.declaracao()
        if self.verificar('ID'):
            return self.atribuicao_ou_chamada()
        if self.verificar('SE'):
            return self.condicional()
        if self.verificar('ENQUANTO'):
            return self.repeticao()
        if self.verificar('ESCREVA'):
            return self.escrita()
        if self.verificar('RETORNE'):
            return self.retorno()
        if self.verificar('ABRE_CHAVE'):
            return self.bloco()
        self.erro('esperado comando')

    def declaracao(self):
        token_tipo = self.atual()
        tipo = self.tipo()
        nome = self.esperar('ID', 'nome da variavel')
        filhos = []
        if self.aceitar('ATRIBUI') is not None:
            filhos.append(self.expressao())
        self.esperar('PONTO_VIRGULA', "';'")
        return No(f'declaracao {nome.lexema} {tipo}', filhos,
                  linha=token_tipo.linha, coluna=token_tipo.coluna,
                  nome=nome.lexema, tipo=tipo)

    def atribuicao_ou_chamada(self):
        nome = self.esperar('ID')
        if self.aceitar('ATRIBUI') is not None:
            valor = self.expressao()
            self.esperar('PONTO_VIRGULA', "';'")
            return No(f'atribuicao {nome.lexema}', [valor],
                      linha=nome.linha, coluna=nome.coluna,
                      nome=nome.lexema)
        if self.verificar('ABRE_PAR'):
            chamada = self.chamada(nome)
            self.esperar('PONTO_VIRGULA', "';'")
            return chamada
        self.erro("esperado '=' ou '(' depois do identificador")

    def condicional(self):
        inicio = self.esperar('SE')
        self.esperar('ABRE_PAR', "'('")
        condicao = self.expressao()
        self.esperar('FECHA_PAR', "')'")
        filhos = [condicao, self.bloco()]
        if self.aceitar('SENAO') is not None:
            filhos.append(self.bloco())
        return No('se', filhos, linha=inicio.linha, coluna=inicio.coluna)

    def repeticao(self):
        inicio = self.esperar('ENQUANTO')
        self.esperar('ABRE_PAR', "'('")
        condicao = self.expressao()
        self.esperar('FECHA_PAR', "')'")
        corpo = self.bloco()
        return No('enquanto', [condicao, corpo],
                  linha=inicio.linha, coluna=inicio.coluna)

    def escrita(self):
        inicio = self.esperar('ESCREVA')
        self.esperar('ABRE_PAR', "'('")
        valor = self.expressao()
        self.esperar('FECHA_PAR', "')'")
        self.esperar('PONTO_VIRGULA', "';'")
        return No('escreva', [valor], linha=inicio.linha, coluna=inicio.coluna)

    def retorno(self):
        inicio = self.esperar('RETORNE')
        filhos = []
        if not self.verificar('PONTO_VIRGULA'):
            filhos.append(self.expressao())
        self.esperar('PONTO_VIRGULA', "';'")
        return No('retorne', filhos, linha=inicio.linha, coluna=inicio.coluna)

    def expressao(self):
        return self.ou()

    def ou(self):
        return self.binaria_esquerda(self.e, 'OU')

    def e(self):
        return self.binaria_esquerda(self.igualdade, 'E')

    def igualdade(self):
        return self.binaria_esquerda(self.comparacao, 'IGUAL', 'DIFERENTE')

    def comparacao(self):
        return self.binaria_esquerda(
            self.adicao, 'MENOR', 'MENOR_IGUAL', 'MAIOR', 'MAIOR_IGUAL')

    def adicao(self):
        return self.binaria_esquerda(self.multiplicacao, 'MAIS', 'MENOS')

    def multiplicacao(self):
        return self.binaria_esquerda(self.unaria, 'VEZES', 'DIVIDE', 'RESTO')

    def binaria_esquerda(self, proximo_nivel, *operadores):
        esquerda = proximo_nivel()
        while self.verificar(*operadores):
            operador = self.atual()
            self.posicao += 1
            direita = proximo_nivel()
            esquerda = No(f'binario {operador.lexema}', [esquerda, direita],
                          linha=operador.linha, coluna=operador.coluna,
                          operador=operador.lexema)
        return esquerda

    def unaria(self):
        operador = self.aceitar('NAO', 'MENOS')
        if operador is not None:
            operando = self.unaria()
            return No(f'unario {operador.lexema}', [operando],
                      linha=operador.linha, coluna=operador.coluna,
                      operador=operador.lexema)
        return self.primaria()

    def primaria(self):
        token = self.atual()

        if self.aceitar('INTEIRO') is not None:
            return No(f'literal inteiro {token.lexema}',
                      linha=token.linha, coluna=token.coluna,
                      tipo='inteiro', valor=int(token.lexema),
                      lexema=token.lexema)

        if self.aceitar('REAL') is not None:
            valor_formatado = format(Decimal(token.lexema), '.6f')
            return No(f'literal real {valor_formatado}',
                      linha=token.linha, coluna=token.coluna,
                      tipo='real', valor=Decimal(token.lexema),
                      lexema=token.lexema)

        if self.aceitar('LOGICO') is not None:
            return No(f'literal logico {token.lexema}',
                      linha=token.linha, coluna=token.coluna,
                      tipo='logico', valor=token.lexema == 'verdadeiro',
                      lexema=token.lexema)

        if self.aceitar('TEXTO') is not None:
            return No(f'literal texto {token.lexema}',
                      linha=token.linha, coluna=token.coluna,
                      tipo='texto', valor=token.lexema,
                      lexema=token.lexema)

        if self.aceitar('ID') is not None:
            if self.verificar('ABRE_PAR'):
                return self.chamada(token)
            return No(f'variavel {token.lexema}',
                      linha=token.linha, coluna=token.coluna,
                      nome=token.lexema)

        if self.aceitar('ABRE_PAR') is not None:
            valor = self.expressao()
            self.esperar('FECHA_PAR', "')'")
            return valor

        self.erro('esperado expressao')

    def chamada(self, nome):
        self.esperar('ABRE_PAR', "'('")
        argumentos = []
        if not self.verificar('FECHA_PAR'):
            while True:
                argumentos.append(self.expressao())
                if self.aceitar('VIRGULA') is None:
                    break
        self.esperar('FECHA_PAR', "')'")
        return No(f'chamada {nome.lexema}', argumentos,
                  linha=nome.linha, coluna=nome.coluna,
                  nome=nome.lexema)


def despejar(no, nivel=0, saida=None):
    """Imprime a arvore no formato do --ast. Ja esta pronto: dois espacos por nivel."""
    saida = saida if saida is not None else []
    saida.append('  ' * nivel + no.rotulo)
    for f in no.filhos:
        despejar(f, nivel + 1, saida)
    return saida
