from flask import Flask, jsonify, request
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES
# =========================

API_BASE = "https://api.wescctech.com.br/core/v2/api"

# Mapa de canais: slug -> { token, nome }
CHANNELS = {
    "farmacia_joao_falcao": {
        "token": "67fe5e4a3622f66e0b4e75bb",
        "nome": "Farmácia João Falcão",
    },
    "redes_sociais": {
        "token": "67af882c462a3ab786446c23",
        "nome": "Redes Sociais",
    },
    "atendimento_2": {
        "token": "67af8837f547555875680469",
        "nome": "Atendimento 2",
    },
}

# Canal padrão para buscar /users (qualquer um, pois os usuários são os mesmos)
DEFAULT_USERS_CHANNEL_SLUG = "atendimento_2"

# Status e typeChat conforme seus exemplos
STATUS_AUTOMATICO = 0
STATUS_AGUARDANDO = 1
STATUS_MANUAL = 2
STATUS_FINALIZADO = 3
TYPECHAT_PADRAO = 2  # em todos os exemplos é 2


# =========================
# FUNÇÕES AUXILIARES
# =========================

def get_headers_for_chats(canal_slug: str):
    """
    Headers com token do canal para /chats/count.
    """
    canal_info = CHANNELS.get(canal_slug)
    if not canal_info:
        return None, None

    token = canal_info["token"]
    headers = {
        "access-token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return headers, canal_info["nome"]


def get_headers_for_users():
    """
    Headers para /users.
    Usa um canal padrão (pois /users traz os mesmos atendentes para qualquer token).
    """
    canal_info = CHANNELS.get(DEFAULT_USERS_CHANNEL_SLUG)
    if not canal_info:
        if not CHANNELS:
            return None
        canal_info = next(iter(CHANNELS.values()))

    token = canal_info["token"]
    headers = {
        "access-token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return headers


def get_today_range_utc():
    """
    Início e fim do dia (00:00:00 até 23:59:59.999) em UTC,
    considerando horário local America/Sao_Paulo (UTC-3).
    """
    now_local = datetime.now()
    start_local = datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0)
    end_local = datetime(now_local.year, now_local.month, now_local.day, 23, 59, 59, 999000)

    offset = timedelta(hours=3)  # local + 3 = UTC
    start_utc = start_local + offset
    end_utc = end_local + offset

    start_iso = start_utc.isoformat() + "Z"
    end_iso = end_utc.isoformat() + "Z"

    return start_iso, end_iso


def build_date_filters():
    """
    Filtro de data para 'finalizado' (somente byStartDate).
    """
    start_iso, end_iso = get_today_range_utc()
    return {
        "dateFilters": {
            "byStartDate": {
                "start": start_iso,
                "finish": end_iso
            }
        }
    }


def chama_users(headers):
    """
    GET /users
    Retorna lista de usuários simplificada + total de online.
    """
    url = f"{API_BASE}/users"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        return None, None, f"Erro de conexão com /users: {e}"

    if not resp.ok:
        return None, None, f"Erro ao chamar /users: {resp.status_code} - {resp.text}"

    try:
        data = resp.json()
    except Exception as e:
        return None, None, f"Erro ao decodificar JSON de /users: {e} - corpo: {resp.text}"

    usuarios_brutos = []

    if isinstance(data, list):
        usuarios_brutos = data
    elif isinstance(data, dict) and isinstance(data.get("data"), list):
        usuarios_brutos = data["data"]
    else:
        return None, None, f"Estrutura inesperada em /users: {data}"

    usuarios_simplificados = []
    total_online = 0

    for u in usuarios_brutos:
        user_id = u.get("id")
        nome = u.get("name")
        status = u.get("status")

        usuarios_simplificados.append(
            {
                "id": user_id,
                "name": nome,
                "status": status,
                "atendimentosEmAndamento": None
            }
        )
        if isinstance(status, str) and status.upper() == "ONLINE":
            total_online += 1

    return usuarios_simplificados, total_online, None


def chama_chats_count(status, headers, usar_filtro_data=False):
    """
    POST /chats/count (GLOBAL)
    - automático / aguardando / manual: SEM filtro de data
    - finalizado: com filtro de data (dia atual)
    Lê 'result' como total.
    """
    url = f"{API_BASE}/chats/count"

    payload = {
        "status": status,
        "typeChat": TYPECHAT_PADRAO,
    }

    if usar_filtro_data:
        payload.update(build_date_filters())

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        return None, f"Erro de conexão com /chats/count (status={status}): {e}"

    if not resp.ok:
        return None, f"HTTP {resp.status_code} em /chats/count (status={status})"

    body_text = resp.text.strip()

    if body_text.isdigit():
        return int(body_text), None

    try:
        data = resp.json()
    except Exception:
        return None, "Retorno não JSON em /chats/count"

    if isinstance(data, dict):
        for key in ("result", "count", "total", "quantity", "amount"):
            if key in data and isinstance(data[key], (int, float)):
                return data[key], None

    return None, f"Não foi possível identificar o total em /chats/count: {data}"


def chama_chats_manual_por_usuario(user_id, headers):
    """
    POST /chats/count por usuário:
    {
      "status": 2,
      "typeChat": 2,
      "userId": "<user_id>"
    }
    """
    url = f"{API_BASE}/chats/count"

    payload = {
        "status": STATUS_MANUAL,
        "typeChat": TYPECHAT_PADRAO,
        "userId": user_id
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        return None, f"Erro de conexão com /chats/count (manual por usuário {user_id}): {e}"

    if not resp.ok:
        return None, f"HTTP {resp.status_code} em /chats/count (manual por usuário {user_id})"

    body_text = resp.text.strip()

    if body_text.isdigit():
        return int(body_text), None

    try:
        data = resp.json()
    except Exception:
        return None, f"Retorno não JSON em /chats/count (manual por usuário {user_id})"

    if isinstance(data, dict):
        for key in ("result", "count", "total", "quantity", "amount"):
            if key in data and isinstance(data[key], (int, float)):
                return data[key], None

    return None, f"Não foi possível identificar o total em /chats/count (manual por usuário {user_id})"


# =========================
# BUILDERS DE RESUMO
# =========================

def build_resumo_por_canal(canal_slug: str, headers_users):
    """
    Monta o mesmo body do /resumo-hoje, mas apenas para 1 canal.
    """
    avisos = []
    hoje_str = datetime.now().date().isoformat()

    headers_chats, canal_nome = get_headers_for_chats(canal_slug)
    if not headers_chats:
        return {"erro": f"Canal '{canal_slug}' não encontrado em CHANNELS"}, 400

    # Usuários (globais)
    usuarios, usuarios_online, err_users = chama_users(headers_users)
    if err_users:
        avisos.append(err_users)

    # Contagens globais do canal
    automatico, err_auto = chama_chats_count(STATUS_AUTOMATICO, headers_chats, usar_filtro_data=False)
    if err_auto:
        avisos.append(f"automatico: {err_auto}")

    aguardando, err_aguard = chama_chats_count(STATUS_AGUARDANDO, headers_chats, usar_filtro_data=False)
    if err_aguard:
        avisos.append(f"aguardando: {err_aguard}")

    manual, err_manual = chama_chats_count(STATUS_MANUAL, headers_chats, usar_filtro_data=False)
    if err_manual:
        avisos.append(f"manual: {err_manual}")

    finalizado, err_final = chama_chats_count(STATUS_FINALIZADO, headers_chats, usar_filtro_data=True)
    if err_final:
        avisos.append(f"finalizado: {err_final}")

    # Atendimentos manuais em andamento por usuário (apenas ONLINE)
    if usuarios:
        for u in usuarios:
            uid = u.get("id")
            status = (u.get("status") or "").upper()

            if not uid:
                u["atendimentosEmAndamento"] = None
                continue

            if status != "ONLINE":
                u["atendimentosEmAndamento"] = 0
                continue

            qtd, err_user = chama_chats_manual_por_usuario(uid, headers_chats)
            if err_user:
                avisos.append(f"usuario {u.get('name')} ({uid}): {err_user}")
                u["atendimentosEmAndamento"] = None
            else:
                u["atendimentosEmAndamento"] = qtd

    resposta = {
        "canal_slug": canal_slug,
        "canal_nome": canal_nome,
        "dataReferencia": hoje_str,
        "usuariosOnline": usuarios_online,
        "usuarios": usuarios,
        "clientes": {
            "automatico": automatico,
            "aguardando": aguardando,
            "manual": manual,
            "finalizado": finalizado,
        },
    }

    if avisos:
        resposta["avisos"] = avisos

    return resposta, 200


def build_resumo_todos(headers_users):
    """
    Mesmo formato do /resumo-hoje, porém SOMANDO os atendimentos dos 3 canais.
    Usuários continuam sendo a lista global, e 'atendimentosEmAndamento'
    de cada usuário é a soma nos 3 canais.
    """
    avisos = []
    hoje_str = datetime.now().date().isoformat()

    # Usuários (globais)
    usuarios, usuarios_online, err_users = chama_users(headers_users)
    if err_users:
        avisos.append(err_users)

    # Totais somados
    total_automatico = 0
    total_aguardando = 0
    total_manual = 0
    total_finalizado = 0

    # Cache de headers por canal
    headers_por_canal = {}

    for canal_slug, info in CHANNELS.items():
        headers_chats, canal_nome_tmp = get_headers_for_chats(canal_slug)
        if not headers_chats:
            avisos.append(f"Canal '{canal_slug}' sem headers válidos.")
            continue

        headers_por_canal[canal_slug] = headers_chats

        automatico, err_auto = chama_chats_count(STATUS_AUTOMATICO, headers_chats, usar_filtro_data=False)
        if err_auto:
            avisos.append(f"[{canal_slug}] automatico: {err_auto}")
        else:
            total_automatico += automatico or 0

        aguardando, err_aguard = chama_chats_count(STATUS_AGUARDANDO, headers_chats, usar_filtro_data=False)
        if err_aguard:
            avisos.append(f"[{canal_slug}] aguardando: {err_aguard}")
        else:
            total_aguardando += aguardando or 0

        manual, err_manual = chama_chats_count(STATUS_MANUAL, headers_chats, usar_filtro_data=False)
        if err_manual:
            avisos.append(f"[{canal_slug}] manual: {err_manual}")
        else:
            total_manual += manual or 0

        finalizado, err_final = chama_chats_count(STATUS_FINALIZADO, headers_chats, usar_filtro_data=True)
        if err_final:
            avisos.append(f"[{canal_slug}] finalizado: {err_final}")
        else:
            total_finalizado += finalizado or 0

    # Atendimentos manuais em andamento por usuário (somando nos 3 canais)
    if usuarios:
        for u in usuarios:
            uid = u.get("id")
            status = (u.get("status") or "").upper()

            if not uid:
                u["atendimentosEmAndamento"] = None
                continue

            if status != "ONLINE":
                u["atendimentosEmAndamento"] = 0
                continue

            total_por_usuario = 0
            for canal_slug, headers_chats in headers_por_canal.items():
                qtd, err_user = chama_chats_manual_por_usuario(uid, headers_chats)
                if err_user:
                    avisos.append(f"[{canal_slug}] usuario {u.get('name')} ({uid}): {err_user}")
                    continue
                total_por_usuario += qtd or 0

            u["atendimentosEmAndamento"] = total_por_usuario

    resposta = {
        "canal_slug": "todos",
        "canal_nome": "Todos os canais",
        "dataReferencia": hoje_str,
        "usuariosOnline": usuarios_online,
        "usuarios": usuarios,
        "clientes": {
            "automatico": total_automatico,
            "aguardando": total_aguardando,
            "manual": total_manual,
            "finalizado": total_finalizado,
        },
    }

    if avisos:
        resposta["avisos"] = avisos

    return resposta, 200


# =========================
# ENDPOINTS
# =========================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "API de dashboard rodando",
        "canais_disponiveis": list(CHANNELS.keys()),
        "canal_padrao_usuarios": DEFAULT_USERS_CHANNEL_SLUG,
        "endpoints": ["/resumo-hoje"]
    })


@app.route("/resumo-hoje", methods=["GET"])
def resumo_hoje():
    """
    - Sem parâmetro ?canal -> soma dos 3 canais (canal_slug='todos')
    - Com ?canal=slug -> apenas aquele canal
    """
    canal_slug = request.args.get("canal", None)

    headers_users = get_headers_for_users()
    if not headers_users:
        return jsonify({"erro": "Não foi possível obter headers para /users"}), 500

    # Sem canal ou canal=todos => resumo geral somando todos
    if not canal_slug or canal_slug == "todos":
        resposta, status_code = build_resumo_todos(headers_users)
        return jsonify(resposta), status_code

    # Canal específico
    if canal_slug not in CHANNELS:
        return jsonify({
            "erro": f"Canal '{canal_slug}' não encontrado. Use um destes: {list(CHANNELS.keys())} ou 'todos'."
        }), 400

    resposta, status_code = build_resumo_por_canal(canal_slug, headers_users)
    return jsonify(resposta), status_code


if __name__ == "__main__":
    # Porta 5000 para alinhar com o Docker (EXPOSE 5000 / gunicorn)
    # host=0.0.0.0 permite acessar de outras máquinas na rede em ambiente local
    app.run(host="0.0.0.0", debug=True, port=5000)
