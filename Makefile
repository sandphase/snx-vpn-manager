.PHONY: help install uninstall test clean lint

PYTHON ?= python3

help:
	@echo "SNX VPN Manager - Makefile Commands"
	@echo "====================================="
	@echo "  make install       Run the universal installer (sudo ./install.sh)"
	@echo "  make uninstall     Run the uninstaller (sudo ./uninstall.sh)"
	@echo "  make test          Run the test suite"
	@echo "  make clean         Remove build artifacts and python cache"
	@echo "  make doctor        Run pre-flight system diagnostics"

install:
	sudo ./install.sh

uninstall:
	sudo ./uninstall.sh

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -v

doctor:
	PYTHONPATH=. $(PYTHON) -m snx_manager doctor

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ *.egg-info .pytest_cache
