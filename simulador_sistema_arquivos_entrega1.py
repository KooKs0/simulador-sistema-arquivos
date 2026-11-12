#!/usr/bin/env python3
"""
Simulador de Sistema de Arquivos - Entrega 1

Implementa:
- Árvore hierárquica de diretórios.
- Navegação por caminhos absolutos e relativos.
- Operações de criação, leitura, atualização e remoção de arquivos.
- Alocação indexada de blocos de tamanho fixo.
- Relatório de ocupação e fragmentação do armazenamento.

Os diretórios são estruturas lógicas e não ocupam blocos de dados.
Cada arquivo possui um bloco de índice e zero ou mais blocos de dados.
"""

from __future__ import annotations

import shlex
import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


TAMANHO_BLOCO = 4096
MAX_REFERENCIAS_POR_INDICE = TAMANHO_BLOCO // 4


@dataclass
class Bloco:
    numero: int
    tipo: str = "livre"
    dono: Optional[str] = None
    conteudo: bytes = b""


@dataclass
class NoArquivo:
    nome: str
    tamanho: int
    data_criacao: datetime = field(default_factory=datetime.now)
    data_modificacao: datetime = field(default_factory=datetime.now)
    bloco_indice: Optional[int] = None
    blocos_dados: list[int] = field(default_factory=list)


@dataclass
class Diretorio:
    nome: str
    pai: Optional["Diretorio"] = None
    diretorios: dict[str, "Diretorio"] = field(default_factory=dict)
    arquivos: dict[str, NoArquivo] = field(default_factory=dict)


class ErroSistemaArquivos(Exception):
    """Erro esperado durante uma operação do sistema de arquivos."""


class SistemaArquivos:
    def __init__(self, quantidade_blocos: int = 256):
        if quantidade_blocos < 2:
            raise ValueError("O sistema precisa ter pelo menos dois blocos.")

        self.blocos = [Bloco(numero=i) for i in range(quantidade_blocos)]
        self.raiz = Diretorio(nome="/")
        self.diretorio_atual = self.raiz

    def _separar_caminho(self, caminho: str) -> tuple[Diretorio, str]:
        caminho = caminho.strip()
        if not caminho:
            raise ErroSistemaArquivos("O caminho não pode estar vazio.")

        partes = [parte for parte in caminho.split("/") if parte]

        if caminho.startswith("/"):
            atual = self.raiz
        else:
            atual = self.diretorio_atual

        if not partes:
            return atual, ""

        for parte in partes[:-1]:
            if parte == ".":
                continue

            if parte == "..":
                if atual.pai is not None:
                    atual = atual.pai
                continue

            proximo = atual.diretorios.get(parte)

            if proximo is None:
                raise ErroSistemaArquivos(
                    f"Diretório não encontrado no caminho: {parte}"
                )

            atual = proximo

        nome = partes[-1]

        if nome in (".", ".."):
            if nome == ".." and atual.pai is not None:
                atual = atual.pai

            return atual, ""

        return atual, nome

    def _resolver_diretorio(self, caminho: str) -> Diretorio:
        caminho = caminho.strip()

        if caminho in ("", "."):
            return self.diretorio_atual

        if caminho == "/":
            return self.raiz

        partes = [parte for parte in caminho.split("/") if parte]

        atual = self.raiz if caminho.startswith("/") else self.diretorio_atual

        for parte in partes:
            if parte == ".":
                continue

            if parte == "..":
                if atual.pai is not None:
                    atual = atual.pai
                continue

            if parte not in atual.diretorios:
                raise ErroSistemaArquivos(
                    f"Diretório não encontrado: "
                    f"{self._caminho_absoluto(atual)}/{parte}"
                )

            atual = atual.diretorios[parte]

        return atual

    def _caminho_absoluto(self, diretorio: Diretorio) -> str:
        if diretorio is self.raiz:
            return "/"

        partes = []
        atual = diretorio

        while atual is not None and atual is not self.raiz:
            partes.append(atual.nome)
            atual = atual.pai

        return "/" + "/".join(reversed(partes))

    def pwd(self) -> str:
        return self._caminho_absoluto(self.diretorio_atual)

    def mkdir(self, caminho: str) -> None:
        pai, nome = self._separar_caminho(caminho)

        if not nome:
            raise ErroSistemaArquivos("Informe o nome do novo diretório.")

        if nome in pai.diretorios or nome in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Já existe um item com o nome '{nome}'."
            )

        novo = Diretorio(nome=nome, pai=pai)
        pai.diretorios[nome] = novo

    def cd(self, caminho: str = "/") -> None:
        self.diretorio_atual = self._resolver_diretorio(caminho)

    def ls(self, caminho: str = ".") -> list[str]:
        diretorio = self._resolver_diretorio(caminho)

        itens = []

        itens.extend(
            f"{nome}/" for nome in sorted(diretorio.diretorios)
        )

        itens.extend(sorted(diretorio.arquivos))

        return itens

    def tree(self, caminho: str = "/") -> str:
        inicio = self._resolver_diretorio(caminho)

        linhas = [
            inicio.nome if inicio is self.raiz else inicio.nome
        ]

        def percorrer(diretorio: Diretorio, prefixo: str) -> None:
            itens = []

            itens.extend(
                (nome + "/", diretorio.diretorios[nome])
                for nome in sorted(diretorio.diretorios)
            )

            itens.extend(
                (nome, diretorio.arquivos[nome])
                for nome in sorted(diretorio.arquivos)
            )

            for indice, (nome, item) in enumerate(itens):
                ultimo = indice == len(itens) - 1

                marcador = "`-- " if ultimo else "|-- "

                linhas.append(prefixo + marcador + nome)

                if isinstance(item, Diretorio):
                    novo_prefixo = prefixo + (
                        "    " if ultimo else "|   "
                    )

                    percorrer(item, novo_prefixo)

        percorrer(inicio, "")

        return "\n".join(linhas)

    def _blocos_livres(self) -> list[int]:
        return [
            bloco.numero
            for bloco in self.blocos
            if bloco.tipo == "livre"
        ]

    def _reservar_bloco(self, tipo: str, dono: str) -> int:
        for bloco in self.blocos:
            if bloco.tipo == "livre":
                bloco.tipo = tipo
                bloco.dono = dono
                bloco.conteudo = b""

                return bloco.numero

        raise ErroSistemaArquivos(
            "Não há blocos livres suficientes no disco."
        )

    def _liberar_bloco(self, numero: int) -> None:
        bloco = self.blocos[numero]

        bloco.tipo = "livre"
        bloco.dono = None
        bloco.conteudo = b""

    def _gravar_conteudo(
        self,
        arquivo: NoArquivo,
        conteudo: bytes
    ) -> None:

        quantidade = (
            len(conteudo) + TAMANHO_BLOCO - 1
        ) // TAMANHO_BLOCO

        if quantidade > MAX_REFERENCIAS_POR_INDICE:
            raise ErroSistemaArquivos(
                "O arquivo ultrapassa a capacidade de um único bloco de índice."
            )

        blocos_novos: list[int] = []
        indice_novo: Optional[int] = None

        try:
            indice_novo = self._reservar_bloco(
                "indice",
                arquivo.nome
            )

            for _ in range(quantidade):
                blocos_novos.append(
                    self._reservar_bloco("dados", arquivo.nome)
                )

        except ErroSistemaArquivos:
            for numero in blocos_novos:
                self._liberar_bloco(numero)

            if indice_novo is not None:
                self._liberar_bloco(indice_novo)

            raise

        for posicao, numero in enumerate(blocos_novos):
            inicio = posicao * TAMANHO_BLOCO
            fim = inicio + TAMANHO_BLOCO

            self.blocos[numero].conteudo = conteudo[inicio:fim]

        referencias = b"".join(
            struct.pack("<I", numero)
            for numero in blocos_novos
        )

        self.blocos[indice_novo].conteudo = referencias

        for numero in arquivo.blocos_dados:
            self._liberar_bloco(numero)

        if arquivo.bloco_indice is not None:
            self._liberar_bloco(arquivo.bloco_indice)

        arquivo.bloco_indice = indice_novo
        arquivo.blocos_dados = blocos_novos
        arquivo.tamanho = len(conteudo)
        arquivo.data_modificacao = datetime.now()

    def create_file(
        self,
        caminho: str,
        conteudo: str = ""
    ) -> None:

        pai, nome = self._separar_caminho(caminho)

        if not nome:
            raise ErroSistemaArquivos("Informe o nome do arquivo.")

        if nome in pai.diretorios or nome in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Já existe um item com o nome '{nome}'."
            )

        arquivo = NoArquivo(nome=nome, tamanho=0)

        self._gravar_conteudo(
            arquivo,
            conteudo.encode("utf-8")
        )

        pai.arquivos[nome] = arquivo

    def read_file(self, caminho: str) -> str:
        pai, nome = self._separar_caminho(caminho)

        if not nome or nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Arquivo não encontrado: {caminho}"
            )

        arquivo = pai.arquivos[nome]

        partes = [
            self.blocos[numero].conteudo
            for numero in arquivo.blocos_dados
        ]

        return b"".join(partes).decode("utf-8")

    def write_file(
        self,
        caminho: str,
        conteudo: str,
        acrescentar: bool = False
    ) -> None:

        pai, nome = self._separar_caminho(caminho)

        if not nome or nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Arquivo não encontrado: {caminho}"
            )

        arquivo = pai.arquivos[nome]

        texto_atual = (
            self.read_file(caminho)
            if acrescentar
            else ""
        )

        novo_conteudo = (
            texto_atual + conteudo
        ).encode("utf-8")

        self._gravar_conteudo(
            arquivo,
            novo_conteudo
        )

    def rm(self, caminho: str) -> None:
        pai, nome = self._separar_caminho(caminho)

        if not nome or nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Arquivo não encontrado: {caminho}"
            )

        arquivo = pai.arquivos.pop(nome)

        for numero in arquivo.blocos_dados:
            self._liberar_bloco(numero)

        if arquivo.bloco_indice is not None:
            self._liberar_bloco(arquivo.bloco_indice)

    def rmdir(self, caminho: str) -> None:
        diretorio = self._resolver_diretorio(caminho)

        if diretorio is self.raiz:
            raise ErroSistemaArquivos(
                "A raiz do sistema não pode ser removida."
            )

        if diretorio.diretorios or diretorio.arquivos:
            raise ErroSistemaArquivos(
                "O diretório não está vazio."
            )

        pai = diretorio.pai

        if pai is not None:
            del pai.diretorios[diretorio.nome]

        if self.diretorio_atual is diretorio:
            self.diretorio_atual = (
                pai if pai is not None else self.raiz
            )

    def stat(self, caminho: str) -> str:
        pai, nome = self._separar_caminho(caminho)

        if not nome or nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Arquivo não encontrado: {caminho}"
            )

        arquivo = pai.arquivos[nome]

        blocos_alocados = len(arquivo.blocos_dados)
        espaco_alocado = blocos_alocados * TAMANHO_BLOCO
        fragmentacao = espaco_alocado - arquivo.tamanho

        return (
            f"Arquivo: {nome}\n"
            f"Tamanho: {arquivo.tamanho} bytes\n"
            f"Bloco de índice: {arquivo.bloco_indice}\n"
            f"Blocos de dados: {arquivo.blocos_dados}\n"
            f"Espaço de dados alocado: {espaco_alocado} bytes\n"
            f"Fragmentação interna: {fragmentacao} bytes\n"
            f"Criado em: {arquivo.data_criacao:%d/%m/%Y %H:%M:%S}\n"
            f"Modificado em: {arquivo.data_modificacao:%d/%m/%Y %H:%M:%S}"
        )

    def _contar_arquivos(self, diretorio: Diretorio) -> int:
        total = len(diretorio.arquivos)

        for filho in diretorio.diretorios.values():
            total += self._contar_arquivos(filho)

        return total

    def fs_status(self, detalhes: bool = False) -> str:
        total = len(self.blocos)

        indices = [
            bloco for bloco in self.blocos
            if bloco.tipo == "indice"
        ]

        dados = [
            bloco for bloco in self.blocos
            if bloco.tipo == "dados"
        ]

        livres = [
            bloco for bloco in self.blocos
            if bloco.tipo == "livre"
        ]

        bytes_arquivos = sum(
            len(bloco.conteudo)
            for bloco in dados
        )

        bytes_alocados = len(dados) * TAMANHO_BLOCO

        fragmentacao_interna = (
            bytes_alocados - bytes_arquivos
        )

        espaco_livre = len(livres) * TAMANHO_BLOCO

        linhas = [
            "Estado do sistema de arquivos",
            f"Tamanho de cada bloco: {TAMANHO_BLOCO} bytes",
            f"Total de blocos: {total}",
            f"Blocos de índice ocupados: {len(indices)}",
            f"Blocos de dados ocupados: {len(dados)}",
            f"Blocos livres: {len(livres)}",
            f"Espaço livre: {espaco_livre} bytes",
            f"Fragmentação interna: {fragmentacao_interna} bytes",
            "Fragmentação externa: não aplicável à alocação indexada",
            "Compactação: não necessária para reunir blocos livres",
            f"Arquivos armazenados: {self._contar_arquivos(self.raiz)}",
        ]

        if detalhes:
            linhas.append("")
            linhas.append("Mapa de blocos:")

            for bloco in self.blocos:
                if bloco.tipo == "livre":
                    estado = "livre"
                else:
                    estado = f"{bloco.tipo} - {bloco.dono}"

                linhas.append(
                    f"Bloco {bloco.numero:03d}: {estado}"
                )

        return "\n".join(linhas)


AJUDA = """
Comandos disponíveis:

  mkdir CAMINHO                  Cria um diretório.
  cd [CAMINHO]                   Muda o diretório atual. Sem caminho, volta à raiz.
  pwd                            Mostra o caminho atual.
  ls [CAMINHO]                   Lista diretórios e arquivos.
  tree [CAMINHO]                 Exibe a árvore de diretórios.
  create CAMINHO [--size TAM]    Cria um arquivo. Ex.: create /docs/a.txt --size 10KB
  read CAMINHO                   Exibe o conteúdo de um arquivo.
  write CAMINHO TEXTO            Substitui o conteúdo de um arquivo.
  append CAMINHO TEXTO           Acrescenta texto ao final de um arquivo.
  rm CAMINHO                     Remove um arquivo e libera seus blocos.
  rmdir CAMINHO                  Remove um diretório vazio.
  stat CAMINHO                   Mostra os detalhes de um arquivo.
  fs_status [--details]          Mostra a ocupação e a fragmentação do disco.
  help                           Mostra esta ajuda.
  exit                           Encerra o simulador.

Os caminhos podem ser absolutos (começam com /) ou relativos ao diretório atual.
Para escrever um texto com espaços, coloque-o entre aspas.
"""


def converter_tamanho(valor: str) -> int:
    texto = valor.strip().upper()
    multiplicador = 1

    if texto.endswith("KB"):
        multiplicador = 1024
        texto = texto[:-2]

    elif texto.endswith("MB"):
        multiplicador = 1024 * 1024
        texto = texto[:-2]

    elif texto.endswith("B"):
        texto = texto[:-1]

    try:
        tamanho = int(texto) * multiplicador

    except ValueError as erro:
        raise ErroSistemaArquivos(
            "Tamanho inválido. Use, por exemplo, 500B, 10KB ou 1MB."
        ) from erro

    if tamanho < 0:
        raise ErroSistemaArquivos(
            "O tamanho não pode ser negativo."
        )

    return tamanho


def executar_comando(
    sistema: SistemaArquivos,
    linha: str
) -> bool:

    try:
        argumentos = shlex.split(linha)

        if not argumentos:
            return True

        comando = argumentos[0].lower()

        if comando == "help":
            print(AJUDA)

        elif comando in ("exit", "quit"):
            return False

        elif comando == "pwd":
            print(sistema.pwd())

        elif comando == "mkdir":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: mkdir CAMINHO"
                )

            sistema.mkdir(argumentos[1])
            print("Diretório criado.")

        elif comando == "cd":
            sistema.cd(
                argumentos[1] if len(argumentos) > 1 else "/"
            )

            print(sistema.pwd())

        elif comando == "ls":
            caminho = (
                argumentos[1]
                if len(argumentos) > 1
                else "."
            )

            itens = sistema.ls(caminho)

            print(
                "\n".join(itens)
                if itens
                else "Diretório vazio."
            )

        elif comando == "tree":
            caminho = (
                argumentos[1]
                if len(argumentos) > 1
                else "/"
            )

            print(sistema.tree(caminho))

        elif comando == "create":
            if len(argumentos) < 2:
                raise ErroSistemaArquivos(
                    "Uso: create CAMINHO [--size TAM]"
                )

            caminho = argumentos[1]
            tamanho = 0

            if len(argumentos) == 4 and argumentos[2] == "--size":
                tamanho = converter_tamanho(argumentos[3])

            elif len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: create CAMINHO [--size TAM]"
                )

            sistema.create_file(
                caminho,
                "\0" * tamanho
            )

            print("Arquivo criado.")

        elif comando == "read":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: read CAMINHO"
                )

            conteudo = sistema.read_file(argumentos[1])

            print(
                conteudo
                if conteudo
                else "O arquivo está vazio."
            )

        elif comando in ("write", "append"):
            if len(argumentos) < 3:
                raise ErroSistemaArquivos(
                    f"Uso: {comando} CAMINHO TEXTO"
                )

            caminho = argumentos[1]
            texto = " ".join(argumentos[2:])

            sistema.write_file(
                caminho,
                texto,
                acrescentar=(comando == "append")
            )

            print("Arquivo atualizado.")

        elif comando == "rm":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: rm CAMINHO"
                )

            sistema.rm(argumentos[1])
            print("Arquivo removido e blocos liberados.")

        elif comando == "rmdir":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: rmdir CAMINHO"
                )

            sistema.rmdir(argumentos[1])
            print("Diretório removido.")

        elif comando == "stat":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: stat CAMINHO"
                )

            print(sistema.stat(argumentos[1]))

        elif comando == "fs_status":
            detalhes = (
                len(argumentos) > 1
                and argumentos[1] == "--details"
            )

            print(sistema.fs_status(detalhes))

        else:
            raise ErroSistemaArquivos(
                f"Comando desconhecido: {comando}. "
                "Digite 'help' para ver os comandos."
            )

    except ErroSistemaArquivos as erro:
        print(f"Erro: {erro}")

    except UnicodeDecodeError:
        print(
            "Erro: o conteúdo do arquivo não pôde "
            "ser interpretado como texto UTF-8."
        )

    return True


def iniciar() -> None:
    sistema = SistemaArquivos(quantidade_blocos=256)

    print("Simulador de Sistema de Arquivos - Entrega 1")
    print(
        f"Disco virtual: {len(sistema.blocos)} blocos "
        f"de {TAMANHO_BLOCO} bytes"
    )
    print("Digite 'help' para consultar os comandos.")

    while True:
        try:
            linha = input(f"{sistema.pwd()} $ ")

        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando o simulador.")
            break

        if not executar_comando(sistema, linha):
            print("Simulador encerrado.")
            break


if __name__ == "__main__":
    iniciar()
