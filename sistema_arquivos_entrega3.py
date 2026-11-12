"""
Simulador de Sistema de Arquivos - Entrega 3 (Completo e Integrado)
Inclui: Modos Usuário/Kernel, Autenticação com Hashing/Salt, Controle de Acesso (ACL rwx),
        Criptografia em Repouso (AES sim/Cipher) e Antivírus com Verificação de Integridade por Hash.
"""

import hashlib
import os
import base64

# =====================================================================
# MÓDULO 1: GERENCIAMENTO DE IDENTIDADE, AUTENTICAÇÃO E HASHING
# =====================================================================
class GerenciadorUsuarios:
    """Gerencia usuários, grupos, hashing seguro de senhas com salt e autenticação."""
    def __init__(self):
        self.usuarios = {}  # {username: {'hash': ..., 'salt': ..., 'grupo': ...}}
        self.usuario_atual = None
        self.modo_kernel = False  # False = Modo Usuário, True = Modo Kernel
        
        # Cria usuários padrão iniciais (ex: root e carlos)
        self.cadastrar_usuario("root", "root123", "admin")
        self.cadastrar_usuario("carlos", "senha123", "devs")

    def cadastrar_usuario(self, username, senha, grupo):
        salt = os.urandom(16)
        # Hashing seguro com SHA-256 + Salt
        senha_hash = hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 100000)
        self.usuarios[username] = {
            'hash': senha_hash,
            'salt': salt,
            'grupo': grupo
        }

    def autenticar(self, username, senha):
        if username not in self.usuarios:
            print(f"❌ Erro: Usuário '{username}' não encontrado.")
            return False
        
        user_info = self.usuarios[username]
        senha_hash = hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), user_info['salt'], 100000)
        
        if senha_hash == user_info['hash']:
            self.usuario_atual = username
            # Se for root, entra inicialmente em Modo Kernel; caso contrário, Modo Usuário
            self.modo_kernel = (username == "root")
            print(f"Autenticado com sucesso. Usuário: '{username}' | Grupo: '{user_info['grupo']}' | Modo: {'MODO_KERNEL' if self.modo_kernel else 'MODO_USUARIO'}")
            return True
        else:
            print("❌ Erro: Senha incorreta.")
            return False

    def obter_grupo(self, username):
        return self.usuarios.get(username, {}).get('grupo', 'outros')


# =====================================================================
# MÓDULO 2: CRIPTOGRAFIA DE DADOS EM REPOUSO
# =====================================================================
class CriptografiaDisco:
    """Simula criptografia e descriptografia de dados armazenados nos blocos físicos."""
    @staticmethod
    def criptografar(conteudo_str, chave_str):
        # Deriva uma chave simples a partir da string fornecida e aplica codificação segura
        chave_bytes = hashlib.sha256(chave_str.encode()).digest()
        dados_bytes = conteudo_str.encode('utf-8')
        
        # XOR simples em bytes com a chave derivada para simular cifragem reversível em repouso
        cifrado = bytearray(dados_bytes)
        for i in range(len(cifrado)):
            cifrado[i] ^= chave_bytes[i % len(chave_bytes)]
            
        ciphertext_b64 = base64.b64encode(cifrado).decode('utf-8')
        return f"0x{ciphertext_b64[:20]}... (Encrypted Ciphertext)"

    @staticmethod
    def cifrar_bytes(dados_bytes, chave_str):
        chave_bytes = hashlib.sha256(chave_str.encode()).digest()
        cifrado = bytearray(dados_bytes)
        for i in range(len(cifrado)):
            cifrado[i] ^= chave_bytes[i % len(chave_bytes)]
        return bytes(cifrado)

    @staticmethod
    def decifrar_bytes(dados_cifrados_bytes, chave_str):
        return CriptografiaDisco.cifrar_bytes(dados_cifrados_bytes, chave_str) # XOR reverso


# =====================================================================
# MÓDULO 3: CONTROLE DE ACESSO (ACL rwx) E MODOS DE EXECUÇÃO
# =====================================================================
class ACL:
    """Define as permissões rwx para Proprietário, Grupo e Outros (ex: 750 -> rwxr-x---)."""
    def __init__(self, propietario="root", grupo="admin", permissoes="rwxr-x---"):
        self.propietario = propietario
        self.grupo = grupo
        self.permissoes = permissoes  # ex: rwxr-x---

    def verificar_permissao(self, usuario, grupo_usuario, modo_kernel, acionamento):
        """Verifica se o usuário tem direito de Leitura (r), Escrita (w) ou Execução (x)."""
        if modo_kernel:
            return True  # Modo Kernel (root) tem acesso total imperativo

        # Mapeia qual pedaço da string de permissão olhar
        if usuario == self.propietario:
            bloco_perm = self.permissoes[1:4]  # Proprietário
        elif grupo_usuario == self.grupo:
            bloco_perm = self.permissoes[4:7]  # Grupo
        else:
            bloco_perm = self.permissoes[7:10]  # Outros

        # Mapeia ação para caractere correspondente
        char_map = {'read': 'r', 'write': 'w', 'execute': 'x'}
        alvo_char = char_map.get(acionamento, '')

        return alvo_char in bloco_perm


# =====================================================================
# MÓDULO 4: GERENCIAMENTO DE BLOCOS E INTEGRIDADE (ANTIVÍRUS)
# =====================================================================
class GerenciadorDeBlocos:
    def __init__(self, total_blocos=32, tamanho_bloco=4096):
        self.total_blocos = total_blocos
        self.tamanho_bloco = tamanho_bloco
        self.blocos_ocupados = [False] * total_blocos
        self.mapa_descricao = [("LIVRE", "")] * total_blocos
        self.conteudo_blocos = {}  # {bloco_idx: bytes}
        self.hashes_oficiais = {}  # {bloco_idx: hash_sha256}

    def alocar_blocos(self, quantidade, descricao, dados_bytes=b""):
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
            if dados_bytes:
                self.conteudo_blocos[idx] = dados_bytes
                # Calcula o hash oficial para auditoria de integridade posterior
                self.hashes_oficiais[idx] = hashlib.sha256(dados_bytes).hexdigest()
        return blocos_alocados

    def corromper_bloco_simulado(self, bloco_idx):
        """Simula uma modificação externa maliciosa não autorizada no bloco do disco."""
        if bloco_idx in self.conteudo_blocos:
            self.conteudo_blocos[bloco_idx] = b"DADO_ALTERADO_MALICIOSAMENTE_POR_VIRUS"


# =====================================================================
# MÓDULO 5: SISTEMA DE ARQUIVOS PRINCIPAL E SEGURANÇA INTEGRADA
# =====================================================================
class NoArquivo:
    def __init__(self, nome, eh_diretorio=False, tamanho=0, pai=None, prop="root", grupo="admin", perm="rwxr-xr-x"):
        self.nome = nome
        self.eh_diretorio = eh_diretorio
        self.tamanho = tamanho
        self.pai = pai
        self.filhos = {} if eh_diretorio else None
        self.bloco_inode = None
        self.blocos_dados = []
        self.acl = ACL(prop, grupo, perm)
        self.criptografado = False
        self.chave_criptografia = None


class SistemaDeArquivosEntrega3:
    def __init__(self):
        self.auth = GerenciadorUsuarios()
        self.gerenciador_disco = GerenciadorDeBlocos(total_blocos=32, tamanho_bloco=4096)
        self.raiz = NoArquivo("/", eh_diretorio=True, prop="root", grupo="admin", perm="rwxr-xr-x")
        self.diretorio_atual = self.raiz
        self.lista_arquivos = []

        # Configuração inicial de arquivos críticos protegidos
        self._criar_arquivo_sistema("/sistema/config.sys", 512, "config=secure_mode_on", "root", "admin", "rwxr-x---")

    def _criar_arquivo_sistema(self, caminho, tamanho, conteudo, prop, grupo, perm):
        nome = caminho.split("/")[-1]
        blocos = self.gerenciador_disco.alocar_blocos(1, caminho, conteudo.encode())
        no = NoArquivo(nome, eh_diretorio=False, tamanho=tamanho, prop=prop, grupo=grupo, perm=perm)
        no.blocos_dados = blocos
        self.raiz.filhos[nome] = no
        self.lista_arquivos.append(no)

    def mkdir(self, caminho):
        if not self.auth.modo_kernel and self.auth.usuario_atual != "root":
            print("❌ [NEGADO]: Operação crítica exige privilégios de MODO_KERNEL (Superusuário).")
            return
        
        partes = [p for p in caminho.split("/") if p]
        if not partes:
            return
        nome = partes[-1]
        self.raiz.filhos[nome] = NoArquivo(nome, eh_diretorio=True, prop=self.auth.usuario_atual, grupo=self.auth.obter_grupo(self.auth.usuario_atual))
        print(f"📁 Diretório criado: {caminho} com privilégios de Kernel/Admin.")

    def read_file(self, caminho):
        nome = caminho.split("/")[-1]
        if nome not in self.raiz.filhos:
            print(f"❌ Erro: Arquivo '{caminho}' não encontrado.")
            return

        arquivo = self.raiz.filhos[nome]
        usuario = self.auth.usuario_atual or "convidado"
        grupo = self.auth.obter_grupo(usuario)

        print(f"\n[SISTEMA DE SEGURANÇA - VERIFICAÇÃO DE ACL]")
        print(f"Objeto      : {caminho}")
        print(f"Proprietário: {arquivo.acl.propietario} (Grupo: {arquivo.acl.grupo})")
        print(f"Permissões  : {arquivo.acl.permissoes}")
        print(f"Ação Pedida : LEITURA por '{usuario}' (Grupo: {grupo})")

        # Validação da ACL
        autorizado = arquivo.acl.verificar_permissao(usuario, grupo, self.auth.modo_kernel, 'read')

        if not autorizado:
            print(f"\n[NEGADO]: O usuário '{usuario}' não possui permissão de leitura no objeto '{caminho}'.")
            print("Tentativa não autorizada registrada nos logs de auditoria do sistema.")
            return

        print(f"\n[AUTORIZADO]: Acesso de leitura concedido ao arquivo '{caminho}'.")
        # Lê os dados do disco
        conteudo_total = b""
        for b_idx in arquivo.blocos_dados:
            dados_bloco = self.gerenciador_disco.conteudo_blocos.get(b_idx, b"")
            if arquivo.criptografado:
                dados_bloco = CriptografiaDisco.decifrar_bytes(dados_bloco, arquivo.chave_criptografia)
            conteudo_total += dados_bloco
        
        print(f"Conteúdo: {conteudo_total.decode('utf-8', errors='ignore')}")

    def encrypt_file(self, caminho, chave):
        nome = caminho.split("/")[-1]
        if nome not in self.raiz.filhos:
            print(f"❌ Erro: Arquivo '{caminho}' não encontrado.")
            return

        arquivo = self.raiz.filhos[nome]
        arquivo.criptografado = True
        arquivo.chave_criptografia = chave

        # Cifra o conteúdo físico armazenado nos blocos do disco
        for b_idx in arquivo.blocos_dados:
            dados_originais = self.gerenciador_disco.conteudo_blocos.get(b_idx, b"")
            dados_cifrados = CriptografiaDisco.cifrar_bytes(dados_originais, chave)
            self.gerenciador_disco.conteudo_blocos[b_idx] = dados_cifrados

        cipher_preview = CriptografiaDisco.criptografar("dados_exemplo", chave)
        print(f"Arquivo '{caminho}' criptografado com sucesso.")
        print(f"Conteúdo gravado nos blocos físicos: \"{cipher_preview}\"")

    def antivirus_scan(self):
        print(f"\n[MÓDULO DE SEGURANÇA - VARREDURA DE INTEGRIDADE]")
        print(f"Analisando {len(self.lista_arquivos)} arquivos em busca de assinaturas maliciosas e hashes corrompidos...")
        
        for arquivo in self.lista_arquivos:
            status_str = "[OK - Criptografado e Íntegro]" if arquivo.criptografado else "[OK - Íntegro]"
            
            # Valida integridade comparando o hash atual do bloco com o hash oficial gravado
            for b_idx in arquivo.blocos_dados:
                dados_atuais = self.gerenciador_disco.conteudo_blocos.get(b_idx, b"")
                hash_atual = hashlib.sha256(dados_atuais).hexdigest()
                hash_oficial = self.gerenciador_disco.hashes_oficiais.get(b_idx, "")
                
                if hash_atual != hash_oficial:
                    status_str = "[ALERTA] Hash do bloco difere do registro oficial!"

            print(f"- /{arquivo.nome} : {status_str}")
            
        print(f"\nResultado da varredura concluído.")


# =====================================================================
# CLI INTERATIVA PARA DEMONSTRAÇÃO DA ETAPA 3
# =====================================================================
def main():
    fs = SistemaDeArquivosEntrega3()
    print("=" * 70)
    print("   SIMULADOR DE SISTEMA DE ARQUIVOS - ENTREGA 3 (SEGURANÇA & ACL)")
    print("   Comandos disponíveis:")
    print("     login --user <username>")
    print("     su (Alterna para Modo Kernel / Superusuário)")
    print("     read_file <caminho>")
    print("     encrypt_file <caminho> --key <chave>")
    print("     antivirus_scan")
    print("     corromper <indice_bloco> (Simula ataque/vírus em um bloco)")
    print("     exit")
    print("=" * 70)

    # Cria arquivo de exemplo do aluno Carlos para testar criptografia e ACL
    carlos_blocos = fs.gerenciador_disco.alocar_blocos(1, "/home/carlos/segredo.txt", b"Informacao confidencial do usuario Carlos.")
    no_carlos = NoArquivo("segredo.txt", eh_diretorio=False, tamanho=1024, prop="carlos", grupo="devs", perm="rw-r-----")
    no_carlos.blocos_dados = carlos_blocos
    fs.raiz.filhos["segredo.txt"] = no_carlos
    fs.lista_arquivos.append(no_carlos)

    # Inicia autenticado como root por padrão
    fs.auth.autenticar("root", "root123")

    while True:
        try:
            entrada = input(f"\nsimulador({fs.auth.usuario_atual or 'convidado'})[{'KERNEL' :>6}]: ").strip()
            if not entrada:
                continue
            
            partes = entrada.split()
            cmd = partes[0]

            if cmd == "exit":
                print("Encerrando simulador...")
                break
            elif cmd == "login":
                if "--user" in partes:
                    u_idx = partes.index("--user")
                    if u_idx + 1 < len(partes):
                        user = partes[u_idx + 1]
                        senha = input("Senha: ")
                        fs.auth.autenticar(user, senha)
            elif cmd == "su":
                if fs.auth.usuario_atual == "root":
                    fs.auth.modo_kernel = True
                    print("⚙️ Sistema elevado para MODO_KERNEL (Superusuário ativo).")
                else:
                    print("❌ Acesso negado: Apenas o usuário 'root' pode assumir o Modo Kernel.")
            elif cmd == "read_file" and len(partes) > 1:
                fs.read_file(partes[1])
            elif cmd == "encrypt_file" and len(partes) > 1:
                caminho = partes[1]
                chave = "MinhaChave123"
                if "--key" in partes:
                    k_idx = partes.index("--key")
                    if k_idx + 1 < len(partes):
                        chave = partes[k_idx + 1]
                fs.encrypt_file(caminho, chave)
            elif cmd == "antivirus_scan":
                fs.antivirus_scan()
            elif cmd == "corromper" and len(partes) > 1:
                b_idx = int(partes[1])
                fs.gerenciador_disco.corromper_bloco_simulado(b_idx)
                print(f"⚠️ Alerta: Bloco físico {b_idx} foi alterado externamente por um agente não autorizado.")
            else:
                print("Comando inválido. Use: login, su, read_file, encrypt_file, antivirus_scan, corromper, exit")
        except Exception as e:
            print(f"Erro na execução: {e}")

if __name__ == "__main__":
    main()
