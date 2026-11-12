# Simulador de Sistema de Arquivos

Projeto desenvolvido em Python para a disciplina de Sistemas Operacionais.

As entregas estão em arquivos separados, mas são integradas. A segunda utiliza a primeira, e a terceira utiliza as funcionalidades das duas anteriores.

## Requisitos

- Python 3 instalado (para execução no computador).
- Biblioteca `cryptography` (necessária para a terceira entrega).

Para instalar a biblioteca no computador, execute no terminal:

```bash
python -m pip install cryptography
```

## Executando no Google Colab

Em um notebook novo, execute os comandos abaixo, um por célula.

Instale a biblioteca:

```python
!pip install cryptography
```

Clone o repositório:

```python
!git clone https://github.com/KooKs0/simulador-sistema-arquivos.git
```

Entre na pasta:

```python
%cd /content/simulador-sistema-arquivos
```

Execute a entrega desejada:

**Entrega 1:**
```python
%run simulador_sistema_arquivos_entrega1.py
```

**Entrega 2:**
```python
%run sistema_arquivos_entrega2.py
```

**Entrega 3:**
```python
%run sistema_arquivos_entrega3.py
```

## Executando no computador

Baixe o projeto pelo GitHub utilizando a opção **Code > Download ZIP** e extraia os arquivos em uma pasta.

Também é possível clonar o repositório pelo terminal:

```bash
git clone https://github.com/KooKs0/simulador-sistema-arquivos.git
```

Abra o terminal na pasta onde estão os arquivos do projeto.

Para executar a primeira entrega:

```bash
python simulador_sistema_arquivos_entrega1.py
```

Para executar a segunda entrega:

```bash
python sistema_arquivos_entrega2.py
```

Para executar a terceira entrega:

```bash
python sistema_arquivos_entrega3.py
```

Os arquivos também podem ser abertos em um editor Python, como VS Code ou IDLE, e executados por ele.

**Importante:** os três arquivos devem permanecer na mesma pasta, pois as entregas utilizam importações entre si.

Em alguns computadores, pode ser necessário utilizar `python3` no lugar de `python` ou `py` no Windows.

## Dicas para os testes

- Utilize `help` para consultar os comandos disponíveis em cada entrega.
- Utilize `exit` para encerrar a execução.
- Os comandos do simulador devem ser digitados um de cada vez, após o programa iniciar.
- Na terceira entrega, a conta inicial para testes é `root`, com senha `root123`. Para entrar, utilize `login root root123`.
- Na segunda e terceira entregas, `raid_status`, `raid_fail` e `raid_rebuild` permitem verificar o funcionamento do RAID 5.
- Na terceira entrega, `antivirus_scan` verifica a integridade dos arquivos e `corrupt` permite simular uma alteração nos dados.
- Os dados ficam armazenados em memória e não são preservados após o encerramento do programa.

## Arquivos do projeto

- `simulador_sistema_arquivos_entrega1.py` — gerenciamento de arquivos, diretórios e blocos.
- `sistema_arquivos_entrega2.py` — RAID 5 e escalonamento SSTF.
- `sistema_arquivos_entrega3.py` — usuários, permissões, criptografia e verificação de integridade.
