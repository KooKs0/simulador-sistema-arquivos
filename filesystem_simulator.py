"""
Simulador de Sistema de Arquivos
Desenvolvido para fins educacionais (Sistemas Operacionais).
Suporta hierarquia de diretórios, operações básicas e alocação indexada.
"""

import os
import sys


class GerenciadorDeBlocos:
    """Responsável por gerenciar o espaço físico do 'disco' dividido em blocos."""

    def __init__(self, total_blocos=16, tamanho_bloco=4096):
        self.total_blocos = total_blocos
        self.tamanho_bloco = tamanho_bloco  # em bytes (ex: 4KB = 4096)
        
        # Estado dos blocos: False = Livre, True = Ocupado
        self.blocos_ocupados = [False] * total_blocos
        
        # Metadados para sabermos o que está alocado em cada bloco
        self.mapa_descricao = [("LIVRE", "")] * total_blocos

    def alocar_blocos(self, quantidade, descricao):
        """Procura blocos livres no disco e faz a alocação."""
        blocos_alocados = []
        for i in range(self.total_blocos):
            if not self.blocos_ocupados[i]:
                blocos_alocados.append(i)
                if len(blocos_alocados) == quantidade:
                    break
        
        if len(blocos_alocados) < quantidade:
            raise MemoryError("Espaço em disco insuficiente! Faltam blocos livres.")
        
        for idx in blocos_alocados:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = ("DADO", descricao)
            
        return blocos_alocados

    def liberar_blocos(self, lista_blocos):
        """Libera os blocos que pertenciam a um arquivo ou diretório removido."""
        for idx in lista_blocos:
            if 0 <= idx < self.total_blocos:
                self.blocos_ocupados[idx] = False
                self.mapa_descricao[idx] = ("LIVRE", "")

    def reservar_bloco(self, idx, tipo_desc):
        """Reserva um bloco específico (usado para i-nodes)."""
        if 0 <= idx < self.total_blocos:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = (tipo_desc, "")


class NoArquivo:
    """Representa um nó na árvore de diretórios (pode ser arquivo ou pasta)."""

    def __init__(self, nome, eh_diretorio=False, tamanho=0, pai=None):
        self.nome = nome
        self.eh_diretorio = eh_diretorio
        self.tamanho = tamanho  # Tamanho real em bytes
        self.pai = pai
        self.filhos = {} if eh_diretorio else None
        
        # Atributos específicos para a alocação indexada
        self.bloco_inode = None
        self.blocos_dados = []


class SimuladorSistemaArquivos:
    """Controla a lógica principal do sistema de arquivos e comandos."""

    def __init__(self, total_blocos=16, tamanho_bloco=4096):
        self.gerenciador_disco = GerenciadorDeBlocos(total_blocos, tamanho_bloco)
        
        # Cria a raiz do sistema '/'
        self.raiz = NoArquivo("/", eh_diretorio=True)
        self.diretorio_atual = self.raiz
        
        # O Bloco 0 é reservado para o i-node do diretório raiz
        self.gerenciador_disco.reservar_bloco(0, "INODE_RAIZ")
        self.raiz.bloco_inode = 0

    def _resolver_caminho(self, caminho):
        """Navega pela árvore a partir de um caminho absoluto ou relativo."""
        if caminho.startswith("/"):
            no_atual = self.raiz
            partes = [p for p in caminho.split("/") if p]
        else:
            no_atual = self.diretorio_atual
            partes = [p for p in caminho.split("/") if p and p != "."]

        for parte in partes:
            if parte == "..":
                if no_atual.pai:
                    no_atual = no_atual.pai
            elif no_atual.filhos and parte in no_atual.filhos:
                no_atual = no_atual.filhos[parte]
            else:
                return None, partes
        return no_atual, partes

    def criar_diretorio(self, caminho):
        """Comando mkdir: Cria um novo diretório."""
        no_pai, partes = self._resolver_caminho(caminho)
        if not partes:
            print("⚠️ Caminho inválido ou já existente.")
            return

        nome_novo_dir = partes[-1]
        if len(partes) > 1:
            caminho_pai = "/" + "/".join(partes[:-1]) if caminho.startswith("/") else "/".join(partes[:-1])
            no_pai, _ = self._resolver_caminho(caminho_pai)

        if no_pai and no_pai.eh_diretorio:
            if nome_novo_dir in no_pai.filhos:
                print(f"⚠️ O diretório '{nome_novo_dir}' já existe.")
                return
            
            novo_dir = NoArquivo(nome_novo_dir, eh_diretorio=True, pai=no_pai)
            no_pai.filhos[nome_novo_dir] = novo_dir
            print(f"📁 Diretório criado com sucesso: {caminho}")
        else:
            print("⚠️ Caminho pai não encontrado.")

    def criar_arquivo(self, caminho, tamanho_bytes):
        """Comando create: Cria um arquivo e aloca seus blocos via i-node."""
        no_pai, partes = self._resolver_caminho(caminho)
        if not partes:
            print("⚠️ Caminho inválido.")
            return

        nome_arquivo = partes[-1]
        if len(partes) > 1:
            caminho_pai = "/" + "/".join(partes[:-1]) if caminho.startswith("/") else "/".join(partes[:-1])
            no_pai, _ = self._resolver_caminho(caminho_pai)

        if no_pai and no_pai.eh_diretorio:
            if nome_arquivo in no_pai.filhos:
                print(f"⚠️ O arquivo '{nome_arquivo}' já existe.")
                return

            tamanho_bloco = self.gerenciador_disco.tamanho_bloco
            # Calcula quantos blocos de dados serão necessários
            qtd_blocos_dados = (tamanho_bytes + tamanho_bloco - 1) // tamanho_bloco

            try:
                # Aloca 1 bloco para o i-node do arquivo
                bloco_inode = self.gerenciador_disco.alocar_blocos(1, f"INODE_{nome_arquivo.upper()}")[0]
                
                # Aloca os blocos de dados necessários
                blocos_dados = self.gerenciador_disco.alocar_blocos(qtd_blocos_dados, f"'{caminho}'")
            except MemoryError as e:
                print(f"❌ Erro de alocação: {e}")
                return

            novo_arquivo = NoArquivo(nome_arquivo, eh_diretorio=False, tamanho=tamanho_bytes, pai=no_pai)
            novo_arquivo.bloco_inode = bloco_inode
            novo_arquivo.blocos_dados = blocos_dados

            no_pai.filhos[nome_arquivo] = novo_arquivo
            print(f"📄 Arquivo criado: {caminho} ({tamanho_bytes} bytes)")
        else:
            print("⚠️ Diretório pai não encontrado.")

    def exibir_arvore(self, no=None, prefixo=""):
        """Exibe a árvore de diretórios de forma visual estilo terminal."""
        if no is None:
            no = self.raiz
        
        print(f"{prefix}{no.nome}{'/' if no.eh_diretorio else ''} {'[DIR]' if no.eh_diretorio else f'({no.tamanho} bytes) [ARQ]'}")
        if no.eh_diretorio and no.filhos:
            itens = list(no.filhos.items())
            for i, (nome, filho) in enumerate(itens):
                conector = "└── " if i == len(itens) - 1 else "├── "
                proximo_prefixo = "    " if i == len(itens) - 1 else "│   "
                self._exibir_arvore_recursivo(filho, prefixo + conector, prefixo + proximo_prefixo)

    def _exibir_arvore_recursivo(self, no, prefixo, prefixo_atual):
        print(f"{prefix}{no.nome}{'/' if no.eh_diretorio else ''} {'[DIR]' if no.eh_diretorio else f'({no.tamanho} bytes) [ARQ]'}")
        if no.eh_diretorio and no.filhos:
            itens = list(no.filhos.items())
            for i, (nome, filho) in enumerate(itens):
                conector = "└── " if i == len(itens) - 1 else "├── "
                proximo_prefixo = "    " if i == len(itens) - 1 else "│   "
                self._exibir_arvore_recursivo(filho, prefixo_atual + conector, prefixo_atual + proximo_prefixo)

    def status_disco(self):
        """Comando fs_status: Mostra o mapa do disco e o relatório de fragmentação."""
        gd = self.gerenciador_disco
        print(f"\n⚙️  Tamanho do Bloco: {gd.tamanho_bloco // 1024} KB | Total de Blocos: {gd.total_blocos} ({gd.total_blocos * gd.tamanho_bloco // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        
        i = 0
        while i < gd.total_blocos:
            status, desc = gd.mapa_descricao[i]
            if status == "LIVRE":
                inicio_livre = i
                while i < gd.total_blocos and gd.mapa_descricao[i][0] == "LIVRE":
                    i += 1
                fim_livre = i - 1
                if inicio_livre == fim_livre:
                    print(f"Bloco {inicio_livre:02d}                  : [LIVRE]")
                else:
                    print(f"Bloco {inicio_livre:02d}..{fim_livre:02d}             : [LIVRE]")
            else:
                print(f"Bloco {i:02d} [{status:<11}] : {desc}")
                i += 1

        self._gerar_relatorio_fragmentacao(self.raiz)

    def _gerar_relatorio_fragmentacao(self, no):
        """Varre os arquivos recursivamente para calcular desperdícios e fragmentação."""
        arquivos = []
        def coletar(n):
            if not n.eh_diretorio:
                arquivos.append(n)
            else:
                for f in n.filhos.values():
                    coletar(f)
        coletar(no)

        for arq in arquivos:
            tamanho_bloco = self.gerenciador_disco.tamanho_bloco
            blocos_alocados = len(arq.blocos_dados)
            espaco_total_alocado = blocos_alocados * tamanho_bloco
            fragmentacao_interna = espaco_total_alocado - arq.tamanho
            
            print(f"\n--- RELATÓRIO DE FRAGMENTAÇÃO ({arq.nome}) ---")
            print(f"Tamanho Real do Arquivo          : {arq.tamanho} bytes ({arq.tamanho // 1024} KB)")
            print(f"Espaço Alocado no Disco          : {espaco_total_alocado} bytes ({blocos_alocados} blocos de {tamanho_bloco // 1024} KB)")
            print(f"Fragmentação Interna             : {fragmentacao_interna} bytes de desperdício no último bloco")
            print(f"Fragmentação Externa             : 0 bytes")
            print(f"Necessidade de Compactação       : NÃO (Alocação indexada gerencia blocos por ponteiros/i-node)")


# --- Execução Interativa se rodado diretamente ---
if __name__ == "__main__":
    fs = SimuladorSistemaArquivos(total_blocos=16, tamanho_bloco=4096)
    
    print("=" * 60)
    print("   DISCO VIRTUAL INICIADO (Simulador de Sistema de Arquivos)")
    print("=" * 60)
    
    # Executando os exemplos padrão do enunciado automaticamente para facilitar
    print("\n[Executando exemplos iniciais sugeridos...]")
    fs.criar_diretorio("/sistema")
    fs.criar_diretorio("/sistema/logs")
    fs.criar_arquivo("/sistema/logs/app.log", 10240)  # 10 KB
    
    print("\n" + "=" * 40)
    print(" [ÁRVORE DO SISTEMA DE ARQUIVOS]")
    print("=" * 40)
    fs.exibir_arvore()
    
    print("\n" + "=" * 40)
    print(" [STATUS DETALHADO DO DISCO]")
    print("=" * 40)
    fs.status_disco()
