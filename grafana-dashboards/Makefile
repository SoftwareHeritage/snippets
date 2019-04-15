# Generate json dashboards

TARGETS= pergamon.filesystem.sizes.json pergamon.cpu.usage.json	\
	 pergamon.uptime.json pergamon.loadavg.json \
	 pergamon.memory.usage.json pergamon.swap.json \
	 pergamon.network.traffic.json

default: $(TARGETS)

%.json:	%.py
	generate-dashboard -o $@ $<

clean:
	rm $(TARGETS)
