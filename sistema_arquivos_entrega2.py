#!/usr/bin/env python3
"""
Simulador de Sistema de Arquivos - Entrega 2

Acrescenta à primeira entrega:
- Armazenamento distribuído em RAID 5 com quatro discos.
- Distribuição de dados e paridade entre os discos.
- Recuperação de dados após a falha de um disco.
- Escalonamento de operações de leitura e escrita com SSTF.

Mantenha este arquivo na mesma pasta de
simulador_sistema_arquivos_entrega1.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from simulador_sistema_arquivos_entrega1 import (
    SistemaArquivos,
    ErroSistemaArquivos,
    TAMANHO_BLOCO,
)


QUANTIDADE_DISCOS = 4


@dataclass
class RequisicaoIO:
    disco: int
    trilha: int
    operacao: str


class EscalonadorSSTF:
    """Atende primeiro a requisição mais próxima da cabeça do disco."""

    def __init__(self) -> None:
        self.cabeca = 0
        self.fila: list[RequisicaoIO] = []
        self.historico: list[tuple[RequisicaoIO, int]] = []
        self.movimento_total = 0

    def adicionar(self, disco: int, trilha: int, operacao: str) -> None:
        self.fila.append(
            RequisicaoIO(
                disco=disco,
                trilha=trilha,
                operacao=operacao
            )
        )

    def executar_fila(self) -> list[tuple[RequisicaoIO, int]]:
        atendidas = []

        while self.fila:
            indice = min(
                range(len(self.fila)),
                key=lambda i: abs(
                    self.fila[i].trilha - self.cabeca
                )
            )

            requisicao = self.fila.pop(indice)

            movimento = abs(
                requisicao.trilha - self.cabeca
            )

            self.movimento_total += movimento
            self.cabeca = requisicao.trilha

            registro = (requisicao, movimento)

            self.historico.append(registro)
            atendidas.append(registro)

        return atendidas

    def limpar_historico(self) -> None:
        self.historico.clear()
        self.movimento_total = 0

    def relatorio(self) -> str:
        linhas = [
            "Estado do escalonador de disco",
            "Algoritmo utilizado: SSTF (Shortest Seek Time First)",
            f"Posição atual da cabeça: trilha {self.cabeca}",
            f"Requisições concluídas: {len(self.historico)}",
            f"Movimento total da cabeça: {self.movimento_total} trilhas",
            f"Requisições aguardando: {len(self.fila)}",
        ]

        if self.historico:
            linhas.append("")
            linhas.append("Últimas operações:")

            for requisicao, movimento in self.historico[-20:]:
                linhas.append(
                    f"Disco {requisicao.disco + 1} | "
                    f"{requisicao.operacao} | "
                    f"trilha {requisicao.trilha} | "
                    f"movimento {movimento}"
                )

        return "\n".join(linhas)


class ControladorRAID5:
    """
    Controlador RAID 5 com quatro discos.

    Cada faixa possui três blocos de dados e um bloco de paridade.
    A posição da paridade muda a cada faixa.
    """

    def __init__(
        self,
        quantidade_blocos_logicos: int,
        escalonador: EscalonadorSSTF
    ) -> None:

        self.quantidade_discos = QUANTIDADE_DISCOS
        self.quantidade_blocos_logicos = quantidade_blocos_logicos
        self.blocos_por_faixa = self.quantidade_discos - 1

        self.quantidade_faixas = (
            quantidade_blocos_logicos + self.blocos_por_faixa - 1
        ) // self.blocos_por_faixa

        self.discos: list[dict[int, bytes]] = [
            {} for _ in range(self.quantidade_discos)
        ]

        self.disco_com_falha: Optional[int] = None
        self.escalonador = escalonador

    def _zeros(self) -> bytes:
        return bytes(TAMANHO_BLOCO)

    def _disco_paridade(self, faixa: int) -> int:
        return faixa % self.quantidade_discos

    def _discos_dados(self, faixa: int) -> list[int]:
        disco_paridade = self._disco_paridade(faixa)

        return [
            disco
            for disco in range(self.quantidade_discos)
            if disco != disco_paridade
        ]

    def _localizar_bloco(
        self,
        bloco_logico: int
    ) -> tuple[int, int, int]:

        if not 0 <= bloco_logico < self.quantidade_blocos_logicos:
            raise ErroSistemaArquivos(
                f"Bloco lógico inválido: {bloco_logico}"
            )

        faixa = bloco_logico // self.blocos_por_faixa
        posicao = bloco_logico % self.blocos_por_faixa

        disco_dados = self._discos_dados(faixa)[posicao]

        return (
            faixa,
            disco_dados,
            self._disco_paridade(faixa)
        )

    def _ler_bloco_fisico(
        self,
        disco: int,
        faixa: int
    ) -> bytes:

        return self.discos[disco].get(
            faixa,
            self._zeros()
        )

    def _registrar_io(
        self,
        disco: int,
        faixa: int,
        operacao: str
    ) -> None:

        self.escalonador.adicionar(
            disco,
            faixa,
            operacao
        )

    def _calcular_paridade(self, faixa: int) -> bytes:
        resultado = bytearray(TAMANHO_BLOCO)

        for disco in self._discos_dados(faixa):
            conteudo = self._ler_bloco_fisico(
                disco,
                faixa
            )

            for indice, valor in enumerate(conteudo):
                resultado[indice] ^= valor

        return bytes(resultado)

    def gravar_bloco(
        self,
        bloco_logico: int,
        conteudo: bytes
    ) -> None:

        if self.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Não é possível gravar enquanto houver um disco em falha. "
                "Execute raid_rebuild primeiro."
            )

        faixa, disco_dados, disco_paridade = (
            self._localizar_bloco(bloco_logico)
        )

        if len(conteudo) > TAMANHO_BLOCO:
            raise ErroSistemaArquivos(
                "O conteúdo ultrapassa o tamanho de um bloco."
            )

        bloco_preenchido = conteudo.ljust(
            TAMANHO_BLOCO,
            b"\0"
        )

        self.discos[disco_dados][faixa] = bloco_preenchido

        self._registrar_io(
            disco_dados,
            faixa,
            "escrita de dados"
        )

        paridade = self._calcular_paridade(faixa)

        self.discos[disco_paridade][faixa] = paridade

        self._registrar_io(
            disco_paridade,
            faixa,
            "escrita de paridade"
        )

        self.escalonador.executar_fila()

    def ler_bloco(self, bloco_logico: int) -> bytes:
        faixa, disco_dados, disco_paridade = (
            self._localizar_bloco(bloco_logico)
        )

        if (
            self.disco_com_falha is None
            or self.disco_com_falha != disco_dados
        ):

            self._registrar_io(
                disco_dados,
                faixa,
                "leitura de dados"
            )

            self.escalonador.executar_fila()

            return self._ler_bloco_fisico(
                disco_dados,
                faixa
            )

        resultado = bytearray(
            self._ler_bloco_fisico(
                disco_paridade,
                faixa
            )
        )

        self._registrar_io(
            disco_paridade,
            faixa,
            "leitura para recuperação"
        )

        for disco in self._discos_dados(faixa):
            if disco == disco_dados:
                continue

            if disco == self.disco_com_falha:
                continue

            conteudo = self._ler_bloco_fisico(
                disco,
                faixa
            )

            self._registrar_io(
                disco,
                faixa,
                "leitura para recuperação"
            )

            for indice, valor in enumerate(conteudo):
                resultado[indice] ^= valor

        self.escalonador.executar_fila()

        return bytes(resultado)

    def simular_falha(self, numero_disco: int) -> None:
        if not 1 <= numero_disco <= self.quantidade_discos:
            raise ErroSistemaArquivos(
                f"Escolha um disco entre 1 e {self.quantidade_discos}."
            )

        if self.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Já existe um disco em falha. "
                "Recupere-o antes de simular outra falha."
            )

        self.disco_com_falha = numero_disco - 1

    def reconstruir_disco(self) -> None:
        if self.disco_com_falha is None:
            raise ErroSistemaArquivos(
                "Não existe disco em falha para reconstruir."
            )

        disco_perdido = self.disco_com_falha

        for faixa in range(self.quantidade_faixas):
            disco_paridade = self._disco_paridade(faixa)

            if disco_perdido == disco_paridade:
                for disco in self._discos_dados(faixa):
                    self._registrar_io(
                        disco,
                        faixa,
                        "leitura para reconstrução"
                    )

                conteudo_reconstruido = self._calcular_paridade(
                    faixa
                )

            else:
                resultado = bytearray(
                    self._ler_bloco_fisico(
                        disco_paridade,
                        faixa
                    )
                )

                self._registrar_io(
                    disco_paridade,
                    faixa,
                    "leitura para reconstrução"
                )

                for disco in self._discos_dados(faixa):
                    if disco == disco_perdido:
                        continue

                    conteudo = self._ler_bloco_fisico(
                        disco,
                        faixa
                    )

                    self._registrar_io(
                        disco,
                        faixa,
                        "leitura para reconstrução"
                    )

                    for indice, valor in enumerate(conteudo):
                        resultado[indice] ^= valor

                conteudo_reconstruido = bytes(resultado)

            self.discos[disco_perdido][faixa] = (
                conteudo_reconstruido
            )

            self._registrar_io(
                disco_perdido,
                faixa,
                "escrita de reconstrução"
            )

            self.escalonador.executar_fila()

        self.disco_com_falha = None

    def status(self) -> str:
        linhas = [
            "Estado do armazenamento RAID 5",
            f"Quantidade de discos: {self.quantidade_discos}",
            "Discos de dados por faixa: 3",
            "Discos de paridade por faixa: 1",
            f"Faixas disponíveis: {self.quantidade_faixas}",
            f"Blocos lógicos disponíveis: {self.quantidade_blocos_logicos}",
            "Distribuição da paridade: rotativa entre os discos",
        ]

        if self.disco_com_falha is None:
            linhas.append(
                "Estado: todos os discos estão funcionando."
            )
        else:
            linhas.append(
                f"Estado: disco {self.disco_com_falha + 1} em falha."
            )

            linhas.append(
                "O sistema está em modo degradado e permite leituras."
            )

        linhas.append("")
        linhas.append("Discos:")

        for disco in range(self.quantidade_discos):
            estado = (
                "com falha"
                if disco == self.disco_com_falha
                else "operacional"
            )

            linhas.append(
                f"Disco {disco + 1}: {estado}"
            )

        return "\n".join(linhas)


class SistemaArquivosEntrega2(SistemaArquivos):
    """Sistema de arquivos integrado ao RAID 5 e ao SSTF."""

    def __init__(self, quantidade_blocos: int = 256):
        super().__init__(quantidade_blocos)

        self.escalonador = EscalonadorSSTF()

        self.raid = ControladorRAID5(
            quantidade_blocos,
            self.escalonador
        )

    def _gravar_conteudo(
        self,
        arquivo,
        conteudo: bytes
    ) -> None:

        super()._gravar_conteudo(
            arquivo,
            conteudo
        )

        if arquivo.bloco_indice is not None:
            bloco_indice = self.blocos[
                arquivo.bloco_indice
            ]

            self.raid.gravar_bloco(
                bloco_indice.numero,
                bloco_indice.conteudo
            )

        for numero in arquivo.blocos_dados:
            bloco = self.blocos[numero]

            self.raid.gravar_bloco(
                numero,
                bloco.conteudo
            )

    def _liberar_bloco(self, numero: int) -> None:
        super()._liberar_bloco(numero)

        if self.raid.disco_com_falha is None:
            self.raid.gravar_bloco(
                numero,
                b""
            )

    def read_file(self, caminho: str) -> str:
        pai, nome = self._separar_caminho(caminho)

        if not nome or nome not in pai.arquivos:
            raise ErroSistemaArquivos(
                f"Arquivo não encontrado: {caminho}"
            )

        arquivo = pai.arquivos[nome]

        partes = [
            self.raid.ler_bloco(numero)[
                :len(self.blocos[numero].conteudo)
            ]
            for numero in arquivo.blocos_dados
        ]

        return b"".join(partes).decode("utf-8")

    def rm(self, caminho: str) -> None:
        if self.raid.disco_com_falha is not None:
            raise ErroSistemaArquivos(
                "Não é possível remover arquivos durante uma falha RAID. "
                "Execute raid_rebuild primeiro."
            )

        super().rm(caminho)

    def fs_status(self, detalhes: bool = False) -> str:
        relatorio = super().fs_status(detalhes)

        return (
            relatorio
            + "\n\n"
            + self.raid.status()
            + "\n\n"
            + self.escalonador.relatorio()
        )


AJUDA_ENTREGA2 = """
Comandos adicionais da Entrega 2:

  raid_status              Mostra o estado dos quatro discos RAID 5.
  raid_fail NUMERO         Simula a falha de um disco (1 a 4).
  raid_rebuild             Reconstrói o disco que apresentou falha.
  io_status                Mostra o estado do escalonador SSTF.
  io_history               Mostra as últimas operações de entrada e saída.
  io_clear                 Limpa o histórico e o movimento acumulado.

Os comandos da Entrega 1 continuam disponíveis.
"""


def executar_comando_entrega2(
    sistema: SistemaArquivosEntrega2,
    linha: str
) -> bool:

    try:
        import shlex

        argumentos = shlex.split(linha)

        if not argumentos:
            return True

        comando = argumentos[0].lower()

        if comando == "raid_status":
            print(sistema.raid.status())

        elif comando == "raid_fail":
            if len(argumentos) != 2:
                raise ErroSistemaArquivos(
                    "Uso: raid_fail NUMERO (de 1 a 4)"
                )

            try:
                numero = int(argumentos[1])

            except ValueError as erro:
                raise ErroSistemaArquivos(
                    "Informe o número do disco."
                ) from erro

            sistema.raid.simular_falha(numero)

            print(
                f"Falha simulada no disco {numero}. "
                "O RAID está operando em modo degradado."
            )

        elif comando == "raid_rebuild":
            sistema.raid.reconstruir_disco()

            print(
                "Reconstrução concluída. "
                "Todos os discos estão operacionais."
            )

        elif comando == "io_status":
            print(sistema.escalonador.relatorio())

        elif comando == "io_history":
            if not sistema.escalonador.historico:
                print(
                    "Ainda não existem operações registradas."
                )

            else:
                for requisicao, movimento in (
                    sistema.escalonador.historico[-20:]
                ):
                    print(
                        f"Disco {requisicao.disco + 1} | "
                        f"{requisicao.operacao} | "
                        f"trilha {requisicao.trilha} | "
                        f"movimento {movimento}"
                    )

        elif comando == "io_clear":
            sistema.escalonador.limpar_historico()

            print(
                "Histórico e movimento acumulado foram zerados."
            )

        elif comando == "help":
            from simulador_sistema_arquivos_entrega1 import AJUDA

            print(AJUDA)
            print(AJUDA_ENTREGA2)

        else:
            from simulador_sistema_arquivos_entrega1 import (
                executar_comando
            )

            return executar_comando(
                sistema,
                linha
            )

    except ErroSistemaArquivos as erro:
        print(f"Erro: {erro}")

    return True


def iniciar() -> None:
    sistema = SistemaArquivosEntrega2(
        quantidade_blocos=256
    )

    print("Simulador de Sistema de Arquivos - Entrega 2")
    print("Armazenamento: RAID 5 com quatro discos")
    print("Escalonamento de disco: SSTF")
    print("Digite 'help' para consultar os comandos.")

    while True:
        try:
            linha = input(
                f"{sistema.pwd()} $ "
            )

        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando o simulador.")
            break

        if not executar_comando_entrega2(
            sistema,
            linha
        ):
            print("Simulador encerrado.")
            break


if __name__ == "__main__":
    iniciar()
