.PHONY: audit

audit:
	@echo "🧹 Formatando..."
	@ruff format .
	@echo "🔧 Corrigindo o básico..."
	@ruff check . --fix
	@echo "🕵️  Gerando relatório de Code Smells para IA..."
	@ruff check . > code_smells.txt || true
	@echo "📄 Relatório salvo em 'code_smells.txt'"
