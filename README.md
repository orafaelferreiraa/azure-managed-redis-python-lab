# Azure Managed Redis Lab (Python)

Laboratorio de entrada para iniciantes em Cloud Computing, focado em cache distribuido com Azure Managed Redis usando Python e autenticacao passwordless com Microsoft Entra ID.

## Por que usar Redis?

Redis e usado para reduzir latencia e aliviar carga de banco relacional em leituras frequentes.

Exemplos reais (de forma pratica):
- E-commerce (pagina de produto):
  ao abrir um produto, a aplicacao primeiro tenta ler no Redis dados como nome, preco, estoque e avaliacao media. Se encontrar, responde em milissegundos sem consultar o banco principal.
- Sessao de usuario (login):
  apos autenticar, dados temporarios da sessao (id do usuario, perfil, permissoes) ficam no Redis com tempo de expiracao, evitando consultar o banco a cada requisicao.
- APIs com resposta repetida:
  em endpoints muito acessados (ex.: cotacao, ranking, catalogo), a resposta pode ser salva no Redis por alguns segundos/minutos, reduzindo custo e melhorando o tempo de resposta.

## Relacao entre Redis e banco de dados

Redis nao substitui o banco relacional. Ele funciona como camada de cache na frente do banco.

Fluxo comum (cache-aside):
1. A aplicacao recebe a requisicao e tenta ler a chave no Redis (ex.: `produto:123`).
2. Se a chave existir (cache hit), responde imediatamente sem consultar o banco.
3. Se a chave nao existir (cache miss), busca no banco relacional.
4. Salva o resultado no Redis com tempo de expiracao (TTL).
5. Retorna a resposta ao usuario.

Quem faz o que:
- Banco relacional: fonte oficial e persistente dos dados.
- Redis: copia temporaria dos dados mais acessados.

Consistencia dos dados:
- Quando um dado e alterado no banco, o cache precisa ser atualizado ou invalidado.
- Praticas comuns:
  - remover a chave do Redis apos update no banco;
  - atualizar banco e cache no mesmo fluxo;
  - usar TTL curto para limitar dados desatualizados.

## O que voce vai aprender

- Criar uma instancia do Azure Managed Redis.
- Configurar acesso com Entra ID (sem chave/senha no codigo).
- Conectar com Python e validar `PING`.
- Simular um banco de dados com arquivo JSON.
- Implementar fluxo cache-aside com cache miss, cache hit e invalidacao.
- Fazer limpeza de recursos para evitar custos.

## Estrutura do projeto

- `main.py`: orquestra o laboratorio e imprime cada etapa.
- `cache_lab.py`: conexao com Redis e operacoes de cache.
- `fake_database.py`: banco fake baseado em arquivo JSON.
- `data/products.json`: dados iniciais usados no laboratorio.
- `requirements.txt`: dependencias Python.

## Pre-requisitos

- Conta no Azure com permissao para criar recursos.
- Python 3.8+ instalado (recomendado 3.10+).
- Azure CLI instalado.
- Git (opcional, para clonar o codigo do GitHub).
  - Download: https://git-scm.com/downloads

Links oficiais:
- Python: https://www.python.org/downloads/
- Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli
- Quickstart oficial (PT-BR): https://learn.microsoft.com/pt-br/azure/redis/python-get-started

## 1) Criar o Azure Managed Redis no portal

1. Entre no Azure Portal.
2. Procure por Azure Managed Redis e clique em Create.
3. Escolha Subscription e Resource Group.
4. Defina um nome unico para o cache.
5. Conclua em Review + create.

Observacoes importantes:
- Neste quickstart, use endpoint publico.
- Entra ID ja vem habilitado por padrao no Azure Managed Redis.

## 2) Configurar acesso de dados (Entra ID)

1. Abra seu recurso do Azure Managed Redis.
2. Va em Authentication
3. Adicione seu usuario Entra ID como Redis user com permissao de leitura e escrita.
4. Aguarde alguns minutos para propagacao de permissao.

Observacao importante:
- Ser Owner da subscription nao garante acesso de data plane ao Redis.

## 3) Preparar ambiente local

No terminal, na pasta do projeto:

```bash
python3 -m venv .venv
```

Ative o ambiente virtual:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS/WSL:

```bash
source .venv/bin/activate
```

Confira se Python e pip sao da virtualenv:

```bash
which python
which pip
```

Os dois comandos devem apontar para `.venv/bin/...`.

Instale dependencias:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install redis redis-entraid azure-identity
```

Autentique no Azure:

```bash
az login --use-device-code
```

## 4) Configurar host

Exemplo:

```python
REDIS_HOST = "reds.brazilsouth.redis.azure.net:10000"
```

Observacao:
- Azure Managed Redis e clustered por padrao. Por isso o laboratorio usa roteamento por slot para direcionar cada chave ao shard correto.

## 5) Executar o laboratorio

```bash
python3 main.py
```

Para gerar metricas medias em repeticao (ex.: 5 rodadas):

```bash
python3 main.py --loops 5
```

Saida esperada (resumo):

```text
== Preparando o laboratorio ==
== Conexao com Redis ==
== Etapa 1: limpa o cache ==
== Etapa 2: primeira leitura ==
== Etapa 3: segunda leitura ==
== Etapa 4: atualiza o banco fake ==
== Etapa 5: invalida e recarrega o cache ==
== Metricas finais ==
```

## 6) Como validar que esta funcionando na pratica

O laboratorio agora usa um fluxo mais proximo do mundo real:

1. Banco fake em arquivo JSON
  - O arquivo `data/products.json` representa a fonte oficial dos dados.
  - No inicio da execucao, o laboratorio reseta esse arquivo para um estado conhecido.

2. Primeira leitura do produto
  - O cache e limpo antes.
  - A leitura deve sair como `cache-miss`.
  - O dado vem do banco fake e e salvo no Redis com TTL.

3. Segunda leitura do mesmo produto
  - A leitura deve sair como `cache-hit`.
  - O dado agora vem do Redis, com tempo menor.

4. Atualizacao do banco fake
  - O laboratorio altera preco e estoque no arquivo `data/products.json`.
  - Antes de invalidar, o cache ainda mostra o valor antigo.

5. Invalidacao e recarga
  - A chave do produto e removida do Redis.
  - A leitura seguinte busca o valor novo no banco fake e atualiza o cache.

Como saber se deu certo:
- `PING: True` confirma conectividade.
- Na primeira leitura aparece `Status: cache-miss (SEM CACHE / BANCO)`.
- Na segunda leitura aparece `Status: cache-hit (COM CACHE / REDIS)`.
- Em `Produto no banco apos update`, o preco muda no banco fake.
- Em `Cache Redis antes de invalidar`, o valor antigo ainda pode aparecer.
- Em `Produto retornado apos recarga (fonte: banco)`, o valor novo aparece apos invalidar.
- Em `Metricas finais`, a tabela mostra `Sem cache (ms)` maior que `Com cache (ms)`.
- A linha de resumo mostra `Reducao media` e `Aceleracao media` para apresentacao.

O ponto didatico do laboratorio e exatamente este:
- o banco fake e a fonte oficial;
- o Redis guarda uma copia temporaria;
- quando o dado muda na fonte oficial, o cache precisa ser invalidado ou atualizado.

## 7) Troubleshooting rapido

- Erro de autenticacao/permissao:
  - rode `az login` no mesmo terminal.
  - confirme que seu usuario foi adicionado como Redis user no recurso.
  - aguarde propagacao de RBAC/permissoes.
- Timeout de conexao:
  - confirme se `REDIS_HOST` esta no formato `host:porta` (ex.: `reds.brazilsouth.redis.azure.net:10000`).
  - confirme que o recurso esta com endpoint publico habilitado para o quickstart.
- Erro durante invalidacao/recarga:
  - rode novamente `python3 main.py` para repetir o fluxo desde o banco fake resetado.
  - confirme que a autenticacao `az login` continua valida no mesmo terminal.
- Modulo nao encontrado:
  - valide se o `.venv` esta ativo.
  - reinstale dependencias com `python -m pip install redis redis-entraid azure-identity`.
- Erro `externally-managed-environment` (PEP 668):
  - esse erro indica uso do pip do sistema em vez do pip da virtualenv.
  - ative a virtualenv com `source .venv/bin/activate` e repita a instalacao com `python -m pip ...`.

## 8) Limpeza de recursos

Ao final do laboratorio, exclua o recurso de Azure Managed Redis (ou o Resource Group de teste) para evitar custos recorrentes.

## Referencias oficiais

- Quickstart Python (PT-BR):
  https://learn.microsoft.com/pt-br/azure/redis/python-get-started
- Adicionar usuarios/principal ao cache (Entra ID):
  https://learn.microsoft.com/azure/redis/entra-for-authentication#add-users-or-system-principal-to-your-cache
- Criar Azure Managed Redis:
  https://learn.microsoft.com/azure/redis/quickstart-create-managed-redis
