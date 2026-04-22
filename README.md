# Dispensing Margin Leakage POC

A minimal POC pipeline to normalise, match, and calculate dispensing margins against invoice data.

## Prerequisites
* Python 3.9+
* Install dependencies: `pip install -r requirements.txt`
* Ensure the mock CSVs (`dispensing_mock.csv`, `invoices_mock.csv`) are in the root directory.

## Run Instructions

* **Standard Run:**
  `python pipeline.py`

* **Golden Dataset Run:**
  `python pipeline.py --golden`

Outputs will be generated in the `outputs/` directory.