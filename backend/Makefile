.PHONY: run test unit integration eval-retrieval eval-generation ingest clean

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	python -m unittest discover -s tests/unit
	python -m unittest discover -s tests/integration

unit:
	python -m unittest discover -s tests/unit

integration:
	python -m unittest discover -s tests/integration

eval-retrieval:
	python scripts/run_retrieval_eval.py --top-k 5

eval-generation:
	python scripts/run_generation_eval.py

ingest:
	python scripts/ingest_documents.py
