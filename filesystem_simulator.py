import os
import sys

class BlockManager:
    def __init__(self, total_blocks=16, block_size=4096):
        self.total_blocks = total_blocks
        self.block_size = block_size  # em bytes (ex: 4KB = 4096)
        # 0: Livre, 1: Ocupado/Reservado
        self.blocks = [False] * total_blocks
        self.block_info = [("LIVRE", "")] * total_blocks

    def allocate_blocks(self, count, info_desc):
        """Aloca blocos contíguos ou livres (exemplo simplificado: primeiros livres)"""
        allocated = []
        for i in range(self.total_blocks):
            if not self.blocks[i]:
                allocated.append(i)
                if len(allocated) == count:
                    break
        
        if len(allocated) < count:
            raise MemoryError("Espaço em disco insuficiente (Sem blocos livres suficientes).")
        
        for idx in allocated:
            self.blocks[idx] = True
            self.block_info[idx] = ("DADO", info_desc)
        return allocated

    def free_blocks(self, block_list):
        for idx in block_list:
            if 0 <= idx < self.total_blocks:
                self.blocks[idx] = False
                self.block_info[idx] = ("LIVRE", "")

    def mark_reserved(self, idx, desc):
        if 0 <= idx < self.total_blocks:
            self.blocks[idx] = True
            self.block_info[idx] = (desc, "")

    def get_external_fragmentation(self):
        """Calcula blocos livres dispersos (impossibilitam alocação contígua grande, se aplicável)"""
        # Para alocação indexada pura, fragmentação externa por contiguidade é zero, 
        # mas podemos medir blocos livres não adjacentes.
        free_blocks = [i for i, used in enumerate(self.blocks) if not used]
        if not free_blocks:
            return 0
        
        # Conta quantas ilhas de blocos livres existem
        islands = 1
        for i in range(1, len(free_blocks)):
            if free_blocks[i] != free_blocks[i-1] + 1:
                islands += 1
        
        # Se há blocos livres mas fragmentados em ilhas menores que a maior necessidade
        return len(free_blocks) * self.block_size if islands > 1 else 0


class FileNode:
    def __init__(self, name, is_dir=False, size=0, parent=None):
        self.name = name
        self.is_dir = is_dir
        self.size = size  # em bytes
        self.parent = parent
        self.children = {} if is_dir else None
        self.inode_block = None
        self.data_blocks = []


class FileSystemSimulator:
    def __init__(self, total_blocks=16, block_size=4096):
        self.bm = BlockManager(total_blocks, block_size)
        self.root = FileNode("/", is_dir=True)
        self.cwd = self.root
        
        # Aloca Bloco 0 para o i-node raiz
        self.bm.mark_reserved(0, "INODE_RAIZ")
        self.root.inode_block = 0

    def resolve_path(self, path_str):
        if path_str.startswith("/"):
            current = self.root
            parts = [p for p in path_str.split("/") if p]
        else:
            current = self.cwd
            parts = [p for p in path_str.split("/") if p and p != "."]

        for part in parts:
            if part == "..":
                if current.parent:
                    current = current.parent
            elif part in current.children:
                current = current.children[part]
            else:
                return None, parts
        return current, parts

    def mkdir(self, path_str):
        parent_node, parts = self.resolve_path(path_str)
        if not parts:
            print(f"Erro: Caminho inválido ou já existe.")
            return

        dir_name = parts[-1]
        # Resolver o pai real
        if len(parts) > 1:
            parent_path = "/" + "/".join(parts[:-1]) if path_str.startswith("/") else "/".join(parts[:-1])
            parent_node, _ = self.resolve_path(parent_path)

        if parent_node and parent_node.is_dir:
            if dir_name in parent_node.children:
                print(f"Erro: Diretório '{dir_name}' já existe.")
                return
            new_dir = FileNode(dir_name, is_dir=True, parent=parent_node)
            parent_node.children[dir_name] = new_dir
            print(f"Diretório criado: {path_str}")
        else:
            print(f"Erro: Caminho pai não encontrado.")

    def create_file(self, path_str, size_bytes):
        parent_node, parts = self.resolve_path(path_str)
        if not parts:
            print(f"Erro: Caminho inválido.")
            return

        file_name = parts[-1]
        if len(parts) > 1:
            parent_path = "/" + "/".join(parts[:-1]) if path_str.startswith("/") else "/".join(parts[:-1])
            parent_node, _ = self.resolve_path(parent_path)

        if parent_node and parent_node.is_dir:
            if file_name in parent_node.children:
                print(f"Erro: Arquivo '{file_name}' já existe.")
                return

            # Calcular blocos necessários
            block_size = self.bm.block_size
            num_blocks = (size_bytes + block_size - 1) // block_size
            total_needed = 1 + num_blocks  # 1 para i-node do arquivo + blocos de dados

            try:
                # Alocar i-node do arquivo (1 bloco)
                inode_blocks = self.bm.allocate_blocks(1, f"INODE_{file_name.upper()}")
                inode_idx = inode_blocks[0]

                # Alocar blocos de dados
                data_blocks = self.bm.allocate_blocks(num_blocks, f"'{path_str}'")
            except MemoryError as e:
                print(f"Erro de Alocação: {e}")
                return

            new_file = FileNode(file_name, is_dir=False, size=size_bytes, parent=parent_node)
            new_file.inode_block = inode_idx
            new_file.data_blocks = data_blocks

            parent_node.children[file_name] = new_file
            print(f"Arquivo criado: {path_str} ({size_bytes} bytes)")
        else:
            print(f"Erro: Diretório pai não encontrado.")

    def print_tree(self, node=None, prefix=""):
        if node is None:
            node = self.root
        
        print(f"{prefix}{node.name}{'/' if node.is_dir else ''} {'[DIR]' if node.is_dir else f'({node.size // 1024} KB) [ARQ]'}")
        if node.is_dir and node.children:
            items = list(node.children.items())
            for i, (name, child) in enumerate(items):
                connector = "└── " if i == len(items) - 1 else "├── "
                extension = "    " if i == len(items) - 1 else "│   "
                self._print_tree_recursive(child, prefix + connector, extension)

    def _print_tree_recursive(self, node, prefix, current_prefix):
        print(f"{prefix}{node.name}{'/' if node.is_dir else ''} {'[DIR]' if node.is_dir else f'({node.size} bytes) [ARQ]'}")
        if node.is_dir and node.children:
            items = list(node.children.items())
            for i, (name, child) in enumerate(items):
                connector = "└── " if i == len(items) - 1 else "├── "
                extension = "    " if i == len(items) - 1 else "│   "
                self._print_tree_recursive(child, current_prefix + connector, current_prefix + extension)

    def fs_status(self):
        print(f"\nTamanho do Bloco de Disco: {self.bm.block_size // 1024} KB | Total de Blocos: {self.bm.total_blocks} ({self.bm.total_blocks * self.bm.block_size // 1024} KB)\n")
        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        
        # Exibe blocos detalhados
        i = 0
        while i < self.bm.total_blocks:
            status, desc = self.bm.block_info[i]
            if status == "LIVRE":
                start_free = i
                while i < self.bm.total_blocks and self.bm.block_info[i][0] == "LIVRE":
                    i += 1
                end_free = i - 1
                if start_free == end_free:
                    print(f"Bloco {start_free:02d}                  : [LIVRE]")
                else:
                    print(f"Bloco {start_free:02d}..{end_free:02d}             : [LIVRE]")
            else:
                print(f"Bloco {i:02d} [{status:<11}] : {desc}")
                i += 1

        # Coleta dados de arquivos para relatório
        self._print_fragmentation_report(self.root)

    def _print_fragmentation_report(self, node):
        # Percorre a árvore para achar arquivos e calcular fragmentação
        files = []
        def collect_files(n):
            if not n.is_dir:
                files.append(n)
            else:
                for child in n.children.values():
                    collect_files(child)
        collect_files(node)

        for f in files:
            block_size = self.bm.block_size
            num_allocated_blocks = len(f.data_blocks)
            allocated_bytes = num_allocated_blocks * block_size
            internal_frag = allocated_bytes - f.size
            waste_pct = (internal_frag / allocated_bytes * 100) if allocated_bytes > 0 else 0
            
            print(f"\n--- RELATÓRIO DE FRAGMENTAÇÃO PARA: {f.name} ---")
            print(f"Tamanho Real do Arquivo          : {f.size} bytes ({f.size // 1024} KB)")
            print(f"Espaço Alocado no Disco          : {allocated_bytes} bytes ({num_allocated_blocks} blocos de {block_size // 1024} KB)")
            print(f"Fragmentação Interna             : {internal_frag} bytes ({waste_pct:.0f}% de desperdício no último bloco)")
            print(f"Fragmentação Externa             : 0 bytes")
            print(f"Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)")


# --- Demonstração Automatizada (Exemplos do Enunciado) ---
if __name__ == "__main__":
    fs = FileSystemSimulator(total_blocks=16, block_size=4096)
    
    print("=== EXECUTANDO COMANDOS DE SIMULAÇÃO ===")
    print("> mkdir /sistema")
    fs.mkdir("/sistema")
    
    print("> mkdir /sistema/logs")
    fs.mkdir("/sistema/logs")
    
    print("> create /sistema/logs/app.log --size 10240")
    fs.create_file("/sistema/logs/app.log", 10240) # 10 KB = 10240 bytes
    
    print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]")
    fs.print_tree()
    
    print("\n> fs_status --details")
    fs.fs_status()
