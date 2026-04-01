.PHONY: setup pipeline dashboard

# GitHub Codespaces: after `make dashboard`, open the forwarded port for 8501 (public if needed).

PYTHON ?= python3

setup:
	$(PYTHON) -m pip install -r requirements.txt

pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) frequency_summary.py -o frequencies.csv
	$(PYTHON) response_analysis.py --report response_analysis_report.txt
	$(PYTHON) subset_analysis.py --report subset_analysis_report.txt

dashboard:
	streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
