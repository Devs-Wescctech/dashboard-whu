# dashboard-whu

API em Flask que compila dados do WHU utilizando a API da Wescctech.

## Endpoints

### `GET /`

Endpoint de status/boas-vindas (healthcheck simples).

### `GET /resumo-hoje`

Retorna o resumo de atendimentos de hoje.

Parâmetros de query:

- `canal` (opcional):
  - Se **não informado**: soma os atendimentos de todos os canais.
  - Se informado com um slug válido, traz apenas daquele canal.
  - Exemplos de valores aceitos:
    - `farmacia_joao_falcao`
    - `redes_sociais`
    - `atendimento_2`
    - `todos` (equivalente a não passar nada)

## Rodando localmente (sem Docker)

1. Crie um ambiente virtual (opcional, mas recomendado):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Execute a aplicação:

```bash
python app.py
```

Por padrão, ela sobe na porta **5000**:

- `http://localhost:5000/`
- `http://localhost:5000/resumo-hoje`
- `http://localhost:5000/resumo-hoje?canal=todos`

## Rodando com Docker

### Build da imagem

```bash
docker build -t dashboard-whu:local .
```

### Subindo o container

```bash
docker run -d   --name dashboard-whu   -p 5021:5000   dashboard-whu:local
```

Acesse:

- `http://localhost:5021/`
- `http://localhost:5021/resumo-hoje?canal=todos`

## Imagem no GHCR (exemplo de tags)

```bash
docker tag dashboard-whu:local ghcr.io/devs-wescctech/dashboard-whu:main
docker push ghcr.io/devs-wescctech/dashboard-whu:main
```
