PYTHON=.env/bin/python
PIP=.env/bin/pip
STREAMLIT=.env/bin/streamlit
REQUIREMENTS=data/requirements.txt

.PHONY: data
data: $(PYTHON)
	$(PYTHON) -m data

.PHONY: data-st
data-st: $(PYTHON)
	$(STREAMLIT) run run_streamlit.py

.PHONY: server
server:
	$(PYTHON) -m http.server --directory public

$(PYTHON): $(REQUIREMENTS)
	python -m venv .env
	$(PIP) install -r $(REQUIREMENTS)
