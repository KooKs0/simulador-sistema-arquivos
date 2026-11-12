#!/usr/bin/env python3
"""
Simulador de Sistema de Arquivos - Entrega 3

Recursos:
- Usuarios e grupos
- Autenticacao com PBKDF2
- Permissoes de leitura, escrita e execucao
- Criptografia com Fernet
- Verificacao de integridade com SHA-256
- Integracao com RAID 5 e SSTF

O armazenamento permanece em memoria.
"""

import hashlib
import os
import shlex
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from sistema_arquivos_entrega2 import SistemaArquivosEntrega2
from simulador_sistema_arquivos_entrega1 import (
    ErroSistemaArquivos,
    converter_tamanho,
)


@dataclass
class Usuario:
    nome: str
    grupo: str
    sal: bytes
    senha_hash: bytes


@dataclass
class Protecao:
    dono: str
    grupo: str
    modo: str
    criptografado: bool = False
    hash_armazenado: str = ""


def hash_senha(senha, sal):
    return hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        sal,
        200_000
    )


class SistemaSeguro(SistemaArquivosEntrega2):

    def __init__(self):
        super().__init__(quantidade_blocos=256)

        self.usuarios = {}
        self.grupos = {"root"}
        self.usuario_atual = None

        self.chave = Fernet.generate_key()
        self.cifra = Fernet(self.chave)

        self.protecoes = {
            "/": Protecao("root", "root", "rwxr-xr-x")
        }

        self.cadastrar_usuario(
            "root",
            "root123",
            "root",
            interno=True
        )

    def cadastrar_usuario(
        self,
        nome,
        senha,
        grupo,
        interno=False
    ):
        if not interno:
            self.exigir_root()

        if not nome or "/" in nome or nome in self.usuarios:
            raise ErroSistemaArquivos(
                "Nome de usuario invalido ou ja existente."
            )

        if grupo not in self.grupos:
            raise ErroSistemaArquivos(
                "O grupo nao existe."
            )

        if not senha:
            raise ErroSistemaArquivos(
                "A senha nao pode estar vazia."
            )

        sal = os.urandom(16)

        self.usuarios[nome] = Usuario(
            nome,
            grupo,
            sal,
            hash_senha(senha, sal)
        )

    def login(self, nome, senha):
        usuario = self.usuarios.get(nome)

        if (
            usuario is None
            or hash_senha(senha, usuario.sal) != usuario.senha_hash
        ):
            raise ErroSistemaArquivos(
                "Usuario ou senha incorretos."
            )

        self.usuario_atual = nome
        self.diretorio_atual = self.raiz

    def exigir_login(self):
        if self.usuario_atual is None:
            raise ErroSistemaArquivos(
                "Faca login antes de usar o sistema."
            )

    def exigir_root(self):
        self.exigir_login()

        if self.usuario_atual != "root":
            raise ErroSistemaArquivos(
                "Operacao permitida apenas ao root."
            )

    def caminho(self, caminho):
        if not caminho:
            raise ErroSistemaArquivos(
                "Informe um caminho."
            )

        partes = (
            []
            if caminho.startswith("/")
            else [p for p in self.pwd().split("/") if p]
        )

        for parte in caminho.split("/"):
            if parte in ("", "."):
                continue

            if parte == "..":
                if partes:
                    partes.pop()
            else:
                partes.append(parte)

        return "/" + "/".join(partes)

    def verificar(self, caminho, permissao):
        self.exigir_login()

        if self.usuario_atual == "root":
            return

        info = self.protecoes.get(caminho)

        if info is None:
            raise ErroSistemaArquivos(
                "Metadados de permissao nao encontrados."
            )

        usuario = self.usuarios[self.usuario_atual]

        if usuario.nome == info.dono:
            trecho = info.modo[:3]

        elif usuario.grupo == info.grupo:
            trecho = info.modo[3:6]

        else:
            trecho = info.modo[6:9]

        if permissao not in trecho:
            raise ErroSistemaArquivos(
                f"Permissao negada: {permissao} em {caminho}."
            )

    def verificar_travessia(self, caminho):
        partes = [
            p for p in caminho.split("/") if p
        ]

        atual = "/"
        self.verificar(atual, "x")

        for parte in partes[:-1]:
            atual = atual.rstrip("/") + "/" + parte
            self.verificar(atual, "x")

    def verificar_pai(self, caminho):
        self.verificar_travessia(caminho)

        pai = caminho.rpartition("/")[0] or "/"

        self.verificar(pai, "w")
        self.verificar(pai, "x")

    def metadados_novos(self, caminho, diretorio=False):
        usuario = self.usuarios[self.usuario_atual]

        modo = (
            "rwxr-xr-x"
            if diretorio
            else "rw-r-----"
        )

        self.protecoes[caminho] = Protecao(
            usuario.nome,
            usuario.grupo,
            modo
        )

    def mkdir_seguro(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_pai(absoluto)
        super().mkdir(caminho)

        self.metadados_novos(
            absoluto,
            diretorio=True
        )

    def criar_seguro(self, caminho, tamanho=0):
        absoluto = self.caminho(caminho)

        self.verificar_pai(absoluto)

        if tamanho < 0:
            raise ErroSistemaArquivos(
                "Tamanho invalido."
            )

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes de gravar."
            )

        super().create_file(
            caminho,
            "\0" * tamanho
        )

        self.metadados_novos(absoluto)
        self.atualizar_hash(absoluto)

    def arquivo_no(self, caminho):
        pai, nome = self._separar_caminho(caminho)

        if nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                "Arquivo nao encontrado."
            )

        return pai.arquivos[nome]

    def bytes_armazenados(self, caminho):
        arquivo = self.arquivo_no(caminho)

        dados = b"".join(
            self.raid.ler_bloco(numero)
            for numero in arquivo.blocos_dados
        )

        return dados[:arquivo.tamanho]

    def atualizar_hash(self, caminho):
        dados = self.bytes_armazenados(caminho)

        self.protecoes[caminho].hash_armazenado = (
            hashlib.sha256(dados).hexdigest()
        )

    def verificar_integridade(self, caminho):
        dados = self.bytes_armazenados(caminho)

        atual = hashlib.sha256(dados).hexdigest()

        if atual != self.protecoes[caminho].hash_armazenado:
            raise ErroSistemaArquivos(
                "Falha de integridade: "
                "conteudo alterado no armazenamento."
            )

        return dados

    def ler_seguro(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "r")

        dados = self.verificar_integridade(absoluto)

        if self.protecoes[absoluto].criptografado:
            try:
                dados = self.cifra.decrypt(dados)

            except InvalidToken as erro:
                raise ErroSistemaArquivos(
                    "Nao foi possivel descriptografar o arquivo."
                ) from erro

        return dados.decode("utf-8")

    def gravar_seguro(
        self,
        caminho,
        texto,
        acrescentar=False
    ):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "w")

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes de gravar."
            )

        if acrescentar:
            self.verificar(absoluto, "r")
            texto = self.ler_seguro(caminho) + texto

        dados = texto.encode("utf-8")

        if self.protecoes[absoluto].criptografado:
            dados = self.cifra.encrypt(dados)

        self._gravar_conteudo(
            self.arquivo_no(caminho),
            dados
        )

        self.atualizar_hash(absoluto)

    def criptografar(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "r")
        self.verificar(absoluto, "w")

        if self.protecoes[absoluto].criptografado:
            raise ErroSistemaArquivos(
                "O arquivo ja esta criptografado."
            )

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes de gravar."
            )

        dados = self.verificar_integridade(absoluto)

        dados_criptografados = self.cifra.encrypt(dados)

        self._gravar_conteudo(
            self.arquivo_no(caminho),
            dados_criptografados
        )

        self.protecoes[absoluto].criptografado = True
        self.atualizar_hash(absoluto)

    def descriptografar(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "r")
        self.verificar(absoluto, "w")

        if not self.protecoes[absoluto].criptografado:
            raise ErroSistemaArquivos(
                "O arquivo nao esta criptografado."
            )

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes de gravar."
            )

        dados = self.verificar_integridade(absoluto)

        try:
            texto = self.cifra.decrypt(dados)

        except InvalidToken as erro:
            raise ErroSistemaArquivos(
                "Nao foi possivel descriptografar o arquivo."
            ) from erro

        self._gravar_conteudo(
            self.arquivo_no(caminho),
            texto
        )

        self.protecoes[absoluto].criptografado = False
        self.atualizar_hash(absoluto)

    def remover_seguro(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_pai(absoluto)

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes de remover."
            )

        super().rm(caminho)

        self.protecoes.pop(absoluto, None)

    def remover_diretorio_seguro(self, caminho):
        absoluto = self.caminho(caminho)

        if absoluto == "/":
            raise ErroSistemaArquivos(
                "Nao e possivel remover a raiz."
            )

        self.verificar_pai(absoluto)
        super().rmdir(caminho)

        self.protecoes.pop(absoluto, None)

    def listar_seguro(self, caminho="."):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "r")
        self.verificar(absoluto, "x")

        return super().ls(caminho)

    def entrar_seguro(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "x")

        super().cd(caminho)

    def arvore_segura(self, caminho="/"):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)
        self.verificar(absoluto, "r")
        self.verificar(absoluto, "x")

        self.exigir_root()

        return super().tree(caminho)

    def chmod(self, caminho, modo):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)

        info = self.protecoes.get(absoluto)

        if info is None:
            raise ErroSistemaArquivos(
                "Caminho nao encontrado."
            )

        if self.usuario_atual not in ("root", info.dono):
            raise ErroSistemaArquivos(
                "Apenas o dono ou root pode alterar permissoes."
            )

        if len(modo) != 9 or any(
            letra not in (esperado, "-")
            for letra, esperado in zip(
                modo,
                "rwxrwxrwx"
            )
        ):
            raise ErroSistemaArquivos(
                "Modo invalido. Exemplo: rw-r-----"
            )

        info.modo = modo

    def chown(self, caminho, usuario):
        self.exigir_root()

        absoluto = self.caminho(caminho)

        if (
            absoluto not in self.protecoes
            or usuario not in self.usuarios
        ):
            raise ErroSistemaArquivos(
                "Arquivo/diretorio ou usuario inexistente."
            )

        self.protecoes[absoluto].dono = usuario
        self.protecoes[absoluto].grupo = (
            self.usuarios[usuario].grupo
        )

    def detalhes_seguranca(self, caminho):
        absoluto = self.caminho(caminho)

        self.verificar_travessia(absoluto)

        info = self.protecoes.get(absoluto)

        if info is None:
            raise ErroSistemaArquivos(
                "Caminho nao encontrado."
            )

        return (
            f"Caminho: {absoluto}\n"
            f"Dono: {info.dono}\n"
            f"Grupo: {info.grupo}\n"
            f"Permissoes: {info.modo}\n"
            f"Criptografado: "
            f"{'sim' if info.criptografado else 'nao'}"
        )

    def varredura(self):
        self.exigir_root()

        resultados = []

        def visitar(diretorio, caminho):
            for nome in sorted(diretorio.arquivos):
                absoluto = (
                    caminho.rstrip("/") + "/" + nome
                )

                try:
                    self.verificar_integridade(absoluto)

                    resultados.append(
                        f"OK: {absoluto}"
                    )

                except ErroSistemaArquivos:
                    resultados.append(
                        f"ALERTA: alteracao detectada em {absoluto}"
                    )

            for nome, filho in sorted(
                diretorio.diretorios.items()
            ):
                proximo = (
                    caminho.rstrip("/") + "/" + nome
                )

                visitar(filho, proximo)

        visitar(self.raiz, "/")

        if not resultados:
            return "Nenhum arquivo para verificar."

        return "\n".join(resultados)

    def corromper_para_teste(self, caminho):
        self.exigir_root()

        absoluto = self.caminho(caminho)
        arquivo = self.arquivo_no(caminho)

        if not arquivo.blocos_dados:
            raise ErroSistemaArquivos(
                "O arquivo nao possui blocos de dados."
            )

        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Reconstrua o RAID antes deste teste."
            )

        numero = arquivo.blocos_dados[0]

        dados = bytearray(
            self.raid.ler_bloco(numero)
        )

        dados[0] ^= 1

        self.raid.gravar_bloco(
            numero,
            bytes(dados)
        )

        # O hash oficial permanece igual para detectar a alteracao.
        return absoluto


AJUDA = """
Comandos da Entrega 3:

  login USUARIO SENHA            Autentica um usuario.
  logout                         Encerra a sessao.
  whoami                         Mostra o usuario atual.
  useradd USUARIO SENHA GRUPO    Cadastra usuario (root).
  groupadd GRUPO                 Cria grupo (root).
  chmod CAMINHO MODO             Altera permissoes.
  chown CAMINHO USUARIO          Altera proprietario (root).
  permissions CAMINHO            Mostra dono, grupo e permissoes.
  encrypt CAMINHO                Criptografa um arquivo.
  decrypt CAMINHO                Descriptografa um arquivo.
  antivirus_scan                 Verifica integridade (root).
  corrupt CAMINHO                Altera um bloco para teste (root).

Comandos anteriores:

  mkdir CAMINHO
  cd CAMINHO
  pwd
  ls [CAMINHO]
  tree
  create CAMINHO [--size TAM]
  read CAMINHO
  write CAMINHO TEXTO
  append CAMINHO TEXTO
  rm CAMINHO
  rmdir CAMINHO
  stat CAMINHO
  fs_status [--details]

  raid_status
  raid_fail NUMERO
  raid_rebuild

  io_status
  io_history
  io_clear

  help
  exit

Conta inicial: root / root123

O sistema e uma simulacao em memoria.
Os dados nao persistem entre execucoes.
"""


def executar(sistema, linha):
    try:
        args = shlex.split(linha)

        if not args:
            return True

        cmd = args[0].lower()

        if cmd in ("exit", "quit"):
            return False

        if cmd == "help":
            print(AJUDA)
            return True

        if cmd == "login":
            if len(args) != 3:
                raise ErroSistemaArquivos(
                    "Uso: login USUARIO SENHA"
                )

            sistema.login(args[1], args[2])

            print(
                f"Sessao iniciada: {sistema.usuario_atual}"
            )

            return True

        if cmd == "logout":
            sistema.exigir_login()

            sistema.usuario_atual = None
            sistema.diretorio_atual = sistema.raiz

            print("Sessao encerrada.")
            return True

        sistema.exigir_login()

        if cmd == "whoami":
            print(sistema.usuario_atual)

        elif cmd == "groupadd" and len(args) == 2:
            sistema.exigir_root()

            if (
                not args[1]
                or "/" in args[1]
                or args[1] in sistema.grupos
            ):
                raise ErroSistemaArquivos(
                    "Grupo invalido ou ja existente."
                )

            sistema.grupos.add(args[1])
            print("Grupo criado.")

        elif cmd == "useradd" and len(args) == 4:
            sistema.cadastrar_usuario(
                args[1],
                args[2],
                args[3]
            )

            print("Usuario cadastrado.")

        elif cmd == "pwd" and len(args) == 1:
            print(sistema.pwd())

        elif cmd == "mkdir" and len(args) == 2:
            sistema.mkdir_seguro(args[1])
            print("Diretorio criado.")

        elif cmd == "cd" and len(args) <= 2:
            caminho = (
                args[1]
                if len(args) == 2
                else "/"
            )

            sistema.entrar_seguro(caminho)
            print(sistema.pwd())

        elif cmd == "ls" and len(args) <= 2:
            caminho = (
                args[1]
                if len(args) == 2
                else "."
            )

            itens = sistema.listar_seguro(caminho)

            print(
                "\n".join(itens)
                if itens
                else "Diretorio vazio."
            )

        elif cmd == "tree" and len(args) <= 2:
            caminho = (
                args[1]
                if len(args) == 2
                else "/"
            )

            print(sistema.arvore_segura(caminho))

        elif cmd == "create" and (
            len(args) == 2
            or (
                len(args) == 4
                and args[2] == "--size"
            )
        ):
            tamanho = (
                converter_tamanho(args[3])
                if len(args) == 4
                else 0
            )

            sistema.criar_seguro(
                args[1],
                tamanho
            )

            print("Arquivo criado.")

        elif cmd == "read" and len(args) == 2:
            texto = sistema.ler_seguro(args[1])

            print(
                texto
                if texto
                else "O arquivo esta vazio."
            )

        elif cmd in ("write", "append") and len(args) >= 3:
            sistema.gravar_seguro(
                args[1],
                " ".join(args[2:]),
                cmd == "append"
            )

            print("Arquivo atualizado.")

        elif cmd == "rm" and len(args) == 2:
            sistema.remover_seguro(args[1])
            print("Arquivo removido.")

        elif cmd == "rmdir" and len(args) == 2:
            sistema.remover_diretorio_seguro(args[1])
            print("Diretorio removido.")

        elif cmd == "stat" and len(args) == 2:
            absoluto = sistema.caminho(args[1])

            sistema.verificar_travessia(absoluto)
            sistema.verificar(absoluto, "r")

            print(sistema.stat(args[1]))
            print(sistema.detalhes_seguranca(args[1]))

        elif cmd == "permissions" and len(args) == 2:
            print(
                sistema.detalhes_seguranca(args[1])
            )

        elif cmd == "chmod" and len(args) == 3:
            sistema.chmod(args[1], args[2])
            print("Permissoes atualizadas.")

        elif cmd == "chown" and len(args) == 3:
            sistema.chown(args[1], args[2])
            print("Proprietario atualizado.")

        elif cmd == "encrypt" and len(args) == 2:
            sistema.criptografar(args[1])
            print("Arquivo criptografado.")

        elif cmd == "decrypt" and len(args) == 2:
            sistema.descriptografar(args[1])
            print("Arquivo descriptografado.")

        elif cmd == "antivirus_scan" and len(args) == 1:
            print(sistema.varredura())

        elif cmd == "corrupt" and len(args) == 2:
            caminho = sistema.corromper_para_teste(
                args[1]
            )

            print(
                "Bloco alterado para teste:",
                caminho
            )

        elif cmd == "fs_status" and (
            len(args) == 1
            or args == ["fs_status", "--details"]
        ):
            sistema.exigir_root()

            print(
                sistema.fs_status(
                    len(args) == 2
                )
            )

        elif cmd == "raid_status" and len(args) == 1:
            print(sistema.raid.status())

        elif cmd == "raid_fail" and len(args) == 2:
            sistema.exigir_root()

            try:
                numero = int(args[1])

            except ValueError as erro:
                raise ErroSistemaArquivos(
                    "Informe um numero de disco valido."
                ) from erro

            sistema.raid.simular_falha(numero)

            print(
                f"Falha simulada no disco {numero}."
            )

        elif cmd == "raid_rebuild" and len(args) == 1:
            sistema.exigir_root()
            sistema.raid.reconstruir_disco()

            print("Disco reconstruido.")

        elif cmd == "io_status" and len(args) == 1:
            print(
                sistema.escalonador.relatorio()
            )

        elif cmd == "io_history" and len(args) == 1:
            historico = (
                sistema.escalonador.historico[-20:]
            )

            if not historico:
                print(
                    "Nenhuma operacao registrada."
                )

            for requisicao, movimento in historico:
                print(
                    f"Disco {requisicao.disco + 1} | "
                    f"{requisicao.operacao} | "
                    f"trilha {requisicao.trilha} | "
                    f"movimento {movimento}"
                )

        elif cmd == "io_clear" and len(args) == 1:
            sistema.exigir_root()
            sistema.escalonador.limpar_historico()

            print("Historico limpo.")

        else:
            print(
                "Comando ou argumentos invalidos. "
                "Digite help."
            )

    except (
        ErroSistemaArquivos,
        UnicodeDecodeError
    ) as erro:
        print(f"Erro: {erro}")

    return True


def iniciar():
    sistema = SistemaSeguro()

    print(
        "Simulador de Sistema de Arquivos - Entrega 3"
    )
    print(
        "Autenticacao, permissoes, criptografia e integridade"
    )
    print(
        "Digite help para consultar os comandos."
    )
    print(
        "Para iniciar os testes: login root root123"
    )

    while True:
        try:
            usuario = (
                sistema.usuario_atual
                or "sem-login"
            )

            linha = input(
                f"{usuario}:{sistema.pwd()} $ "
            )

        except (EOFError, KeyboardInterrupt):
            print("\nSimulador encerrado.")
            break

        if not executar(sistema, linha):
            print("Simulador encerrado.")
            break


if __name__ == "__main__":
    iniciar()
