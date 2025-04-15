# products/management/commands/update_prices.py

import requests
import time
import logging
import json
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

# --- Configurações ---
# API Externa (G Suplementos)
G_SUPLEMENTOS_API_BASE_URL = "https://www.gsuplementos.com.br/api/v2/front"
G_SUPLEMENTOS_PRODUCT_DETAIL_ENDPOINT = "/product/{product_id}" # SUPOSIÇÃO! Ajuste se necessário
REQUEST_DELAY_SECONDS_EXTERNAL = 0.5 # Pausa entre chamadas de detalhe externo

# API Local (Sua Aplicação Django)
LOCAL_API_BASE_URL = "http://127.0.0.1:8000/api" # Ajuste se necessário
LOCAL_API_PRODUCTS_ENDPOINT = f"{LOCAL_API_BASE_URL}/products/"
# Endpoint para POST de preço - EXIGE O ID DA VARIANTE LOCAL
LOCAL_API_PRICE_POST_ENDPOINT = f"{LOCAL_API_BASE_URL}/products/{{local_variant_id}}/prices/"
REQUEST_TIMEOUT_SECONDS = 20

# ID da Loja na sua API Local - IMPORTANTE: Obtenha o ID correto!
# Idealmente, busque via API (ex: /api/stores/?name=G%20Suplementos) no início do script.
# Por simplicidade, vamos usar um placeholder. AJUSTE ESTE VALOR!
G_SUPLEMENTOS_LOCAL_STORE_ID = 1 # <<< AJUSTE O ID DA LOJA G SUPLEMENTOS NO SEU DB/API

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Atualiza preços/estoque via API local, buscando dados da API externa.'

    def add_arguments(self, parser):
         parser.add_argument('--local-api-url', type=str, default=LOCAL_API_PRODUCTS_ENDPOINT)
         # Poderia adicionar argumento para --store-id se quisesse tornar mais flexível

    def _fetch_paginated_data(self, url, params=None, headers=None):
        """Helper para buscar dados de APIs paginadas locais."""
        # (Igual ao do script compare_products_api.py - pode ser movido para um utils)
        results = []
        current_url = url
        page = 1
        while current_url:
            logger.debug(f"Buscando API local: {current_url} com params {params}")
            try:
                response = requests.get(current_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                data = response.json()
                page_results = data.get('results')
                if page_results is None:
                    if isinstance(data, list):
                         page_results = data
                         current_url = None
                    else:
                         logger.error(f"Formato inesperado da API local: {data}")
                         return None
                if page_results: results.extend(page_results)
                current_url = data.get('next')
                params = None
                page += 1
                if current_url: time.sleep(0.2)
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro ao buscar API local '{current_url}': {e}")
                return None
            except json.JSONDecodeError as e:
                 logger.error(f"Erro ao decodificar JSON da API local '{current_url}': {e}")
                 return None
        return results

    def handle(self, *args, **options):
        local_api_url = options['local_api_url']

        if not G_SUPLEMENTOS_LOCAL_STORE_ID:
             logger.error("ID da Loja local (G_SUPLEMENTOS_LOCAL_STORE_ID) não configurado no script. Abortando.")
             return

        # 1. Buscar Produtos da API Local (que tenham ID externo)
        logger.info(f"Buscando produtos da API local com ID externo: {local_api_url} ...")
        # Adicionar filtro aqui se a API permitir: params={'external_api_id__isnull': 'false'}
        local_variants_data = self._fetch_paginated_data(local_api_url)

        if local_variants_data is None:
            logger.error("Falha ao buscar produtos da API local. Abortando.")
            return

        variants_to_update = []
        for item in local_variants_data:
            if item.get('external_api_id'):
                variants_to_update.append({
                    'local_id': item.get('id'),
                    'external_id': str(item.get('external_api_id')),
                    'name': item.get('name', 'N/A') # Para logging
                })

        logger.info(f"Encontradas {len(variants_to_update)} variantes na API local com ID externo para verificar.")

        update_success_count = 0
        update_error_count = 0

        # 2. Iterar e Atualizar cada Produto
        for variant in variants_to_update:
            local_id = variant['local_id']
            external_id = variant['external_id']
            variant_name = variant['name']
            logger.debug(f"Processando: {variant_name} (Local ID: {local_id}, Ext ID: {external_id})")

            # 3. Buscar Dados Atuais da API Externa
            external_detail_url = f"{G_SUPLEMENTOS_API_BASE_URL}{G_SUPLEMENTOS_PRODUCT_DETAIL_ENDPOINT.format(product_id=external_id)}"
            current_price = None
            stock_available_api = None # Ex: True/False
            product_full_url = None

            try:
                headers = {'User-Agent': 'MeuAppDeMonitoramentoDePrecos/1.0'} # Seja um bom vizinho
                response = requests.get(external_detail_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)

                if response.status_code == 404:
                    logger.warning(f"API externa 404 para Ext ID {external_id} ({variant_name}). Produto pode ter sido removido.")
                    # Opcional: Chamar um endpoint da sua API local para marcar como inativo?
                    update_error_count += 1
                    time.sleep(REQUEST_DELAY_SECONDS_EXTERNAL)
                    continue
                response.raise_for_status()
                product_data = response.json()

                # Extrair Preço, Estoque, URL (AJUSTE CONFORME A API REAL)
                price_str = product_data.get('price', {}).get('price')
                stock_info = product_data.get('stock')
                if isinstance(stock_info, dict): stock_available_api = stock_info.get('available')
                elif isinstance(stock_info, bool): stock_available_api = stock_info
                if stock_available_api is None: stock_available_api = False # Assume esgotado se não achar info

                url_path = product_data.get('url')
                if url_path: product_full_url = f"https://www.gsuplementos.com.br{url_path}" # Assume URL base

                if price_str:
                    try: current_price = Decimal(price_str)
                    except (InvalidOperation, TypeError): logger.error(f"Formato de preço inválido ('{price_str}') da API externa para Ext ID {external_id}.")
                else: logger.warning(f"Preço não encontrado na API externa para Ext ID {external_id}.")

            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de rede/API ao buscar detalhes externos para Ext ID {external_id}: {e}")
                update_error_count += 1
                time.sleep(REQUEST_DELAY_SECONDS_EXTERNAL)
                continue
            except Exception as e:
                logger.error(f"Erro inesperado ao processar API externa para Ext ID {external_id}: {e}", exc_info=True)
                update_error_count += 1
                time.sleep(REQUEST_DELAY_SECONDS_EXTERNAL)
                continue

            # 4. Enviar Atualização para API Local (se tiver preço)
            if current_price is not None:
                # Mapear status da API para o seu model ('A', 'L', 'O')
                stock_code = 'A' if stock_available_api else 'O'

                # Preparar payload para POST na API Local
                price_payload = {
                    'store_id': G_SUPLEMENTOS_LOCAL_STORE_ID, # ID da loja G Suplementos na sua API
                    'price': str(current_price), # Enviar como string é mais seguro para JSON com Decimais
                    'stock_status': stock_code,
                    'affiliate_link': product_full_url or "" # Envia URL atualizada ou vazia
                }

                post_url = LOCAL_API_PRICE_POST_ENDPOINT.format(local_variant_id=local_id)
                logger.debug(f"Enviando POST para {post_url} com payload: {price_payload}")

                try:
                    # Adicionar autenticação se sua API local exigir (ex: Headers com Token)
                    headers_local = {'Content-Type': 'application/json'}
                    # headers_local['Authorization'] = 'Bearer SEU_TOKEN_AQUI' # Exemplo
                    post_response = requests.post(post_url, json=price_payload, headers=headers_local, timeout=REQUEST_TIMEOUT_SECONDS)
                    post_response.raise_for_status() # Levanta erro para 4xx/5xx

                    if post_response.status_code == 201: # HTTP 201 Created (sucesso DRF padrão)
                        logger.info(f"Preço/Estoque atualizado com sucesso via API local para: {variant_name} (Local ID: {local_id})")
                        update_success_count += 1
                    else:
                        # Status inesperado, mas sem erro HTTP
                        logger.warning(f"API local retornou status {post_response.status_code} inesperado para {variant_name} (Local ID: {local_id}). Resposta: {post_response.text}")
                        update_error_count += 1

                except requests.exceptions.RequestException as e:
                    logger.error(f"Erro ao enviar POST para API local ({post_url}): {e}")
                    try:
                         logger.error(f"Resposta da API (se houver): {e.response.text}") # Loga erro da API
                    except: pass
                    update_error_count += 1
                except Exception as e:
                     logger.error(f"Erro inesperado ao postar atualização local para {variant_name}: {e}", exc_info=True)
                     update_error_count += 1

            else:
                logger.warning(f"Não foi possível obter preço da API externa para {variant_name} (Ext ID: {external_id}). Nenhuma atualização enviada.")
                update_error_count += 1

            # Pausa antes de processar o próximo produto
            time.sleep(REQUEST_DELAY_SECONDS_EXTERNAL)
            # --- Fim do loop de variantes ---

        logger.info("--- Atualização de Preços via API Concluída ---")
        logger.info(f"Total de variantes verificadas: {len(variants_to_update)}")
        logger.info(f"Atualizações enviadas com sucesso via API: {update_success_count}")
        logger.info(f"Erros encontrados durante o processo: {update_error_count}")