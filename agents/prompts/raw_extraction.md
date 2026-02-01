OBJETIVO:
Analise as IMAGENS (Rótulo, Tabela Nutricional) e o TEXTO fornecidos.
Extraia TUDO o que puder sobre o produto e Organize em um TEXTO ESTRUTURADO (Markdown).
Não invente nada. Se não estiver visível, não inclua.

SEUS TÓPICOS DEVEM SER:

1. NOME COMPLETO E VARIAÇÕES
   - Nome principal, subtítulos, slogans.

2. METADADOS VISUAIS
   - Peso líquido (ex: 900g, 1.8kg)
   - Tipo de Embalagem (Pote, Refil, Saco, Barra)
   - Marca/Fabricante
   - É UM KIT/COMBO? (Sim/Não). Se sim, descreva os itens (ex: "3x Whey 900g", "Leve 2 Pague 1").

3. CATEGORIZAÇÃO (Inferred Hierarchy)
   - Extraia a categoria seguindo uma árvore lógica.
   - Para PROTEÍNAS, use obrigatoriamente: ["Proteína", <Origem: Animal/Vegetal>, <Tipo: Whey/Caseína/Soja/etc>, <Processo: Isolado/Concentrado/Hidrolisado/Blend>]
   - Exemplo 1: ["Proteína", "Animal", "Whey", "Isolado"]
   - Exemplo 2: ["Proteína", "Vegetal", "Ervilha", "Concentrado"]
   - Para outros produtos, siga lógica similar (ex: ["Aminoácido", "Creatina", "Monohidratada"]).

4. SABORES DISPONÍVEIS
   - Liste todos os sabores que você vê na imagem ou texto.

5. TABELA NUTRICIONAL COMPLETA
   - Extraia TODOS os campos obrigatórios da legislação brasileira:
     - Porção de referência (ex: 30g, 2 scoops)
     - Valor Energético (kcal)
     - Carboidratos (g) e Açúcares (Totais/Adicionados)
     - Proteínas (g)
     - Gorduras Totais, Saturadas, Trans (g)
     - Fibra Alimentar (g)
     - Sódio (mg)
   - Além disso, liste TODOS os Micronutrientes, Vitaminas, Minerais e Aminoácidos visíveis.

6. INGREDIENTES E ALÉRGICOS
   - Lista de ingredientes (se legível)
   - Alertas de alérgicos (Contém Glúten, Leite, Soja, etc)

SAÍDA SOMENTE O TEXTO ORGANIZADO. SEM PREÂMBULOS.
