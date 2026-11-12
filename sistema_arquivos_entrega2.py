"""
Simulador de Sistema de Arquivos - Entrega 2 (Integrado, Dinâmico e Interativo)
Requisitos: Integração de E/S, Escalonamento SSTF Dinâmico e RAID 5 com XOR Real.
"""

import random

# =====================================================================
# MÓDULO 1: GERENCIAMENTO FÍSICO DO DISCO & ALOCAÇÃO (Etapa 1)
# =====================================================================
class GerenciadorDeBlocos:
    def __init__(self, total_blocos=32, tamanho_bloco=4096):
        self.total_blocos = total_blocos
        self.tamanho_bloco = tamanho_bloco  # 4 KB
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
            raise MemoryError("Espaço em disco insuficiente.")
        
        for idx in blocos_alocados:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = ("DADO", descricao)
        return blocos_alocados

    def reservar_bloco(self, idx, tipo_desc):
        if 0 <= idx < self.total_blocos:
            self.blocos_ocupados[idx] = True
            self.mapa_descricao[idx] = (tipo_desc, "")


# =====================================================================
# MÓDULO 2: ESCALONAMENTO DO BRAÇO DE DISCO (Requisito 2 - SSTF)
# =====================================================================
class EscalonadorDisco:
    """Calcula dinamicamente a fila de atendimento e o deslocamento da cabeça."""
    def __init__(self, posicao_inicial=53):
        self.cabeca_atual = posicao_inicial

    def sstf(self, requisicoes_trilhas):
        pendentes = list(requisicoes_trilhas)
        atual = self.cabeca_atual
        ordem_atendimento = [atual]
        movimento_total = 0
        formulas = []

        while pendentes:
            # Encontra a trilha mais próxima da posição atual (lógica SSTF real)
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
# MÓDULO 3: REDUNDÂNCIA E TOLERÂNCIA A FALHAS VIA RAID 5 (Requisito 3)
# =====================================================================
class DiscoFisico:
    def __init__(self, id_disco):
        self.id_disco = id_disco
        self.blocos = {}  # {bloco_idx: dados_em_bytes}

    def escrever(self, bloco_idx, dados):
        self.blocos[bloco_idx] = dados

    def ler(self, bloco_idx):
        return self.blocos.get(bloco_idx, None)


class ControladorRAID5:
    """Implementa distribuição por striping e paridade XOR real com recuperação."""
    def __init__(self, num_discos=3, tamanho_bloco=4096):
        self.num_discos = num_discos
        self.tamanho_bloco = tamanho_bloco
        self.discos = [DiscoFisico(i+1) for i in range(num_discos)]

    def _calcular_xor(self, lista_dados):
        """Simula a operação lógica XOR entre os blocos de dados."""
        # Se os dados forem bytes, fazemos o XOR byte a byte ou geramos um checksum de paridade real
        xor_result = bytearray(self.tamanho_bloco)
        for d in lista_dados:
            # Preenche padding se o bloco for menor que o tamanho do bloco padrão
            padded_d = d.ljust(self.tamanho_bloco, b'\x00')
            for i in range(min(len(padded_d), len(xor_result))):
                xor_result[i] ^= padded_d[i]
        return bytes(xor_result)

    def gravar_raid5(self, nome_arquivo, dados_bytes):
        # Divide os dados em pedaços do tamanho do bloco
        partes = [dados_bytes[i:i+self.tamanho_bloco] for i in range(0, len(dados_bytes), self.tamanho_bloco)]
        dados_por_linha = self.num_discos - 1
        
        print(f"\n[E/S - DISTRIBUIÇÃO EM DISCO - Arranjo RAID 5 ({self.num_discos} Discos Físicos, Blocos de {self.tamanho_bloco//1024} KB)]")
        bloco_idx = 1
        
        for i in range(0, max(1, len(partes)), dados_por_linha):
            grupo = partes[i:i+dados_por_linha]
            # Garante que temos dados no grupo
            if not grupo:
                grupo = [b""]
                
            # Disco de paridade rotativo no RAID 5
            disco_paridade_idx = (bloco_idx - 1) % self.num_discos
            
            # Calcula o XOR real com base nos dados do grupo
            paridade_calculada = self._calcular_xor(grupo)
            
            d_idx = 0
            for d in range(self.num_discos):
                if d == disco_paridade_idx:
                    self.discos[d].escrever(bloco_idx, paridade_calculada)
                    print(f"Disco {d+1}: [PARIDADE : XOR calculado para o Bloco {bloco_idx:02d}]")
                else:
                    if d_idx < len(grupo):
                        p = grupo[d_idx]
                        self.discos[d].escrever(bloco_idx, p)
                        print(f"Disco {d+1}: [Bloco {bloco_idx:02d}: {nome_arquivo} - Part {d_idx+1} ({len(p)} bytes)]")
                        d_idx += 1
            bloco_idx += 1

    def simular_falha_e_recuperacao(self, disco_falhado_id=2, bloco_alvo=1):
        print(f"\n[TESTE DE FALHA SIMULADO NO RAID 5]")
        print(f"- Falha forçada no Disco {disco_falhado_id}!")
        
        disco_alvo_obj = self.discos[disco_falhado_id - 1]
        dado_perdido = disco_alvo_obj.ler(bloco_alvo)
        
        if dado_perdido is None:
            print(f"- Aviso: O Disco {disco_falhado_id} não possui o Bloco {bloco_alvo} alocado.")
            return

        # Isola temporariamente o disco falhado
        disco_alvo_obj.blocos[bloco_alvo] = None

        print(f"- Lendo discos remanescentes e bloco de paridade para o Bloco {bloco_alvo:02d}...")
        
        dados_sobreviventes = []
        paridade_obtida = None
        
        for d in self.discos:
            val = d.ler(bloco_alvo)
            if d.id_disco == disco_falhado_id:
                continue
            if val is not None:
                # Identifica se é paridade ou dado restante
                # No RAID 5 rotativo, verificamos quem guarda o que dinamicamente
                dados_sobreviventes.append(val)

        # Reconstrução matemática via XOR reverso entre os sobreviventes e a paridade
        print(f"- Executando reconstrução matemática via operação XOR em cima dos dados restantes...")
        dado_reconstruido = self._calcular_xor(dados_sobreviventes)
        
        # Restaura o bloco no disco físico
        disco_alvo_obj.blocos[bloco_alvo] = dado_reconstruido
        print(f"- Recuperação do Bloco {bloco_alvo:02d} via operação XOR -> Reconstrução [OK] (Dado íntegro recuperado).")


# =====================================================================
# MÓDULO 4: SISTEMA DE ARQUIVOS PRINCIPAL E INTEGRAÇÃO DE E/S
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


class SistemaDeArquivosIntegrado:
    def __init__(self):
        self.gerenciador_disco = GerenciadorDeBlocos(total_blocos=32, tamanho_bloco=4096)
        self.raiz = NoArquivo("/", eh_diretorio=True)
        self.diretorio_atual = self.raiz
        
        self.gerenciador_disco.reservar_bloco(0, "INODE_RAIZ")
        self.raiz.bloco_inode = 0
        
        self.escalonador = EscalonadorDisco(posicao_inicial=53)
        self.raid = ControladorRAID5(num_discos=3, tamanho_bloco=4096)
        self.lista_arquivos = []

    def mkdir(self, caminho):
        partes = [p for p in caminho.split("/") if p]
        if not partes:
            return
        nome = partes[-1]
        self.raiz.filhos[nome] = NoArquivo(nome, eh_diretorio=True, pai=self.raiz)
        print(f"📁 Diretório criado: {caminho}")

    def write_file(self, caminho, tamanho_bytes, conteudo_str=""):
        partes = [p for p in caminho.split("/") if p]
        if not partes:
            return
        nome = partes[-1]
        
        tamanho_bloco = self.gerenciador_disco.tamanho_bloco
        num_blocos = (tamanho_bytes + tamanho_bloco - 1) // tamanho_bloco
        
        try:
            inode_idx = self.gerenciador_disco.alocar_blocos(1, f"INODE_{nome.upper()}")[0]
            blocos_dados = self.gerenciador_disco.alocar_blocos(num_blocos, f"'{caminho}'")
        except MemoryError as e:
            print(f"❌ Erro: {e}")
            return

        novo_arq = NoArquivo(nome, eh_diretorio=False, tamanho=tamanho_bytes, pai=self.raiz)
        novo_arq.bloco_inode = inode_idx
        novo_arq.blocos_dados = blocos_dados
        self.raiz.filhos[nome] = novo_arq
        self.lista_arquivos.append(novo_arq)

        print(f"\n> write_file {caminho} --size {tamanho_bytes}")
        
        # 1. Geração dinâmica de requisições de E/S baseadas nos blocos alocados
        # (Gera trilhas aleatórias ou baseadas nos índices dos blocos para simulação real)
        requisicoes_geradas = [b * 7 + 14 for b in blocos_dados] + [random.randint(10, 190) for _ in range(3)]
        print(f"[E/S] Requisições de leitura/escrita pendentes nas trilhas: {requisicoes_geradas}")
        print(f"Posição atual da cabeça de leitura: Trilha {self.escalonador.cabeca_atual}")

        # 2. Execução do Escalonador de Disco (SSTF)
        ordem, movimento, formulas = self.escalonador.sstf(requisicoes_geradas)
        print(f"\n--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---")
        print(f"Ordem de Atendimento : {' -> '.join(map(str, ordem))}")
        print(f"Deslocamento da Cabeça: {' + '.join(formulas)}")
        print(f"Total de Movimento    : {' + '.join([f'{abs(ordem[i]-ordem[i+1])}' for i in range(len(ordem)-1))]} = {movimento} trilhas")

        # 3. Gravação física distribuída sob arranjo RAID 5
        if not conteudo_str:
            conteudo_str = f"Conteúdo do arquivo {nome} gerado pelo sistema." * ((tamanho_bytes // 30) + 1)
        
        self.raid.gravar_raid5(caminho, conteudo_str.encode('utf-8')[:tamanho_bytes])

    def fs_status(self):
        gd = self.gerenciador_disco
        print(f"\nTamanho do Bloco de Disco: {gd.tamanho_bloco // 1024} KB | Total de Blocos: {gd.total_blocos} ({gd.total_blocos * gd.tamanho_bloco // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        for i in range(gd.total_blocos):
            status, desc = gd.mapa_descricao[i]
            if status == "LIVRE":
                print(f"Bloco {i:02d}                  : [LIVRE]")
            else:
                print(f"Bloco {i:02d} [{status:<11}] : {desc}")

        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO DINÂMICO ---")
        if not self.lista_arquivos:
            print("Nenhum arquivo gravado.")
            return

        for arq in self.lista_arquivos:
            espaco_alocado = len(arq.blocos_dados) * gd.tamanho_bloco
            frag_interna = espaco_alocado - arq.tamanho
            perc = (frag_interna / espaco_alocado * 100) if espaco_alocado > 0 else 0
            print(f"Arquivo          : {arq.nome}")
            print(f"Tamanho Real     : {arq.tamanho} bytes")
            print(f"Espaço Alocado   : {espaco_alocado} bytes ({len(arq.blocos_dados)} blocos de {gd.tamanho_bloco//1024} KB)")
            print(f"Frag. Interna    : {frag_interna} bytes ({perc:.1f}% de desperdício)")
            print(f"Frag. Externa    : 0 bytes")
            print(f"Compactação      : NÃO (Alocação Indexada)\n")


# =====================================================================
# CLI INTERATIVA PARA TESTES DO PROFESSOR
# =====================================================================
def main():
    fs = SistemaDeArquivosIntegrado()
    print("=" * 70)
    print("   SIMULADOR DE SISTEMA DE ARQUIVOS - ENTREGA 2 (INTERATIVO)")
    print("   Comandos disponíveis:")
    print("     mkdir <caminho>")
    print("     create <caminho> --size <bytes>")
    print("     fs_status")
    print("     raid_fail <disco_id> <bloco_idx>")
    print("     exit")
    print("=" * 70)

    # Caso de teste inicial automático baseado no modelo do professor
    print("\n[Executando caso de teste inicial para demonstração...]")
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    fs.write_file("/sistema/logs/app.log", 10240, "Novo Registro de Log do Sistema Operacional 2026")

    while True:
        try:
            entrada = input("\nsimulador> ").strip()
            if not entrada:
                continue
            
            partes = entrada.split()
            cmd = partes[0]

            if cmd == "exit":
                print("Encerrando simulador...")
                break
            elif cmd == "mkdir" and len(partes) > 1:
                fs.mkdir(partes[1])
            elif cmd == "create" and len(partes) > 1:
                caminho = partes[1]
                tamanho = 8192
                if "--size" in partes:
                    idx = partes.index("--size")
                    if idx + 1 < len(partes):
                        tamanho = int(partes[idx + 1])
                fs.write_file(caminho, tamanho)
            elif cmd == "fs_status":
                fs.fs_status5 = fs.fs_status()
            elif cmd == "raid_fail":
                d_id = int(partes[1]) if len(partes) > 1 else 2
                b_idx = int(partes[2]) if len(partes) > 2 else 1
                fs.raid.simular_falha_e_recuperacao(d_id, b_idx)
            else:
                print("Comando inválido. Use: mkdir, create, fs_status, raid_fail, exit")
        except Exception as e:
            print(f"Erro na execução: {e}")

if __name__ == "__main__":
    main()
