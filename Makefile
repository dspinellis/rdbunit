PREFIX = /usr/local
EGTEST=simple datatypes

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
	./runtest.sh python $(EGTEST)
	./runtest.sh python3 $(EGTEST)
	pycodestyle rdbunit.py
	pylint -r n rdbunit.py
