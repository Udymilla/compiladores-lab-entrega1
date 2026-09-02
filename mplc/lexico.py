"""
Entrega 1 — analise lexica.

Transformar o texto do programa numa lista de tokens.

O que voces tem que devolver: uma lista de Token. O ultimo elemento e sempre
um token FIM_ARQUIVO. A regra de posicao dele esta em CONTRATOS.md, secao 7.

Leiam antes: LINGUAGEM.md secao 2, e CONTRATOS.md secao 2.
"""
from mplc.erros import ErroMPL


class Token:
    __slots__ = ('tipo', 'lexema', 'linha', 'coluna')

    def __init__(self, tipo, lexema, linha, coluna):
        self.tipo = tipo          # 'ID', 'INTEIRO', 'MAIS', ... (a lista esta no contrato)
        self.lexema = lexema      # o texto exato como apareceu no fonte
        self.linha = linha
        self.coluna = coluna      # a coluna do PRIMEIRO caractere do token

    def __str__(self):
        # esta e a linha que o --tokens imprime; nao mexam no formato
        return f"{self.linha},{self.coluna},{self.tipo},{self.lexema}"


def analisar(fonte):
    """Recebe o texto do programa. Devolve a lista de Token."""
    palavras = {
        'funcao': 'FUNCAO',
        'retorne': 'RETORNE',
        'se': 'SE',
        'senao': 'SENAO',
        'enquanto': 'ENQUANTO',
        'escreva': 'ESCREVA',
        'inteiro': 'TIPO_INTEIRO',
        'real': 'TIPO_REAL',
        'logico': 'TIPO_LOGICO',
        'texto': 'TIPO_TEXTO',
        'vazio': 'TIPO_VAZIO',
        'verdadeiro': 'LOGICO',
        'falso': 'LOGICO',
        'e': 'E',
        'ou': 'OU',
        'nao': 'NAO',
    }

    simbolos_duplos = {
        '==': 'IGUAL',
        '!=': 'DIFERENTE',
        '<=': 'MENOR_IGUAL',
        '>=': 'MAIOR_IGUAL',
    }

    simbolos_simples = {
        '+': 'MAIS',
        '-': 'MENOS',
        '*': 'VEZES',
        '/': 'DIVIDE',
        '%': 'RESTO',
        '<': 'MENOR',
        '>': 'MAIOR',
        '=': 'ATRIBUI',
        '(': 'ABRE_PAR',
        ')': 'FECHA_PAR',
        '{': 'ABRE_CHAVE',
        '}': 'FECHA_CHAVE',
        ',': 'VIRGULA',
        ';': 'PONTO_VIRGULA',
    }

    tokens = []
    indice = 0
    linha = 1
    coluna = 1
    tamanho = len(fonte)

    def avancar():
        """Consome um caractere e atualiza a posicao do proximo."""
        nonlocal indice, linha, coluna
        caractere = fonte[indice]
        indice += 1
        if caractere == '\n':
            linha += 1
            coluna = 1
        else:
            coluna += 1
        return caractere

    def erro(linha_erro, coluna_erro, mensagem):
        raise ErroMPL('lexico', linha_erro, coluna_erro, mensagem)

    while indice < tamanho:
        atual = fonte[indice]

        # Espacos apenas separam tokens. A leitura do arquivo em modo texto
        # normaliza CRLF para \n; o \r continua aceito caso analisar() seja
        # chamado diretamente.
        if atual in ' \t\r\n':
            avancar()
            continue

        # Comentario de linha.
        if fonte.startswith('//', indice):
            avancar()
            avancar()
            while indice < tamanho and fonte[indice] != '\n':
                avancar()
            continue

        # Comentario de bloco. O primeiro */ encerra o comentario.
        if fonte.startswith('/*', indice):
            linha_inicio, coluna_inicio = linha, coluna
            avancar()
            avancar()
            while indice < tamanho and not fonte.startswith('*/', indice):
                avancar()
            if indice == tamanho:
                erro(linha_inicio, coluna_inicio, 'comentario de bloco nao terminado')
            avancar()
            avancar()
            continue

        linha_inicio, coluna_inicio = linha, coluna
        inicio = indice

        # Identificador ou palavra reservada. A MPL permite apenas letras
        # ASCII, digitos e sublinhado nos identificadores.
        if atual == '_' or 'a' <= atual <= 'z' or 'A' <= atual <= 'Z':
            avancar()
            while indice < tamanho:
                atual = fonte[indice]
                if atual == '_' or atual.isascii() and atual.isalnum():
                    avancar()
                else:
                    break
            lexema = fonte[inicio:indice]
            tipo = palavras.get(lexema, 'ID')
            tokens.append(Token(tipo, lexema, linha_inicio, coluna_inicio))
            continue

        # Literal numerico. Um ponto depois dos digitos obrigatoriamente
        # inicia um real e, portanto, precisa ser seguido por outro digito.
        if '0' <= atual <= '9':
            while indice < tamanho and '0' <= fonte[indice] <= '9':
                avancar()
            tipo = 'INTEIRO'
            if indice < tamanho and fonte[indice] == '.':
                linha_ponto, coluna_ponto = linha, coluna
                avancar()
                if indice == tamanho or not '0' <= fonte[indice] <= '9':
                    erro(linha_ponto, coluna_ponto,
                         'o ponto de um real precisa de digitos dos dois lados')
                while indice < tamanho and '0' <= fonte[indice] <= '9':
                    avancar()
                tipo = 'REAL'
            tokens.append(Token(tipo, fonte[inicio:indice],
                                linha_inicio, coluna_inicio))
            continue

        # Literal de texto. O lexema preserva aspas e escapes exatamente como
        # aparecem no fonte; a interpretacao deles pertence a fases seguintes.
        if atual == '"':
            avancar()
            terminou = False
            while indice < tamanho:
                atual = fonte[indice]
                if atual == '"':
                    avancar()
                    terminou = True
                    break
                if atual == '\n' or atual == '\r':
                    erro(linha_inicio, coluna_inicio, 'texto nao terminado')
                if atual == '\\':
                    linha_escape, coluna_escape = linha, coluna
                    avancar()
                    if indice == tamanho or fonte[indice] not in 'nt"\\':
                        erro(linha_escape, coluna_escape, 'escape invalido')
                    avancar()
                    continue
                avancar()
            if not terminou:
                erro(linha_inicio, coluna_inicio, 'texto nao terminado')
            tokens.append(Token('TEXTO', fonte[inicio:indice],
                                linha_inicio, coluna_inicio))
            continue

        # Operadores de dois caracteres precisam vir antes dos simples.
        duplo = fonte[indice:indice + 2]
        if duplo in simbolos_duplos:
            avancar()
            avancar()
            tokens.append(Token(simbolos_duplos[duplo], duplo,
                                linha_inicio, coluna_inicio))
            continue

        if atual in simbolos_simples:
            avancar()
            tokens.append(Token(simbolos_simples[atual], atual,
                                linha_inicio, coluna_inicio))
            continue

        # Um ponto nunca e valido isoladamente, inclusive em .5.
        if atual == '.':
            erro(linha_inicio, coluna_inicio,
                 'o ponto de um real precisa de digitos dos dois lados')

        erro(linha_inicio, coluna_inicio, f'caractere invalido: {atual!r}')

    tokens.append(Token('FIM_ARQUIVO', '', linha, coluna))
    return tokens
