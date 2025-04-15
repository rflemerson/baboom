# products/management/commands/compare_products.py

import requests
import time
import logging
import json
from datetime import datetime
import os

from django.core.management.base import BaseCommand

# --- Configurações ---
# API Externa (G Suplementos)
G_SUPLEMENTOS_API_BASE_URL = "https://www.gsuplementos.com.br/api/v2/front"
G_SUPLEMENTOS_STORE_NAME = "G Suplementos" # Usado no relatório
TARGET_CATEGORY_URL = "/whey-protein/"
REQUEST_DELAY_SECONDS_EXTERNAL = 1
PRODUCTS_PER_PAGE_EXTERNAL = 24

# API Local (Sua Aplicação Django)
LOCAL_API_BASE_URL = "http://127.0.0.1:8000/api" # Ajuste se necessário
LOCAL_API_PRODUCTS_ENDPOINT = f"{LOCAL_API_BASE_URL}/products/"
REQUEST_TIMEOUT_SECONDS = 30

# Arquivo de Saída
OUTPUT_DIR = "reports" # Cria um diretório para os relatórios
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILENAME = os.path.join(OUTPUT_DIR, f"comparison_report_{TIMESTAMP}.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = f'Compara produtos da API da {G_SUPLEMENTOS_STORE_NAME} com a API local e salva relatório JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--category', type=str, default=TARGET_CATEGORY_URL)
        parser.add_argument('--max-pages', type=int, default=None)
        parser.add_argument('--local-api-url', type=str, default=LOCAL_API_PRODUCTS_ENDPOINT)

    def _fetch_paginated_data(self, url, params=None, headers=None):
        """Helper para buscar dados de APIs paginadas (se suportarem /results ou similar)."""
        results = []
        current_url = url
        page = 1
        while current_url:
            logger.debug(f"Buscando API local: {current_url} com params {params}")
            try:
                response = requests.get(current_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                data = response.json()

                # Tenta encontrar a lista de resultados (adapte conforme sua API)
                page_results = data.get('results') # Comum em DRF com paginação
                if page_results is None:
                    if isinstance(data, list): # API retorna lista direto?
                         page_results = data
                         current_url = None # Assume que não há paginação se for lista direta
                    else: # Não achou 'results' nem é lista
                         logger.error(f"Formato de resposta inesperado da API local: {data}")
                         return None # Ou levanta um erro

                if page_results:
                    results.extend(page_results)

                # Lógica de Paginação (adapte conforme sua API DRF)
                current_url = data.get('next') # DRF padrão
                params = None # Params só são usados na primeira chamada normalmente
                page += 1
                if current_url:
                    logger.debug(f"Próxima página API local: {current_url}")
                    time.sleep(0.2) # Pequena pausa entre páginas locais

            except requests.exceptions.RequestException as e:
                logger.error(f"Erro ao buscar dados da API local '{current_url}': {e}")
                return None # Falha na busca local
            except json.JSONDecodeError as e:
                 logger.error(f"Erro ao decodificar JSON da API local '{current_url}': {e}")
                 return None

        return results


    def handle(self, *args, **options):
        category_url = options['category']
        max_pages_external = options['max_pages']
        local_api_url = options['local_api_url']
        page_external = 1

        # 1. Buscar dados da API Externa (G Suplementos)
        scraped_products = {}
        total_api_products_external = 0
        logger.info(f"Iniciando busca na API externa ({G_SUPLEMENTOS_STORE_NAME}) para '{category_url}'...")

        while True:
            external_api_url = f"{G_SUPLEMENTOS_API_BASE_URL}/url/product/listing/category"
            params = {
                'url': category_url,
                'pg': page_external,
                'offset': (page_external - 1) * PRODUCTS_PER_PAGE_EXTERNAL,
                'limit': PRODUCTS_PER_PAGE_EXTERNAL
            }
            logger.debug(f"Buscando API externa página {page_external}...")

            try:
                response = requests.get(external_api_url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro ao buscar dados da API externa na página {page_external}: {e}")
                break
            except json.JSONDecodeError as e:
                 logger.error(f"Erro ao decodificar JSON da API externa na página {page_external}: {e}")
                 break

            products_on_page = data.get('products', [])
            if not products_on_page:
                logger.debug("API externa: Não foram encontrados mais produtos.")
                break

            total_api_products_external += len(products_on_page)
            for product_data in products_on_page:
                api_product_id = product_data.get('sku') or product_data.get('id')
                if api_product_id:
                    scraped_products[str(api_product_id)] = {
                        'external_id': str(api_product_id),
                        'name': product_data.get('name', 'N/A'),
                        'brand': product_data.get('brand', {}).get('name', 'N/A'),
                        'price': product_data.get('price', {}).get('price', 'N/A'),
                        'url': product_data.get('url') # Path relativo
                    }
                else:
                     logger.warning(f"API externa: Produto encontrado sem ID (Nome: {product_data.get('name', 'N/A')}). Pulando.")

            logger.info(f"API Externa: Página {page_external} processada ({len(products_on_page)} produtos).")
            page_external += 1
            if max_pages_external and page_external > max_pages_external:
                logger.info(f"API Externa: Limite de {max_pages_external} páginas atingido.")
                break
            time.sleep(REQUEST_DELAY_SECONDS_EXTERNAL)

        logger.info(f"Busca API externa concluída. {len(scraped_products)} produtos com ID encontrados.")

        # 2. Buscar dados da API Local
        logger.info(f"Buscando produtos da API local: {local_api_url} ...")
        # Adiciona filtro para buscar apenas os que tem external_api_id, se sua API suportar
        # Ex: params={'external_api_id__isnull': 'false'} ou similar
        local_api_data = self._fetch_paginated_data(local_api_url)

        if local_api_data is None:
            logger.error("Não foi possível buscar dados da API local. Abortando comparação.")
            return

        local_products = {}
        for variant_data in local_api_data:
            ext_id = variant_data.get('external_api_id') # Verifique se o serializer expõe esse campo
            if ext_id:
                local_products[str(ext_id)] = {
                    'local_id': variant_data.get('id'),
                    'external_id': str(ext_id),
                    'name': variant_data.get('name', 'N/A'), # Nome combinado do serializer
                    'brand': variant_data.get('brand', 'N/A'), # Nome da marca do serializer
                    # Adicione outros campos da sua API local se útil para o relatório
                }
            # else: # Opcional: Logar variantes locais sem ID externo?
            #    logger.debug(f"API Local: Variante encontrada sem ID Externo (ID Local: {variant_data.get('id')}). Ignorando para comparação.")

        logger.info(f"Busca API local concluída. {len(local_products)} produtos com ID externo encontrados.")

        # 3. Comparar os Conjuntos de IDs
        scraped_ids = set(scraped_products.keys())
        local_ids = set(local_products.keys())

        ids_missing_in_local = scraped_ids - local_ids
        ids_missing_in_external = local_ids - scraped_ids

        # 4. Preparar Relatório JSON
        report = {
            'report_metadata': {
                'timestamp': datetime.now().isoformat(),
                'store_compared': G_SUPLEMENTOS_STORE_NAME,
                'external_api_category': category_url,
                'local_api_endpoint': local_api_url,
                'total_external_with_id': len(scraped_ids),
                'total_local_with_id': len(local_ids),
            },
            'missing_in_local_api': [
                scraped_products[pid] for pid in sorted(list(ids_missing_in_local))
            ],
            'missing_in_external_api': [
                local_products[pid] for pid in sorted(list(ids_missing_in_external))
            ]
        }

        # 5. Salvar Arquivo JSON
        try:
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            logger.info(self.style.SUCCESS(f"Relatório de comparação salvo em: {OUTPUT_FILENAME}"))
            # Imprimir resumo no console também
            self.stdout.write(self.style.WARNING(f"\nProdutos encontrados na API externa mas não na local: {len(ids_missing_in_local)}"))
            self.stdout.write(self.style.WARNING(f"Produtos encontrados na API local mas não na externa: {len(ids_missing_in_external)}"))
            self.stdout.write(f"Veja detalhes no arquivo: {OUTPUT_FILENAME}")

        except IOError as e:
            logger.error(f"Erro ao salvar o arquivo de relatório JSON '{OUTPUT_FILENAME}': {e}")
            # Opcional: Imprimir o JSON no console como fallback
            # print(json.dumps(report, indent=4, ensure_ascii=False))