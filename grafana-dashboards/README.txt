Task: Grafana dashboards
========================

Goal: replace munin graphs


1. Grafanalib installation
--------------------------

	pip3 install --user grafanalib
	export PATH=$PATH:~/.local/bin


2. Define grafana graph programmaticaly
---------------------------------------

Grafanalib invocation:

	generate-dashboard -o frontend.json frontend.dashboard.py


3. Import dashboard into Grafana
--------------------------------

	Cross on top of the left panel => "Import"
