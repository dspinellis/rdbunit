PREFIX = /usr/local

.PHONY: install
install: rdbunit.py
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp $< $(DESTDIR)$(PREFIX)/bin/rdbunit

.PHONY: uninstall
uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/rdbunit

test:
	cd examples && ../rdbunit.py *.rdbu | mysql -u root -p$$DBPASS -N

qa:
	pep8 rdbunit.py
