.PHONY: install test

install:
	pip install -r requirements.txt

test:
	python3 -m pytest completeness_proof/tests/ kci/tests/ policy_gate/tests/ aibom/tests/ -v
