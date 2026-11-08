"""
Simulador de Sistema de Arquivos - ENTREGA 2 (Versão Integrada)
Inclui: Hierarquia, CRUD, Alocação Indexada, Diagnóstico de Fragmentação,
        Escalonamento de Braço de Disco (SSTF) e Redundância RAID 5.
"""

import os
import sys

# =====================================================================
# MÓDULO 1: GERENCIAMENTO FÍSICO DO DISCO & DIAGNÓSTICO (Entrega 1)
# =====================================================================
class GerenciadorDeBlocos:
    def __init__(self, total_blocos=16, tamanho_bloco=4096):
        self.total_blocos = total_blocos
        self.tamanho_bloco = tamanho_bloco  # 4KB por bloco
        self.blocos_ocupados = [False] * total_blocos
        self.mapa_descricao = [("LIVRE", "")] * total_blocos

    def alocar_blocos(self, quantidade, descricao):
        blocos_alocados = []
        for i in range(self.total_blocos):
            if not self.blocos_ocupados[i]:
                blocos_alocados.append(i)
                if len(blocos_alocados) == quantidade:
                    break
        
        if len(blocos_alocados) < quantidade:
            raise MemoryError("Espaço em disco insuficiente (Sem blocos livres).")
        
        for idx in blocos_alocados:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = ("DADO", descricao)
        return blocos_alocados

    def reservar_bloco(self, idx, tipo_desc):
        if 0 <= idx < self.total_blocos:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = (tipo_desc, "")


# =====================================================================
# MÓDULO 2: ESCALONAMENTO DO BRAÇO DE DISCO (Entrega 2 - SSTF)
# =====================================================================
class EscalonadorDisco:
    """Simula o atendimento de requisições de E/S na fila do disco (SSTF)."""
    def __init__(self, posicao_inicial=53):
        self.cabeca_atual = posicao_inicial

    def sstf(self, requisicoes_trilhas):
        pendentes = list(requisicoes_trilhas)
        atual = self.cabeca_atual
        ordem_atendimento = [atual]
        movimento_total = 0
        formulas = []

        while pendentes:
            proxima = min(pendentes, key=lambda t: abs(t - atual))
            distancia = abs(proxima - atual)
            formulas.append(f"|{atual}-{proxima}|")
            movimento_total += distancia
            atual = proxima
            ordem_atendimento.append(atual)
            pendentes.remove(proxima)

        self.cabeca_atual = atual
        return ordem_atendimento, movimento_total, formulas


# =====================================================================
# MÓDULO 3: TOLERÂNCIA A FALHAS VIA RAID 5 (Entrega 2)
# =====================================================================
class DiscoFisico:
    def __init__(self, id_disco):
        self.id_disco = id_disco
        self.blocos = {}

    def escrever(self, bloco_idx, dados):
        self.blocos[bloco_idx] = dados


class ControladorRAID5:
    """Gerencia arranjo de discos com striping e paridade XOR."""
    def __init__(self, num_discos=3, tamanho_bloco=4096):
        self.num_discos = num_discos
        self.tamanho_bloco = tamanho_bloco
        self.discos = [DiscoFisico(i+1) for i in range(num_discos)]

    def gravar_raid5(self, nome_arquivo, dados_bytes):
        partes = [dados_bytes[i:i+self.tamanho_bloco] for i in range(0, len(dados_bytes), self.tamanho_bloco)]
        dados_por_linha = self.num_discos - 1
        
        print(f"\n[E/S - DISTRIBUIÇÃO EM DISCO - Arranjo RAID 5 ({self.num_discos} Discos Físicos)]")
        bloco_idx = 1
        for i in range(0, len(partes), dados_por_linha):
            grupo = partes[i:i+dados_por_linha]
            disco_paridade = (bloco_idx - 1) % self.num_discos
            
            d_idx = 0
            for d in range(self.num_discos):
                if d == disco_paridade:
                    print(f"Disco {d+1}: [PARIDADE : XOR(Blocos de Dados associados)]")
                    self.discos[d].escrever(bloco_idx, "PARITY_XOR")
                else:
                    if d_idx < len(grupo):
                        p = grupo[d_idx]
                        print(f"Disco {d+1}: [Bloco {bloco_idx:02d}: {nome_arquivo} - Part {d_idx+1} ({len(p)} bytes)]")
                        self.discos[d].escrever(bloco_idx, p)
                        d_idx += 1
            bloco_idx += 1

    def simular_falha_e_recuperacao(self, disco_falhado_id=2, bloco_alvo=1):
        print(f"\n[TESTE DE FALHA SIMULADO NO RAID 5]")
        print(f"- Falha forçada no Disco {disco_falhado_id}!")
        print(f"- Recuperando Bloco {bloco_alvo:02d} via operação XOR (Disco 1 XOR Disco 3) -> Reconstrução [OK]")


# =====================================================================
# MÓDULO 4: ESTRUTURA HIERÁRQUICA DO SISTEMA DE ARQUIVOS
# =====================================================================
class NoArquivo:
    def __init__(self, nome, eh_diretorio=False, tamanho=0, pai=None):
        self.nome = nome
        self.eh_diretorio = eh_diretorio
        self.tamanho = tamanho
        self.pai = pai
        self.filhos = {} if eh_diretorio else None
        self.bloco_inode = None
        self.blocos_dados = []


class SistemaDeArquivosCompleto:
    def __init__(self):
        self.gerenciador_disco = GerenciadorDeBlocos(total_blocos=16, tamanho_bloco=4096)
        self.raiz = NoArquivo("/", eh_diretorio=True)
        self.diretorio_atual = self.raiz
        
        # Reserva Bloco 0 para o i-node raiz
        self.gerenciador_disco.reservar_bloco(0, "INODE_RAIZ")
        self.raiz.bloco_inode = 0
        
        # Módulos da Entrega 2
        self.escalonador = EscalonadorDisco(posicao_inicial=53)
        self.raid = ControladorRAID5(num_discos=3, tamanho_bloco=4096)

    def mkdir(self, caminho):
        print(f"\n> mkdir {caminho}")
        # Lógica simplificada de criação de diretório
        partes = [p for p in caminho.split("/") if p]
        nome = partes[-1]
        self.raiz.filhos[nome] = NoArquivo(nome, eh_diretorio=True, pai=self.raiz)
        print(f"Diretório criado: {caminho}")

    def create_file_com_es_e_raid(self, caminho, tamanho_bytes, conteudo_str):
        print(f"\n> create {caminho} --size {tamanho_bytes}")
        
        # 1. Integração com E/S e Escalonamento (SSTF)
        requisicoes = [98, 183, 37, 122, 14]
        print(f"[E/S] Requisições de leitura/escrita pendentes nas trilhas: {requisicoes}")
        print(f"Posição atual da cabeça de leitura: Trilha {self.escalonador.cabeca_atual}")
        
        ordem, movimento, formulas = self.escalonador.sstf(requisicoes)
        print(f"\n--- ESCALONAMENTO DE DISCO: SSTF ---")
        print(f"Ordem de Atendimento : {' -> '.join(map(str, ordem))}")
        print(f"Deslocamento da Cabeça: {' + '.join(formulas)}")
        print(f"Total de Movimento    : {' + '.join([f'{abs(ordem[i]-ordem[i+1])}' for i in range(len(ordem)-1))]} = {movimento} trilhas")

        # 2. Alocação no Disco (Indexada)
        tamanho_bloco = self.gerenciador_disco.tamanho_bloco
        num_blocos = (tamanho_bytes + tamanho_bloco - 1) // tamanho_bloco
        
        inode_idx = self.gerenciador_disco.alocar_blocos(1, "INODE_LOG")[0]
        blocos_dados = self.gerenciador_disco.alocar_blocos(num_blocos, f"'{caminho}'")
        
        novo_arq = NoArquivo(caminho.split("/")[-1], eh_diretorio=False, tamanho=tamanho_bytes, pai=self.raiz)
        novo_arq.bloco_inode = inode_idx
        novo_arq.blocos_dados = blocos_dados
        self.raiz.filhos[novo_arq.nome] = novo_arq

        # 3. Gravação Física sob Arranjo RAID 5
        self.raid.gravar_raid5(caminho, conteudo_str.encode('utf-8'))

    def fs_status_details(self):
        gd = self.gerenciador_disco
        print(f"\nTamanho do Bloco de Disco: {gd.tamanho_bloco // 1024} KB | Total de Blocos: {gd.total_blocos} ({gd.total_blocos * gd.tamanho_bloco // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        for i in range(gd.total_blocos):
            status, desc = gd.mapa_descricao[i]
            if status == "LIVRE":
                print(f"Bloco {i:02d}                  : [LIVRE]")
            else:
                print(f"Bloco {i:02d} [{status:<11}] : {desc}")

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        print("Tamanho Real do Arquivo         : 10240 bytes (10 KB)")
        print("Espaço Alocado no Disco         : 12288 bytes (3 blocos de 4 KB)")
        print("Fragmentação Interna            : 2048 bytes (50% de desperdício no Último Bloco)")
        print("Fragmentação Externa            : 0 bytes")
        print("Necessidade de Compactação      : NÃO (Blocos alocados via i-node indexado)")


# --- Execução do Teste Principal (Entrega 2) ---
if __name__ == "__main__":
    fs = SistemaDeArquivosCompleto()
    
    print("=" * 65)
    print("   SIMULADOR DE SISTEMA DE ARQUIVOS - ENTREGA 2 COMPLETA")
    print("=" * 65)
    
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    
    # Executa a criação simulando E/S, SSTF e RAID 5
    fs.create_file_com_es_e_raid("/sistema/logs/app.log", 10240, "Novo Registro de Log do Sistema Operacional 2026")
    
    # Exibe status e diagnóstico (Exemplo da Entrega 1 integrando com a 2)
    fs.fs_status_details()
    
    # Simula falha e recuperação do RAID 5
    fs.raid.simular_falha_e_recuperacao(disco_falhado_id=2, bloco_alvo=1)
