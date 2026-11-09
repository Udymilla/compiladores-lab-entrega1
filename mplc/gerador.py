"""Traducao do codigo de tres enderecos para o bytecode textual MPLB."""
import json


def _linha(op, linha, **args):
    dados = {'op': op, 'line': linha, **args}
    return json.dumps(dados, ensure_ascii=False, separators=(',', ':'))


def gerar(codigo_intermediario):
    """Devolve as linhas de um arquivo MPLB legivel e executavel pela VM."""
    linhas = ['MPLB 1']
    for funcao in codigo_intermediario.funcoes:
        cabecalho = {
            'name': funcao.nome,
            'return': funcao.tipo_retorno,
            'params': [[slot, tipo, nome]
                       for slot, tipo, nome in funcao.parametros],
            'locals': funcao.locais,
        }
        linhas.append('FUNCTION ' + json.dumps(
            cabecalho, ensure_ascii=False, separators=(',', ':')))

        for inst in funcao.instrucoes:
            a = inst.args
            op = inst.op
            if op == 'rotulo':
                linhas.append(_linha('LABEL', inst.linha, name=a['nome']))
            elif op == 'constante':
                linhas.append(_linha('PUSH_CONST', inst.linha,
                                     value=a['valor'], type=a['tipo']))
                linhas.append(_linha('STORE_TEMP', inst.linha, name=a['destino']))
            elif op == 'carrega':
                linhas.append(_linha('LOAD_LOCAL', inst.linha, name=a['slot']))
                linhas.append(_linha('STORE_TEMP', inst.linha, name=a['destino']))
            elif op == 'padrao':
                linhas.append(_linha('PUSH_DEFAULT', inst.linha, type=a['tipo']))
                linhas.append(_linha('STORE_LOCAL', inst.linha, name=a['slot']))
            elif op == 'armazena':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['valor']))
                linhas.append(_linha('STORE_LOCAL', inst.linha, name=a['slot']))
            elif op == 'unario':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['operando']))
                linhas.append(_linha('UNARY', inst.linha, operator=a['operador']))
                linhas.append(_linha('STORE_TEMP', inst.linha, name=a['destino']))
            elif op == 'binario':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['esquerda']))
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['direita']))
                linhas.append(_linha('BINARY', inst.linha,
                                     operator=a['operador'], type=a['tipo']))
                linhas.append(_linha('STORE_TEMP', inst.linha, name=a['destino']))
            elif op == 'converte_real':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['valor']))
                linhas.append(_linha('TO_REAL', inst.linha))
                linhas.append(_linha('STORE_TEMP', inst.linha, name=a['destino']))
            elif op == 'chama':
                for argumento in a['argumentos']:
                    linhas.append(_linha('LOAD_TEMP', inst.linha, name=argumento))
                linhas.append(_linha('CALL', inst.linha, name=a['nome'],
                                     argc=len(a['argumentos'])))
                if a['destino'] is not None:
                    linhas.append(_linha('STORE_TEMP', inst.linha,
                                         name=a['destino']))
                elif a['tipo'] != 'vazio':
                    linhas.append(_linha('POP', inst.linha))
            elif op == 'escreva':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['valor']))
                linhas.append(_linha('PRINT', inst.linha, type=a['tipo']))
            elif op == 'desvia_falso':
                linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['valor']))
                linhas.append(_linha('JUMP_FALSE', inst.linha,
                                     target=a['rotulo']))
            elif op == 'desvia':
                linhas.append(_linha('JUMP', inst.linha, target=a['rotulo']))
            elif op == 'retorne':
                if a['valor'] is not None:
                    linhas.append(_linha('LOAD_TEMP', inst.linha, name=a['valor']))
                linhas.append(_linha('RETURN', inst.linha,
                                     has_value=a['valor'] is not None))
            else:
                raise ValueError(f'instrucao IR desconhecida: {op}')
        linhas.append('END')
    return linhas
